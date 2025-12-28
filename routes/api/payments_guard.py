# say/routes/api/payments_guard.py
from flask import current_app, abort
from auth.entitlements import get_current_user


def require_payments_enabled():
    """
    PAYMENTS_ENABLED=false면 전면 차단.
    예외: 관리자 계정은 통과(운영에서 내부 테스트용).
    """
    if current_app.config.get("PAYMENTS_ENABLED"):
        return

    user = get_current_user()
    if user and getattr(user, "is_admin", False):
        return

    abort(403, description="Payments are disabled")
