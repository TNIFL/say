from functools import wraps

from flask import request, jsonify, make_response
from sqlalchemy import and_

from auth.entitlements import get_current_user
from domain.models import db, Usage, GuestUsage as GuestUsage
from auth.guards import resolve_tier
from cookie.cookie import ensure_guest_cookie, set_guest_cookie
from domain.policies import LIMITS
from domain.schema import USAGE_SCOPES
from utils.time_utils import _utcnow, _day_window, _month_window


def enforce_quota(scope: str, methods=("POST",)):
    """
    사용량 게이트(성공시에만 +1)
    scope별로 별도 카운트/한도 적용
      - guest: daily (GuestUsage)
      - free/pro: monthly (Usage[Date])
    - methods: 해당 HTTP 메서드에만 실행 (기본 POST)
    """
    assert scope in USAGE_SCOPES, f"Unknown scope '{scope}'"

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if methods and request.method.upper() not in {m.upper() for m in methods}:
                return view(*args, **kwargs)

            tier = resolve_tier()
            now = _utcnow()

            if tier == "guest":
                guest_key, need_set = ensure_guest_cookie()
                day_start, _ = _day_window(now)

                from psycopg2._psycopg import IntegrityError
                try:
                    with db.session.begin_nested():
                        row = (
                            GuestUsage.query.filter(
                                and_(
                                    GuestUsage.guest_key == guest_key,
                                    GuestUsage.scope == scope,
                                    GuestUsage.window_start == day_start,
                                )
                            )
                            .with_for_update(nowait=False)
                            .first()
                        )

                        # 아직 row 없으면 새로 만들기 (여기서 race가 날 수 있음)
                        if not row:
                            row = GuestUsage(
                                guest_key=guest_key,
                                ip=request.remote_addr,
                                scope=scope,
                                window_start=day_start,
                                count=0,
                            )
                            db.session.add(row)
                            db.session.flush()

                        limit = LIMITS["guest"]["daily"]
                        if row.count >= limit:
                            resp = jsonify(
                                {
                                    "error": "daily_limit_reached",
                                    "limit": limit,
                                    "scope": scope,
                                }
                            )
                            resp.status_code = 429
                            if need_set:
                                resp = set_guest_cookie(make_response(resp), guest_key)
                            return resp

                except IntegrityError:
                    # 여기로 온다는 건, 방금 INSERT 경쟁에서 졌다는 뜻
                    db.session.rollback()
                    # 이미 다른 트랜잭션이 row를 만든 상태이므로 그냥 다시 가져오기만
                    with db.session.begin_nested():
                        row = (
                            GuestUsage.query.filter(
                                and_(
                                    GuestUsage.guest_key == guest_key,
                                    GuestUsage.scope == scope,
                                    GuestUsage.window_start == day_start,
                                )
                            )
                            .with_for_update(nowait=False)
                            .one()
                        )
                        limit = LIMITS["guest"]["daily"]
                        if row.count >= limit:
                            resp = jsonify(
                                {
                                    "error": "daily_limit_reached",
                                    "limit": limit,
                                    "scope": scope,
                                }
                            )
                            resp.status_code = 429
                            if need_set:
                                resp = set_guest_cookie(make_response(resp), guest_key)
                            return resp
                # 여기까지가 "limit 확인" 단계

                resp = view(*args, **kwargs)

                with db.session.begin_nested():
                    row = (
                        GuestUsage.query.filter(
                            and_(
                                GuestUsage.guest_key == guest_key,
                                GuestUsage.scope == scope,
                                GuestUsage.window_start == day_start,
                            )
                        )
                        .with_for_update(nowait=False)
                        .one()
                    )
                    row.count += 1
                db.session.commit()

                if need_set:
                    if not hasattr(resp, "set_cookie"):
                        resp = make_response(resp)
                    resp = set_guest_cookie(resp, guest_key)
                return resp

            # ===== free / pro (월간 집계 — Date window) =====
            month_start, _ = _month_window(now)
            user = get_current_user()
            if not user:
                return jsonify({"error": "auth_required"}), 401

            tier_key = "pro" if tier == "pro" else "free"

            with db.session.begin_nested():
                row = (
                    Usage.query.filter(
                        and_(
                            Usage.user_id == user.user_id,
                            Usage.tier == tier_key,
                            Usage.scope == scope,  # scope 포함
                            Usage.window_start == month_start,
                        )
                    )
                    .with_for_update(nowait=False)
                    .first()
                )
                if not row:
                    row = Usage(
                        user_id=user.user_id,
                        tier=tier_key,
                        scope=scope,  # 신규 row에 scope 저장
                        window_start=month_start,
                        count=0,
                    )
                    db.session.add(row)
                    db.session.flush()

                limit = LIMITS[tier]["monthly"]
                if row.count >= limit:
                    return jsonify({"error": "monthly_limit_reached", "limit": limit, "scope": scope}), 429

            resp = view(*args, **kwargs)

            with db.session.begin_nested():
                row = (
                    Usage.query.filter(
                        and_(
                            Usage.user_id == user.user_id,
                            Usage.tier == tier_key,
                            Usage.scope == scope,  # scope 포함
                            Usage.window_start == month_start,
                        )
                    )
                    .with_for_update(nowait=False)
                    .one()
                )
                row.count += 1
            db.session.commit()
            return resp

        return wrapper

    return decorator