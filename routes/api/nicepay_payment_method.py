# routes/api/nicepay_payment_method.py
from flask import Blueprint, jsonify, request
from core.extensions import csrf
from auth.entitlements import get_current_user
from domain.models import db, PaymentMethod, Subscription

api_nicepay_pm_bp = Blueprint("api_nicepay_pm", __name__)

def _get_active_subscription(user_id: str):
    return (
        Subscription.query
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "past_due", "incomplete")),
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

@csrf.exempt
@api_nicepay_pm_bp.route("/api/nicepay/payment-method/change", methods=["POST"])
def change_payment_method():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401
    if not user.email_verified:
        return jsonify({"ok": False, "error": "email_verify_required"}), 403

    payload = request.get_json(silent=True) or {}
    bid = (payload.get("bid") or "").strip()
    if not bid:
        return jsonify({"ok": False, "error": "bid_required"}), 400

    sub = _get_active_subscription(user.user_id)
    if not sub:
        return jsonify({"ok": False, "error": "no_active_subscription"}), 400

    try:
        # 기존 active 결제수단 비활성화
        PaymentMethod.query.filter(
            PaymentMethod.user_id == user.user_id,
            PaymentMethod.status == "active",
        ).update({"status": "inactive"})

        # 새 결제수단 생성
        pm = PaymentMethod(
            user_id=user.user_id,
            provider="nicepay",
            billing_key=bid,
            status="active",
        )
        db.session.add(pm)
        db.session.flush()

        # 구독 연결
        sub.default_payment_method_id = pm.id

        db.session.commit()
        return jsonify({"ok": True}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "server_error", "message": str(e)}), 500
