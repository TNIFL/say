from flask import request, Blueprint, jsonify, current_app
import os


from core.extensions import csrf
from services.nicepay import _new_order_id, _nicepay_iso8601_kst, _nicepay_sign_pay, nicepay_request
from utils.idempo import _new_idempo
from utils.time_utils import _utcnow, KST
from domain.models import db
from datetime import datetime, timezone

api_internal_cron_bp = Blueprint("internal_cron", __name__)


# ---- 4) 정기 청구 스케줄러 — 내부용 Cron 엔드포인트 ----
@api_internal_cron_bp.route("/internal/cron/bill-due", methods=["POST"])
@csrf.exempt
def cron_bill_due():
    """
    - 서버 크론 또는 외부 스케줄러(Cloud Scheduler 등)가 1일 1회 호출.
    - 오늘 anchor_day인 구독을 찾아 `next_billing_at <= now` 인 것만 청구.
    - 헤더 Authorization: Bearer <CRON_SECRET> 체크.
    """
    auth = request.headers.get("Authorization", "")
    want = f"Bearer {os.getenv('CRON_SECRET', '')}"

    cfg = current_app.config
    if not want or auth != want:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    from domain.models import Subscription, Payment
    now_utc = _utcnow()

    due = (
        Subscription.query
        .filter(
            Subscription.status == "active",
            Subscription.next_billing_at != None,  # noqa: E711
            Subscription.next_billing_at <= now_utc
        )
        .all()
    )

    charged = 0
    for sub in due:
        # 결제수단
        pm = None
        if sub.default_payment_method_id:
            pm = db.session.get(type('PM', (), {'__tablename__': 'payment_methods'}), sub.default_payment_method_id)
        if not pm:
            pm = None
            pm = db.session.query(db.Model.metadata.tables['payment_methods']).filter_by(
                id=sub.default_payment_method_id
            ).first()

        # 안전하게 다시 조회
        from domain.models import PaymentMethod as PM
        pm = PM.query.get(sub.default_payment_method_id) if sub.default_payment_method_id else None
        if not pm or pm.status != "active":
            continue  # 다음번에 재시도

        order_id = _new_order_id("recurr")
        idempo = _new_idempo()
        req = {
            "billingKey": pm.billing_key,
            "orderId": order_id,
            "amount": int(sub.plan_amount),
            "orderName": f"Lexinoa Pro 월구독",
            "customerKey": f"u_{sub.user_id}",
            "currency": "KRW",
            "useEscrow": False,
            "taxFreeAmount": 0,
            "metadata": {"user_id": sub.user_id, "subscription_id": sub.id},
        }

        # Payment row 생성
        with db.session.begin():
            prow = Payment(
                user_id=sub.user_id,
                subscription_id=sub.id,
                provider="nicepay",
                order_id=order_id,
                idempotency_key=idempo,
                amount=sub.plan_amount,
                currency="KRW",
                status="pending",
                raw_request=req,
            )
            db.session.add(prow)
            db.session.flush()

        # (Cron 내부) 토스 결제 시도 부분을 NICEPAY 호출로 교체
        try:
            edi_date = _nicepay_iso8601_kst()
            sign_data = _nicepay_sign_pay(order_id, pm.billing_key,
                                          edi_date)  # :contentReference[oaicite:19]{index=19}

            req = {
                "orderId": order_id,
                "amount": int(sub.plan_amount),
                "goodsName": "Lexinoa Pro 월구독",
                "cardQuota": "0",
                "useShopInterest": False,  # :contentReference[oaicite:20]{index=20}
                "buyerName": sub.user_id,
                "buyerEmail": None,
                "ediDate": edi_date,
                "signData": sign_data,  # :contentReference[oaicite:21]{index=21}
                "returnCharSet": "utf-8",
            }

            res = nicepay_request("POST", cfg.get("NICEPAY_PATH_SUBSCRIBE_PAY").format(bid=pm.billing_key), req)

            if str(res.get("resultCode")) != "0000":
                raise RuntimeError(f"NICEPAY_FAIL {res}")

            tx = res.get("tid")

            with db.session.begin():
                prow = Payment.query.filter_by(order_id=order_id).first()
                prow.status = "captured"
                prow.psp_transaction_id = tx
                prow.raw_response = res
                db.session.add(prow)

                # 다음 청구일 갱신(기존 로직 유지)
                cur = sub.next_billing_at.astimezone(KST)
                if cur.month == 12:
                    nxt = datetime(cur.year + 1, 1, min(sub.anchor_day or cur.day, 28), tzinfo=KST)
                else:
                    nxt = datetime(cur.year, cur.month + 1, min(sub.anchor_day or cur.day, 28), tzinfo=KST)
                sub.next_billing_at = nxt.astimezone(timezone.utc)
                db.session.add(sub)

            charged += 1

        except Exception as e:
            with db.session.begin():
                prow = Payment.query.filter_by(order_id=order_id).first()
                prow.status = "failed"
                prow.failure_message = str(e)
                db.session.add(prow)
            continue

    return jsonify({"ok": True, "charged": charged, "due_count": len(due)}), 200