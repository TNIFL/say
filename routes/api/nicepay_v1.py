# say/routes/api/nicepay_v1.py
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, url_for, redirect

from core.extensions import csrf
from domain.models import db, Payment, PaymentMethod, Subscription
from auth.entitlements import get_current_user
from utils.idempo import _new_idempo
from routes.api.payments_guard import require_payments_enabled
from services.nicepay import nicepay_approve_payment, nicepay_regist_billing_key

api_nicepay_v1_bp = Blueprint("api_nicepay_v1", __name__)


def _new_order_id(prefix: str) -> str:
    return f"{prefix}_{_new_idempo()}"


def _safe_int(v, default: int = 0) -> int:
    try:
        return int(str(v))
    except Exception:
        return default


def _form_dict() -> dict:
    # NICEPAY return은 form-urlencoded가 일반적
    if request.form:
        return request.form.to_dict(flat=True)
    j = request.get_json(silent=True)
    return j or {}


def _mark_payment_auth(p: Payment, *, form: dict, tid: str) -> None:
    p.psp_transaction_id = tid
    p.auth_result_code = str(form.get("authResultCode") or "")
    p.auth_result_message = str(form.get("authResultMsg") or "")
    p.auth_token = str(form.get("authToken") or "")
    p.signature = str(form.get("signature") or "")
    if hasattr(p, "client_id") and not getattr(p, "client_id", None):
        p.client_id = str(form.get("clientId") or "")


def _fail_payment(p: Payment, *, code: str, msg: str, raw=None) -> None:
    p.status = "failed"
    p.failure_code = code
    p.failure_message = (msg[:500] if msg else msg)
    if raw is not None:
        p.raw_response = raw


def _capture_payment(p: Payment, *, approved: dict) -> bool:
    """
    nicepay approve 응답 성공 처리.
    성공 resultCode는 통상 "0000" (문서/환경에 따라 다를 수 있어 문자열 비교)
    """
    result_code = str(approved.get("resultCode") or "")
    if result_code != "0000":
        return False

    p.status = "captured"
    p.psp_transaction_id = str(approved.get("tid") or p.psp_transaction_id or "")
    p.raw_response = approved
    return True


# ---------------------------------------------------------------------
# 단건 결제 (Server 승인)
# ---------------------------------------------------------------------
@api_nicepay_v1_bp.route("/api/nicepay/payment/start", methods=["POST"])
@csrf.exempt
def nicepay_payment_start():
    require_payments_enabled()

    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401

    cfg = current_app.config
    client_id = (cfg.get("NICEPAY_CLIENT_ID") or "").strip()
    if not client_id:
        return jsonify({"ok": False, "error": "missing_NICEPAY_CLIENT_ID"}), 500

    body = request.get_json(silent=True) or {}
    order_id = _new_order_id("pay")
    amount = _safe_int(body.get("amount"), 1000)
    goods_name = body.get("goodsName") or "Lexinoa 결제"
    return_url = url_for("api_nicepay_v1.nicepay_payment_return", _external=True)

    p = Payment(
        order_id=order_id,
        idempotency_key=_new_idempo(),
        user_id=str(getattr(user, "user_id", "") or getattr(user, "id", "")),
        amount=amount,
        currency="KRW",
        status="ready",
        provider="nicepay",
        client_id=client_id,
        raw_request={
            "kind": "payment",
            "amount": amount,
            "goodsName": goods_name,
            "returnUrl": return_url,
        },
    )
    db.session.add(p)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "clientId": client_id,
            "method": "card",
            "orderId": order_id,
            "amount": amount,
            "goodsName": goods_name,
            "returnUrl": return_url,
        }
    )


