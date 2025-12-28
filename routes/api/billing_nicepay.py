# routes/api/billing_nicepay.py
from flask import Blueprint, jsonify, request, current_app
from core.extensions import csrf
from domain.models import db
from datetime import datetime, timezone

from utils.time_utils import KST, _compute_anchor_day
from utils.billing_dates import next_billing_kst, to_utc_naive

from auth.entitlements import get_current_user
from utils.idempo import _new_idempo

from services.nicepay import (
    new_order_id,
    nicepay_subscribe_pay,
    verify_signature,
)

api_nicepay_subscribe_complete_bp = Blueprint("api_nicepay_subscribe_complete", __name__)


def _utcnow_naive() -> datetime:
    # DB가 timezone=False (naive UTC)인 전제
    return datetime.now(timezone.utc).replace(tzinfo=None)


@csrf.exempt
@api_nicepay_subscribe_complete_bp.route("/api/nicepay/subscribe/complete", methods=["POST"])
def nicepay_subscribe_complete():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401
    if not user.email_verified:
        return jsonify({"ok": False, "error": "email_verify_required"}), 403

    payload = request.get_json(silent=True) or {}
    bid = (payload.get("bid") or "").strip()
    if not bid:
        return jsonify({"ok": False, "error": "bid_required"}), 400

    # 서버 기준 플랜
    plan_name = "pro_monthly"
    plan_amount = 4900  # KRW (int)

    from domain.models import PaymentMethod, Subscription, Payment

    order_id = None
    sub_id = None
    pm_id = None

    # ------------------------------------------------------------------
    # 1) 결제수단 저장 + Subscription(incomplete) + Payment(pending)
    # ------------------------------------------------------------------
    try:
        # 기존 active 결제수단 비활성화
        (
            db.session.query(PaymentMethod)
            .filter(
                PaymentMethod.user_id == user.user_id,
                PaymentMethod.status == "active",
            )
            .update({"status": "inactive"})
        )

        pm = PaymentMethod(
            user_id=user.user_id,
            provider="nicepay",
            billing_key=bid,
            status="active",
        )
        db.session.add(pm)
        db.session.flush()
        pm_id = pm.id

        now_kst = datetime.now(KST)
        anchor_day = _compute_anchor_day(now_kst)

        sub = Subscription(
            user_id=user.user_id,
            status="incomplete",
            plan_name=plan_name,
            plan_amount=plan_amount,
            anchor_day=anchor_day,
            current_period_start=now_kst.date(),
            current_period_end=None,
            next_billing_at=None,
            cancel_at_period_end=False,
            default_payment_method_id=pm.id,
            fail_count=0,
            retry_at=None,
            last_failed_at=None,
        )
        db.session.add(sub)
        db.session.flush()
        sub_id = sub.id

        order_id = new_order_id("first")

        pay = Payment(
            user_id=user.user_id,
            subscription_id=sub.id,
            provider="nicepay",
            order_id=order_id,
            idempotency_key=_new_idempo(),
            amount=plan_amount,
            currency="KRW",
            status="pending",
            raw_request={
                "kind": "first_charge",
                "bid": bid,
                "orderId": order_id,
                "amount": plan_amount,
            },
        )
        db.session.add(pay)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error", "message": str(e)}), 500

    # ------------------------------------------------------------------
    # (안전 분기) CLIENT_ID/SECRET_KEY 없으면 첫 결제는 스킵하고 구독만 활성화
    # - 테스트(MID/MERCHANT_KEY) 단계에서 500/400을 방지
    # ------------------------------------------------------------------
    cfg = current_app.config
    if not (cfg.get("NICEPAY_CLIENT_ID") and cfg.get("NICEPAY_SECRET_KEY")):
        try:
            now_kst = datetime.now(KST)
            anchor_day = _compute_anchor_day(now_kst)
            next_kst = next_billing_kst(now_kst, anchor_day)
            next_utc = to_utc_naive(next_kst)

            pay_row = Payment.query.filter_by(order_id=order_id).first()
            sub_row = Subscription.query.get(sub_id)

            if pay_row:
                pay_row.status = "skipped"
                pay_row.raw_response = {"note": "first_charge_skipped_no_client_credentials"}

            if sub_row:
                sub_row.status = "active"
                sub_row.anchor_day = anchor_day
                sub_row.current_period_end = next_kst.date()
                sub_row.next_billing_at = next_utc

            db.session.commit()

            return jsonify({"ok": True, "status": "subscribed_no_charge", "orderId": order_id}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": "activate_without_charge_failed", "message": str(e)}), 500


    # ------------------------------------------------------------------
    # 2) NICEPAY 서버-서버 첫 결제
    # ------------------------------------------------------------------
    paid = None
    try:
        paid = nicepay_subscribe_pay(
            bid,
            order_id=order_id,
            amount=int(plan_amount),
            goods_name="Lexinoa Pro 월구독(첫 결제)",
            buyer_name=user.user_id,
            buyer_email=user.email,
        )

        if str(paid.get("resultCode")) != "0000":
            raise RuntimeError(f"NICEPAY_FAIL {paid}")

        tid = paid.get("tid")
        resp_edi_date = paid.get("ediDate")
        signature = paid.get("signature")

        if tid and resp_edi_date and signature:
            if not verify_signature(tid, int(plan_amount), resp_edi_date, signature):
                raise RuntimeError("NICEPAY_SIGNATURE_MISMATCH")

        # ------------------------------------------------------------------
        # 3) 성공 반영 (billing_dates 유틸 사용)
        # ------------------------------------------------------------------
        now_kst = datetime.now(KST)
        anchor_day = _compute_anchor_day(now_kst)

        next_kst = next_billing_kst(now_kst, anchor_day)
        next_utc = to_utc_naive(next_kst)

        pay_row = Payment.query.filter_by(order_id=order_id).first()
        if not pay_row:
            raise RuntimeError("PAYMENT_ROW_MISSING")

        sub_row = Subscription.query.get(pay_row.subscription_id)
        if not sub_row:
            raise RuntimeError("SUBSCRIPTION_ROW_MISSING")

        pay_row.status = "captured"
        pay_row.psp_transaction_id = tid
        pay_row.raw_response = paid

        sub_row.status = "active"
        sub_row.anchor_day = anchor_day
        sub_row.current_period_start = now_kst.date()
        sub_row.current_period_end = next_kst.date()
        sub_row.next_billing_at = next_utc
        sub_row.fail_count = 0
        sub_row.retry_at = None
        sub_row.last_failed_at = None

        db.session.commit()

        return jsonify({"ok": True, "status": "subscribed", "orderId": order_id}), 200

    # ------------------------------------------------------------------
    # 4) 첫 결제 실패 처리
    # ------------------------------------------------------------------
    except Exception as e:
        db.session.rollback()

        try:
            pay_row = Payment.query.filter_by(order_id=order_id).first()
            if pay_row:
                pay_row.status = "failed"
                pay_row.failure_message = str(e)
                pay_row.raw_response = paid

                sub_row = Subscription.query.get(pay_row.subscription_id)
                if sub_row:
                    sub_row.status = "canceled"
                    sub_row.canceled_at = _utcnow_naive()
                    sub_row.cancel_at_period_end = True

                    pm_row = PaymentMethod.query.get(sub_row.default_payment_method_id)
                    if pm_row:
                        pm_row.status = "inactive"

            db.session.commit()
        except Exception as e2:
            db.session.rollback()
            return jsonify({"ok": False, "error": "first_payment_failed_and_db_failed", "message": f"{e} / {e2}"}), 500

        return jsonify({"ok": False, "error": "first_payment_failed", "message": str(e)}), 400
