# routes/api/subscription.py
from flask import Blueprint, jsonify, current_app
from core.extensions import csrf
from domain.models import db
from datetime import datetime

from auth.entitlements import get_current_user
from domain.models import Subscription

api_subscription_bp = Blueprint("api_subscription", __name__)


@csrf.exempt
@api_subscription_bp.route("/api/subscription/cancel", methods=["POST"])
def cancel_subscription_at_period_end():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401

    # 현재 active/past_due 구독 1개를 기준(서비스 정책에 맞게 조정 가능)
    sub = (
        Subscription.query
        .filter(
            Subscription.user_id == user.user_id,
            Subscription.status.in_(("active", "past_due")),
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub:
        return jsonify({"ok": False, "error": "no_active_subscription"}), 404

    with db.session.begin():
        sub.cancel_at_period_end = True
        # 즉시 해지가 아니므로 status는 유지(active/past_due)
        # canceled_at은 주기 종료 시점에 찍는 것이 정합성에 맞음

    return jsonify({"ok": True, "cancel_at_period_end": True}), 200
