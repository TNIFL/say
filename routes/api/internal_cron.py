from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy.exc import IntegrityError

from core.extensions import csrf
from domain.models import db, Subscription, PaymentMethod, Payment
from services.account_delete import purge_expired_accounts
from services.nicepay import nicepay_subscribe_pay, new_order_id
from utils.billing_dates import next_billing_kst, to_utc_naive
from utils.time_utils import KST

api_internal_cron_bp = Blueprint("internal_cron", __name__)


def _now_utc_naive() -> datetime:
    # DB(timestamp without tz) 비교를 위해 naive UTC 사용
    return datetime.utcnow().replace(tzinfo=None)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@api_internal_cron_bp.route("/internal/cron/bill-due", methods=["POST"])
@csrf.exempt
def cron_bill_due():
    """
    - 외부 스케줄러가 호출(중복 호출 가능성을 전제로 멱등/락 처리)
    - status=active 이면서 next_billing_at <= now 인 구독을 청구
    - retry_at이 있으면 retry_at <= now 에서만 재시도
    - Authorization: Bearer <CRON_SECRET>
    """
    auth = request.headers.get("Authorization", "")
    want = f"Bearer {os.getenv('CRON_SECRET', '')}".strip()

    if not want or auth != want:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    now_utc = _now_utc_naive()

    # 동시 실행/중복 실행 대비: 구독 row를 락 + 멱등키 유니크로 2중 방어
    due = (
        Subscription.query.filter(
            Subscription.status == "active",
            Subscription.next_billing_at.isnot(None),
            Subscription.next_billing_at <= now_utc,
            (
                (Subscription.retry_at.is_(None))
                | (Subscription.retry_at <= now_utc)
            ),
        )
        .with_for_update(skip_locked=True)
        .limit(50)
        .all()
    )

    charged = 0
    skipped = 0
    failed = 0

    for sub in due:
        # 결제수단 확인
        pm = sub.default_payment_method
        if not pm and sub.default_payment_method_id:
            pm = PaymentMethod.query.get(sub.default_payment_method_id)

        if not pm or pm.status != "active" or not pm.billing_key:
            skipped += 1
            continue

        # “이번 청구 건” 멱등키: (구독ID + 청구일(KST 기준))로 고정
        nb_aware = _as_utc_aware(sub.next_billing_at).astimezone(KST)
        bill_key = f"bill:{sub.id}:{nb_aware.date().isoformat()}"

        order_id = new_order_id("recurr")

        # Payment 선생성: 멱등키 UNIQUE로 중복 과금 방지
        try:
            with db.session.begin():
                prow = Payment(
                    user_id=sub.user_id,
                    subscription_id=sub.id,
                    provider="nicepay",
                    order_id=order_id,
                    idempotency_key=bill_key,
                    amount=sub.plan_amount,
                    currency="KRW",
                    status="pending",
                    raw_request={
                        "kind": "subscription_charge",
                        "subscription_id": sub.id,
                        "user_id": sub.user_id,
                        "billing_key": pm.billing_key,
                        "plan_name": sub.plan_name,
                        "plan_amount": str(sub.plan_amount),
                        "anchor_day": sub.anchor_day,
                        "target_kst_date": nb_aware.date().isoformat(),
                    },
                )
                db.session.add(prow)
        except IntegrityError:
            # 이미 같은 청구건이 처리/진행 중
            db.session.rollback()
            skipped += 1
            continue

        # 실제 과금 호출
        try:
            res = nicepay_subscribe_pay(
                pm.billing_key,
                order_id=order_id,
                amount=int(sub.plan_amount),
                goods_name=f"Lexinoa {sub.plan_name} 월구독",
                buyer_name=str(sub.user_id),
                buyer_email="",
            )

            if str(res.get("resultCode") or "") != "0000":
                raise RuntimeError(f"NICEPAY_FAIL {res}")

            tid = str(res.get("tid") or "")

            # 성공 처리 + 다음 청구일 갱신 + 실패 카운터 리셋
            with db.session.begin():
                prow = Payment.query.filter_by(idempotency_key=bill_key).first()
                if not prow:
                    # 이 경우는 거의 없지만, 안전하게 방어
                    raise RuntimeError("payment_row_missing_after_charge")

                prow.status = "captured"
                prow.psp_transaction_id = tid
                prow.raw_response = res
                db.session.add(prow)

                # 다음 청구일(말일 자동 보정)
                cur_kst = nb_aware  # 이번 청구 기준일(원래 next_billing_at)
                anchor = int(sub.anchor_day or cur_kst.day)
                nxt_kst = next_billing_kst(cur_kst, anchor)

                sub.current_period_start = cur_kst.date()
                sub.current_period_end = nxt_kst.date()
                sub.next_billing_at = to_utc_naive(nxt_kst)

                sub.fail_count = 0
                sub.retry_at = None
                sub.last_failed_at = None

                db.session.add(sub)

            charged += 1

        except Exception as e:
            # 실패 처리 + 재시도 스케줄링
            with db.session.begin():
                prow = Payment.query.filter_by(idempotency_key=bill_key).first()
                if prow:
                    prow.status = "failed"
                    prow.failure_code = "billing_failed"
                    prow.failure_message = str(e)[:500]
                    db.session.add(prow)

                sub.fail_count = int(sub.fail_count or 0) + 1
                sub.last_failed_at = now_utc

                # 재시도 정책: 1일 → 3일 → 7일, 3회 이상이면 past_due
                if sub.fail_count == 1:
                    sub.retry_at = now_utc + timedelta(days=1)
                elif sub.fail_count == 2:
                    sub.retry_at = now_utc + timedelta(days=3)
                else:
                    sub.retry_at = now_utc + timedelta(days=7)
                    sub.status = "past_due"

                db.session.add(sub)

            failed += 1
            continue

    return jsonify(
        {
            "ok": True,
            "due_count": len(due),
            "charged": charged,
            "skipped": skipped,
            "failed": failed,
        }
    ), 200

# 회원 탈퇴 시 30일 유예기간
@api_internal_cron_bp.route("/internal/cron/purge-accounts", methods=["POST"])
@csrf.exempt
def cron_purge_accounts():
    """
    30일 유예가 끝난 계정을 완전 탈퇴 처리.
    헤더: Authorization: Bearer <CRON_SECRET>
    """
    auth = (request.headers.get("Authorization") or "").strip()
    # 환경변수에서 CRON_SECRET 읽기 (프로젝트 방식에 맞게 current_app.config 사용해도 됨)
    import os
    expected = os.getenv("CRON_SECRET", "")

    if not expected or auth != f"Bearer {expected}":
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    # 기본은 100개씩 처리 (필요 시 조정)
    result = purge_expired_accounts(limit=200)
    return jsonify(result), 200