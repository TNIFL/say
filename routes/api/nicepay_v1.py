# say/routes/api/nicepay_v1.py
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, url_for, redirect
from core.extensions import csrf
from domain.models import db, Payment, PaymentMethod
from auth.entitlements import get_current_user
from utils.idempo import _new_idempo

from routes.api.payments_guard import require_payments_enabled
from services.nicepay_v1 import approve_payment, regist_billing_key

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
    """
    인증 결과(결제창 콜백)에서 가능한 필드를 Payment에 기록.
    필드가 Payment 모델에 존재한다는 전제(너 로그 기준 존재).
    """
    p.psp_transaction_id = tid
    p.auth_result_code = str(form.get("authResultCode") or "")
    p.auth_result_message = str(form.get("authResultMsg") or "")
    p.auth_token = str(form.get("authToken") or "")
    p.signature = str(form.get("signature") or "")
    # clientId는 start에서 넣는 게 기본이지만, return에서도 들어오는 경우가 있어 보강
    if hasattr(p, "client_id") and not getattr(p, "client_id", None):
        p.client_id = str(form.get("clientId") or "")


def _fail_payment(p: Payment, *, code: str, msg: str, raw=None) -> None:
    p.status = "failed"
    p.failure_code = code
    p.failure_message = msg[:500] if msg else msg  # 너무 길면 컷(선택)
    if raw is not None:
        p.raw_response = raw


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

    # Payment 선생성 (idempotency_key NOT NULL 대응)
    p = Payment(
        order_id=order_id,
        idempotency_key=_new_idempo(),
        user_id=user.id,
        amount=amount,
        currency="KRW",
        status="ready",
        provider="nicepay",
        client_id=client_id,
    )
    db.session.add(p)
    db.session.commit()

    return jsonify({
        "ok": True,
        "clientId": client_id,
        "method": "card",
        "orderId": order_id,
        "amount": amount,
        "goodsName": goods_name,
        "returnUrl": return_url,
    })


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

    if auth_code != "0000" or not tid or not order_id:
        current_app.logger.warning(f"[nicepay/payment/return] auth_failed: {form}")
        return redirect(url_for("subscribe.subscribe_fail", reason="auth_failed"))

    p = Payment.query.filter_by(order_id=order_id).first()
    if not p:
        current_app.logger.warning(f"[nicepay/payment/return] payment_not_found orderId={order_id}")
        return redirect(url_for("subscribe.subscribe_fail", reason="payment_not_found"))

    # 인증 결과 기록
    _mark_payment_auth(p, form=form, tid=tid)
    db.session.commit()

    # 승인 요청
    try:
        approved = approve_payment(tid=tid, amount=amount)
    except Exception as e:
        _fail_payment(p, code="approve_failed", msg=str(e))
        db.session.commit()
        current_app.logger.exception(f"[nicepay/payment/return] approve_failed: {e}")
        return redirect(url_for("subscribe.subscribe_fail", reason="approve_failed"))

    p.raw_response = approved
    if str(approved.get("resultCode")) == "0000":
        p.status = "paid"
        db.session.commit()
        return redirect(url_for("subscribe.subscribe_success", orderId=order_id))

    _fail_payment(
        p,
        code=str(approved.get("resultCode") or "approve_not_ok"),
        msg=str(approved.get("resultMsg") or "approve_not_ok"),
        raw=approved,
    )
    db.session.commit()
    current_app.logger.warning(f"[nicepay/payment/return] approve_not_ok: {approved}")
    return redirect(url_for("subscribe.subscribe_fail", reason="approve_not_ok"))