@api_nicepay_v1_bp.route("/api/nicepay/payment/return", methods=["POST"])
@csrf.exempt
def nicepay_payment_return():
    """
    결제창 인증 결과 수신 → 서버 승인(/v1/payments/{tid}) 호출 → Payment 반영
    """
    require_payments_enabled()

    form = _form_dict()
    auth_code = str(form.get("authResultCode") or "")
    tid = str(form.get("tid") or "")
    order_id = str(form.get("orderId") or "")
    amount = _safe_int(form.get("amount"), 0)

    if not order_id:
        return redirect(url_for("subscribe.subscribe_fail", reason="missing_orderId"))

    p = Payment.query.filter_by(order_id=order_id).first()
    if not p:
        current_app.logger.warning(f"[nicepay/payment/return] payment_not_found orderId={order_id}")
        return redirect(url_for("subscribe.subscribe_fail", reason="payment_not_found"))

    _mark_payment_auth(p, form=form, tid=tid)
    p.raw_response = form  # 인증 콜백 원문 보관(민감정보 없음 전제)
    db.session.commit()

    if auth_code != "0000":
        _fail_payment(p, code=f"auth_{auth_code}", msg=str(form.get("authResultMsg") or "auth_failed"), raw=form)
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_fail", reason="auth_failed"))

    if not tid or amount <= 0:
        _fail_payment(p, code="invalid_return", msg="tid/amount missing", raw=form)
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_fail", reason="invalid_return"))

    try:
        approved = nicepay_approve_payment(tid=tid, amount=amount)
    except Exception as e:
        _fail_payment(p, code="approve_failed", msg=str(e))
        db.session.commit()
        current_app.logger.exception(f"[nicepay/payment/return] approve_failed: {e}")
        return redirect(url_for("subscribe.subscribe_fail", reason="approve_failed"))

    if not _capture_payment(p, approved=approved):
        _fail_payment(
            p,
            code=str(approved.get("resultCode") or "approve_not_ok"),
            msg=str(approved.get("resultMsg") or "approve_not_ok"),
            raw=approved,
        )
        db.session.commit()
        current_app.logger.warning(f"[nicepay/payment/return] approve_not_ok: {approved}")
        return redirect(url_for("subscribe.subscribe_fail", reason="approve_not_ok"))

    db.session.commit()
    return redirect(url_for("subscribe.subscribe_success", orderId=order_id))


# ---------------------------------------------------------------------
# 정기결제(빌키) — 카드 등록(BID 발급)
# ---------------------------------------------------------------------
@api_nicepay_v1_bp.route("/api/nicepay/subscribe/start", methods=["POST"])
@csrf.exempt
def nicepay_subscribe_start():
    """
    빌키 발급 플로우 시작:
    - 프론트에서 Nicepay 카드 인증창 호출에 필요한 값 반환
    - ReturnURL에서 Payment(orderId)로 user_id를 다시 찾아야 하므로 Payment 선생성
    """
    require_payments_enabled()

    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401
    if not getattr(user, "email_verified", True):
        return jsonify({"ok": False, "error": "email_verify_required"}), 403

    cfg = current_app.config
    client_id = (cfg.get("NICEPAY_CLIENT_ID") or "").strip()
    if not client_id:
        return jsonify({"ok": False, "error": "missing_NICEPAY_CLIENT_ID"}), 500

    body = request.get_json(silent=True) or {}
    # 빌키 발급은 실제 결제가 아니라 인증/등록 목적이므로, 최소금액(문서/정책에 따라)만 사용
    amount = _safe_int(body.get("amount"), 4900)
    goods_name = body.get("goodsName") or "Lexinoa 구독 카드등록"
    order_id = _new_order_id("subreg")

    # customerId는 빌키 발급 API에서 요구(고객 식별자). 사용자별 고정 값 권장.
    user_id = str(getattr(user, "user_id", "") or getattr(user, "id", ""))
    customer_id = f"u_{user_id}"

    return_url = url_for("api_nicepay_v1.nicepay_subscribe_return", _external=True)

    p = Payment(
        order_id=order_id,
        idempotency_key=_new_idempo(),
        user_id=user_id,
        amount=amount,
        currency="KRW",
        status="ready",
        provider="nicepay",
        client_id=client_id,
        raw_request={
            "kind": "subscribe_regist",
            "amount": amount,
            "goodsName": goods_name,
            "customerId": customer_id,
            "returnUrl": return_url,
        },
    )
    db.session.add(p)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "clientId": client_id,
            "method": "card",
            "orderId": order_id,
            "amount": amount,
            "goodsName": goods_name,
            "customerId": customer_id,
            "returnUrl": return_url,
        }
    )


