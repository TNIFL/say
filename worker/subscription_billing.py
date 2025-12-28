# worker/subscription_billing.py
import os
import time
from datetime import datetime, timedelta, timezone

from app import create_app
from domain.models import db
from domain.models import Subscription, Payment, PaymentMethod, User

from utils.idempo import _new_idempo
from utils.time_utils import KST, _compute_anchor_day
from utils.billing_dates import next_billing_kst, to_utc_naive

from services.nicepay import new_order_id, nicepay_subscribe_pay, verify_signature


RETRY_MAX = 3
RETRY_INTERVAL_DAYS = 1
POLL_SECONDS = int(os.getenv("BILLING_POLL_SECONDS", "120"))
BATCH_LIMIT = int(os.getenv("BILLING_BATCH_LIMIT", "50"))


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pick_due_subscriptions(now_utc: datetime, limit: int = 50):
    q = (
        Subscription.query
        .filter(
            Subscription.status.in_(("active", "past_due")),
            Subscription.cancel_at_period_end.is_(False),
        )
        .join(PaymentMethod, PaymentMethod.id == Subscription.default_payment_method_id)
        .filter(
            PaymentMethod.status == "active",
            PaymentMethod.billing_key.isnot(None),
        )
        .filter(
            (
                (Subscription.retry_at.isnot(None)) & (Subscription.retry_at <= now_utc)
            )
            | (
                (Subscription.retry_at.is_(None))
                & (Subscription.next_billing_at.isnot(None))
                & (Subscription.next_billing_at <= now_utc)
            )
        )
        .order_by(
            Subscription.retry_at.asc().nullslast(),
            Subscription.next_billing_at.asc().nullslast(),
            Subscription.id.asc(),
        )
        .limit(limit)
    )
    return q.all()


def _finalize_cancellations(now_utc: datetime, limit: int = 200):
    subs = (
        Subscription.query
        .filter(
            Subscription.status.in_(("active", "past_due")),
            Subscription.cancel_at_period_end.is_(True),
            Subscription.next_billing_at.isnot(None),
            Subscription.next_billing_at <= now_utc,
        )
        .order_by(Subscription.next_billing_at.asc())
        .limit(limit)
        .all()
    )

    if not subs:
        return 0

    try:
        for s in subs:
            s.status = "canceled"
            s.canceled_at = now_utc
            s.retry_at = None
        db.session.commit()
        return len(subs)
    except Exception:
        db.session.rollback()
        return 0


def _get_user_email(user_id: str) -> str:
    u = User.query.filter_by(user_id=user_id).first()
    return (u.email or "") if u else ""


def _success_rollover_period(sub: Subscription):
    now_kst = datetime.now(KST)
    anchor_day = sub.anchor_day or _compute_anchor_day(now_kst)
    sub.anchor_day = anchor_day

    next_kst = next_billing_kst(now_kst, anchor_day)
    sub.current_period_start = now_kst.date()
    sub.current_period_end = next_kst.date()
    sub.next_billing_at = to_utc_naive(next_kst)


def _fail_and_schedule_retry_or_cancel(sub: Subscription, now_utc: datetime):
    sub.status = "past_due"
    sub.fail_count = int(sub.fail_count or 0) + 1
    sub.last_failed_at = now_utc

    if sub.fail_count >= RETRY_MAX:
        sub.status = "canceled"
        sub.cancel_at_period_end = True
        sub.canceled_at = now_utc
        sub.retry_at = None
    else:
        sub.retry_at = now_utc + timedelta(days=RETRY_INTERVAL_DAYS)


def _process_one_subscription(sub: Subscription, now_utc: datetime):
    pm = PaymentMethod.query.get(sub.default_payment_method_id)
    if not pm or pm.status != "active" or not pm.billing_key:
        return

    bid = pm.billing_key
    amount = int(sub.plan_amount)
    order_id = new_order_id("rebill")
    idempo = _new_idempo()
    buyer_email = _get_user_email(sub.user_id)

    # (1) Payment row 생성 (커밋 먼저)
    try:
        pay = Payment(
            user_id=sub.user_id,
            subscription_id=sub.id,
            provider="nicepay",
            order_id=order_id,
            idempotency_key=idempo,
            amount=amount,
            currency="KRW",
            status="pending",
            raw_request={
                "kind": "rebill",
                "bid": bid,
                "orderId": order_id,
                "amount": amount,
                "sub_id": sub.id,
                "fail_count_before": int(sub.fail_count or 0),
                "retry_at_before": sub.retry_at.isoformat() if sub.retry_at else None,
                "next_billing_at_before": sub.next_billing_at.isoformat() if sub.next_billing_at else None,
            },
        )
        db.session.add(pay)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return

    paid = None
    try:
        # (2) NICEPAY 승인 호출
        paid = nicepay_subscribe_pay(
            bid,
            order_id=order_id,
            amount=amount,
            goods_name=f"Lexinoa {sub.plan_name} 월구독",
            buyer_name=sub.user_id,
            buyer_email=buyer_email,
        )

        if str(paid.get("resultCode")) != "0000":
            raise RuntimeError(f"NICEPAY_FAIL {paid}")

        tid = paid.get("tid")
        resp_edi_date = paid.get("ediDate")
        signature = paid.get("signature")

        if tid and resp_edi_date and signature:
            if not verify_signature(tid, amount, resp_edi_date, signature):
                raise RuntimeError("NICEPAY_SIGNATURE_MISMATCH")

        # (3) 성공 반영
        pay_row = Payment.query.filter_by(order_id=order_id).first()
        sub2 = Subscription.query.get(sub.id)
        if not pay_row or not sub2:
            raise RuntimeError("DB_ROW_MISSING_AFTER_PAY")

        pay_row.status = "captured"
        pay_row.psp_transaction_id = tid
        pay_row.raw_response = paid

        sub2.status = "active"
        sub2.fail_count = 0
        sub2.retry_at = None
        sub2.last_failed_at = None
        _success_rollover_period(sub2)

        db.session.commit()
        return

    except Exception as e:
        db.session.rollback()

        # (4) 실패 반영 + 재시도/자동해지
        try:
            pay_row = Payment.query.filter_by(order_id=order_id).first()
            sub2 = Subscription.query.get(sub.id)

            if pay_row:
                pay_row.status = "failed"
                pay_row.failure_message = str(e)
                pay_row.raw_response = paid

            if sub2:
                _fail_and_schedule_retry_or_cancel(sub2, now_utc)

            db.session.commit()
        except Exception:
            db.session.rollback()
        return


def run_once(app):
    with app.app_context():
        now_utc = _now_utc_naive()
        _finalize_cancellations(now_utc)

        subs = _pick_due_subscriptions(now_utc, limit=BATCH_LIMIT)
        for sub in subs:
            _process_one_subscription(sub, now_utc)


def run_loop():
    app = create_app()

    while True:
        try:
            run_once(app)
        except Exception as e:
            print(f"[billing-worker] error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_loop()
