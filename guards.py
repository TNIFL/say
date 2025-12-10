# guards.py
from functools import wraps
from flask import request, jsonify, g, make_response
from sqlalchemy import and_
from extensions import db
from policies import FEATURES_BY_TIER, LIMITS
from auth import get_current_user, has_active_subscription
from models import Usage, AnonymousUsage, db
from utils.time_windows import utcnow, day_window, month_window
from utils.anon import ensure_anon_cookie

def resolve_tier():
    user = get_current_user()
    if not user:
        return "anon"
    return "pro" if has_active_subscription(user) else "free"

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

def enforce_quota(scope: str):
    """
    사용량 게이트(성공시에만 +1)
    - anon: daily
    - free/pro: monthly
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tier = resolve_tier()
            now = utcnow()

            if tier == "anon":
                day_start, _ = day_window(now)
                anon_key, _ = ensure_anon_cookie(response=None)

                # 잠금 + 조회/생성
                with db.session.begin():
                    row = (AnonymousUsage.query
                           .filter(and_(AnonymousUsage.anon_key == anon_key,
                                        AnonymousUsage.window_start == day_start))
                           .with_for_update(nowait=False)
                           .first())
                    if not row:
                        row = AnonymousUsage(anon_key=anon_key, ip=request.remote_addr,
                                             window_start=day_start, count=0)
                        db.session.add(row)
                        db.session.flush()

                    limit = LIMITS["anon"]["daily"]
                    if row.count >= limit:
                        return jsonify({"error": "daily_limit_reached", "limit": limit}), 429

                resp = f(*args, **kwargs)

                # 성공 시 증가
                with db.session.begin():
                    row = (AnonymousUsage.query
                           .filter(and_(AnonymousUsage.anon_key == anon_key,
                                        AnonymousUsage.window_start == day_start))
                           .with_for_update(nowait=False)
                           .one())
                    row.count += 1

                # 쿠키 없었던 경우 세팅
                if not request.cookies.get("aid"):
                    if not hasattr(resp, "set_cookie"):
                        resp = make_response(resp)
                    _, resp = ensure_anon_cookie(response=resp)
                return resp

            else:
                month_start, _ = month_window(now)
                user = get_current_user()
                if not user:
                    return jsonify({"error": "auth_required"}), 401

                tier_key = "pro" if tier == "pro" else "free"

                with db.session.begin():
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

                with db.session.begin():
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
