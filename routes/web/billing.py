# routes/web/billing.py
from flask import Blueprint, redirect, url_for
from auth.entitlements import get_current_user
from domain.models import db, Subscription

billing_bp = Blueprint("billing", __name__)

def _get_active_subscription(user_id: str):
    return (
        Subscription.query
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "past_due")),  # incomplete 제외
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

@billing_bp.route("/billing/cancel", methods=["POST"])
def cancel_subscription():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login_page", next="/mypage"))

    sub = _get_active_subscription(user.user_id)
    if not sub:
        return redirect("/mypage")

    try:
        sub.cancel_at_period_end = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        return redirect("/mypage?err=billing_cancel_failed")

    return redirect("/mypage")

@billing_bp.route("/billing/resume", methods=["POST"])
def resume_subscription():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login_page", next="/mypage"))

    sub = _get_active_subscription(user.user_id)
    if not sub:
        return redirect("/mypage")

    try:
        sub.cancel_at_period_end = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        return redirect("/mypage?err=billing_resume_failed")

    return redirect("/mypage")
