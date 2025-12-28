# guards.py
from functools import wraps
from flask import request, jsonify, make_response, g
from sqlalchemy import and_

from cookie.cookie import ensure_guest_cookie
from domain.policies import FEATURES_BY_TIER, LIMITS
from auth.entitlements import get_current_user, has_active_subscription
from domain.models import Usage, GuestUsage, db
from utils.time_utils import utcnow, day_window, month_window
from contextlib import contextmanager

def resolve_tier():
    user = get_current_user()
    if not user:
        return "guest"
    if getattr(user, "is_admin", False):
        return "pro"
    return "pro" if has_active_subscription(user) else "free"



def outputs_for_tier():
    tier = resolve_tier()
    return 3 if tier == "pro" else 1


def feature_allowed(tier: str, feature_key: str) -> bool:
    allowed = FEATURES_BY_TIER.get(tier, set())
    return "*" in allowed or feature_key in allowed


def require_feature(feature_key: str):
    """기능 권한 게이트: 허용 안 되면 403"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tier = resolve_tier()
            if not feature_allowed(tier, feature_key):
                return jsonify({"error": "feature_not_allowed", "feature": feature_key, "tier": tier}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

@contextmanager
def begin_tx():
    s = db.session()
    if s.in_transaction():
        with s.begin_nested():
            yield
    else:
        with s.begin():
            yield

def enforce_quota(scope: str):
    """
    사용량 게이트(성공시에만 +1)
    - guest: daily
    - free/pro: monthly
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tier = resolve_tier()
            now = utcnow()

            if tier == "guest":
                # guest 사용자
                print("guest 사용자 진입")
                day_start, _ = day_window(now)
                guest_key, _ = ensure_guest_cookie()

                # 잠금 + 조회/생성
                with begin_tx():
                    row = (GuestUsage.query
                           .filter(and_(GuestUsage.guest_key == guest_key,
                                        GuestUsage.window_start == day_start))
                           .with_for_update(nowait=False)
                           .first())
                    if not row:
                        row = GuestUsage(guest_key=guest_key, ip=request.remote_addr,
                                             window_start=day_start, count=0)
                        db.session.add(row)
                        db.session.flush()

                    limit = LIMITS["guest"]["daily"]
                    if row.count >= limit:
                        return jsonify({"error": "daily_limit_reached", "limit": limit}), 429

                resp = f(*args, **kwargs)

                # 성공 시 증가
                with begin_tx():
                    row = (GuestUsage.query
                           .filter(and_(GuestUsage.guest_key == guest_key,
                                        GuestUsage.window_start == day_start))
                           .with_for_update(nowait=False)
                           .one())
                    row.count += 1

                # 쿠키 없었던 경우 세팅
                if not request.cookies.get("aid"):
                    if not hasattr(resp, "set_cookie"):
                        resp = make_response(resp)
                    _, resp = ensure_guest_cookie(response=resp)
                return resp

            else:
                # free, pro 사용자
                month_start, _ = month_window(now)
                user = get_current_user()
                if not user:
                    return jsonify({"error": "auth_required"}), 401

                tier_key = "pro" if tier == "pro" else "free"

                with begin_tx():
                    row = (Usage.query
                           .filter(and_(Usage.user_id == user.user_id,
                                        Usage.tier == tier_key,
                                        Usage.window_start == month_start))
                           .with_for_update(nowait=False)
                           .first())
                    if not row:
                        row = Usage(user_id=user.user_id, tier=tier_key,
                                    window_start=month_start, count=0)
                        db.session.add(row)
                        db.session.flush()

                    limit = LIMITS[tier]["monthly"]
                    if row.count >= limit:
                        return jsonify({"error": "monthly_limit_reached", "limit": limit}), 429

                resp = f(*args, **kwargs)

                with begin_tx():
                    row = (Usage.query
                           .filter(and_(Usage.user_id == user.user_id,
                                        Usage.tier == tier_key,
                                        Usage.window_start == month_start))
                           .with_for_update(nowait=False)
                           .one())
                    row.count += 1
                return resp
        return wrapper
    return decorator