# ---------------------------------------------------------------------
# 정기결제(빌키) — 카드 등록(BID 발급)
# ---------------------------------------------------------------------
@api_nicepay_v1_bp.route("/api/nicepay/subscribe/start", methods=["POST"])
@csrf.exempt
def nicepay_subscribe_start():
    """
    빌키(BID) 발급을 위한 '카드 인증' 시작.
    - 결제창 인증 성공 후 returnUrl로 tid가 넘어옴
    - return에서 /v1/subscribe/regist를 호출해서 bid를 발급받고 PaymentMethod에 저장
    """
    require_payments_enabled()

    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401

    cfg = current_app.config
    client_id = (cfg.get("NICEPAY_CLIENT_ID") or "").strip()
    if not client_id:
        return jsonify({"ok": False, "error": "missing_NICEPAY_CLIENT_ID"}), 500

    body = request.get_json(silent=True) or {}
    order_id = _new_order_id("subreg")

    # 카드등록(빌키 발급) 플로우에서 amount는 정책에 따라 다를 수 있음.
    # 샌드박스에서는 임의값 반환이므로 테스트 편의상 금액 유지.
    amount = _safe_int(body.get("amount"), 4900)
    goods_name = body.get("goodsName") or "Lexinoa 구독(빌키발급)"

    return_url = url_for("api_nicepay_v1.nicepay_subscribe_return", _external=True)

    # return에서 user_id를 확보하기 위해 Payment를 선생성 (쿠키 없어도 됨)
    p = Payment(
        order_id=order_id,
        idempotency_key=_new_idempo(),
        user_id=user.id,
        amount=amount,
        currency="KRW",
        status="ready",
        provider="nicepay",
        client_id=client_id,
    )
    db.session.add(p)
    db.session.commit()

    return jsonify({
        "ok": True,
        "clientId": client_id,
        "method": "card",
        "orderId": order_id,
        "amount": amount,
        "goodsName": goods_name,
        "returnUrl": return_url,
    })


@api_nicepay_v1_bp.route("/api/nicepay/subscribe/return", methods=["POST"])
@csrf.exempt
def nicepay_subscribe_return():
    """
    카드 인증 완료 → tid 확보 → /v1/subscribe/regist 호출 → bid 발급 → PaymentMethod에 저장

    주의:
    - 여기서 approve_payment(/v1/payments/{tid})를 호출하지 않음.
      (운영에서 실결제 위험 + 카드등록 단계의 목적이 "BID 발급"이기 때문)
    """
    require_payments_enabled()

    form = _form_dict()
    auth_code = str(form.get("authResultCode") or "")
    tid = str(form.get("tid") or "")
    order_id = str(form.get("orderId") or "")

    if auth_code != "0000" or not tid or not order_id:
        current_app.logger.warning(f"[nicepay/subscribe/return] auth_failed: {form}")
        return redirect(url_for("subscribe.subscribe_fail", reason="auth_failed"))

    p = Payment.query.filter_by(order_id=order_id).first()
    if not p:
        current_app.logger.warning(f"[nicepay/subscribe/return] payment_not_found orderId={order_id}")
        return redirect(url_for("subscribe.subscribe_fail", reason="payment_not_found"))

    # 인증 결과 기록(추적성)
    _mark_payment_auth(p, form=form, tid=tid)
    db.session.commit()

    user_id = p.user_id
    customer_id = f"user_{user_id}"

    # 빌키 발급
    try:
        issued = regist_billing_key(customer_id=customer_id, tid=tid)
    except Exception as e:
        _fail_payment(p, code="regist_failed", msg=str(e))
        db.session.commit()
        current_app.logger.exception(f"[nicepay/subscribe/return] regist_failed: {e}")
        return redirect(url_for("subscribe.subscribe_fail", reason="regist_failed"))

    # Payment에 raw 저장(디버깅)
    p.raw_response = issued
    db.session.commit()

    bid = (issued.get("bid") or issued.get("BID") or issued.get("billingKey") or "").strip()
    if not bid:
        _fail_payment(p, code="bid_missing", msg="bid missing in response", raw=issued)
        db.session.commit()
        current_app.logger.warning(f"[nicepay/subscribe/return] bid_missing: {issued}")
        return redirect(url_for("subscribe.subscribe_fail", reason="bid_missing"))

    # PaymentMethod upsert
    pm = PaymentMethod.query.filter_by(user_id=user_id).order_by(PaymentMethod.id.desc()).first()
    if not pm:
        pm = PaymentMethod(user_id=user_id, method="card", provider="nicepay")
        db.session.add(pm)

    pm.nicepay_bid = bid
    pm.nicepay_customer_id = customer_id
    pm.status = "active"
    pm.raw = issued
    db.session.commit()

    return redirect(url_for("subscribe.subscribe_checkout_complete", bid=bid))