@api_nicepay_v1_bp.route("/api/nicepay/subscribe/return", methods=["POST"])
@csrf.exempt
def nicepay_subscribe_return():
    """
    카드 인증 완료 → tid 확보 → /v1/subscribe/regist 호출 → bid 발급 → PaymentMethod 저장(+구독 연결)
    """
    require_payments_enabled()

    form = _form_dict()
    auth_code = str(form.get("authResultCode") or "")
    tid = str(form.get("tid") or "")
    order_id = str(form.get("orderId") or "")

    if not order_id:
        return redirect(url_for("subscribe.subscribe_fail", reason="missing_orderId"))

    p = Payment.query.filter_by(order_id=order_id).first()
    if not p:
        current_app.logger.warning(f"[nicepay/subscribe/return] payment_not_found orderId={order_id}")
        return redirect(url_for("subscribe.subscribe_fail", reason="payment_not_found"))

    _mark_payment_auth(p, form=form, tid=tid)
    p.raw_response = form
    db.session.commit()

    if auth_code != "0000":
        _fail_payment(p, code=f"auth_{auth_code}", msg=str(form.get("authResultMsg") or "auth_failed"), raw=form)
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_fail", reason="auth_failed"))

    user_id = str(p.user_id or "")
    if not user_id:
        _fail_payment(p, code="user_missing", msg="user_id missing", raw=form)
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_fail", reason="user_missing"))

    # start에서 customerId를 넣었지만 return에서 누락될 수 있어 고정 규칙으로 재생성
    customer_id = str(form.get("customerId") or f"u_{user_id}")

    try:
        issued = nicepay_regist_billing_key(customer_id=customer_id, tid=tid)
    except Exception as e:
        _fail_payment(p, code="bid_regist_failed", msg=str(e))
        db.session.commit()
        current_app.logger.exception(f"[nicepay/subscribe/return] bid_regist_failed: {e}")
        return redirect(url_for("subscribe.subscribe_fail", reason="bid_regist_failed"))

    bid = (issued.get("bid") or issued.get("BID") or issued.get("billingKey") or "").strip()
    if not bid:
        _fail_payment(p, code="bid_missing", msg="bid missing in response", raw=issued)
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_fail", reason="bid_missing"))

    # PaymentMethod upsert (모델 컬럼에 정확히 맞춤)
    pm = (
        PaymentMethod.query.filter_by(user_id=user_id, provider="nicepay")
        .order_by(PaymentMethod.id.desc())
        .first()
    )
    if not pm:
        pm = PaymentMethod(
            user_id=user_id,
            provider="nicepay",
            billing_key=bid,
            status="active",
        )
        db.session.add(pm)
    else:
        pm.billing_key = bid
        pm.status = "active"

    pm.tx_tid = tid
    pm.last_auth_token = str(form.get("authToken") or "")
    pm.last_signature = str(form.get("signature") or "")
    pm.last_order_id = order_id

    # 활성 구독이 있으면 기본 결제수단으로 연결(없으면 pm만 저장)
    sub = (
        Subscription.query.filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "past_due", "trial", "incomplete")),
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub:
        sub.default_payment_method_id = pm.id

    # 카드등록은 “결제 완료”가 아니라 “수단 등록 완료”이므로 상태는 captured 대신 별도 운용 가능.
    # 기존 코드 관성을 유지하려면 captured로 두어도 무방.
    p.status = "captured"
    p.raw_response = issued

    db.session.commit()
    return redirect(url_for("subscribe.subscribe_checkout_complete", bid=bid))
