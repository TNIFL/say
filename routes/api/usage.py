from flask import session, Blueprint, make_response, jsonify, request

from cookie.cookie import set_guest_cookie, ensure_guest_cookie
from core.extensions import csrf
from core.hooks import origin_allowed
from core.http_utils import nocache
from domain.models import Subscription, db, Usage, GuestUsage as GuestUsage
from domain.policies import LIMITS
from domain.schema import USAGE_SCOPES
from utils.time_utils import _utcnow, _month_window, _day_window

from sqlalchemy import func
api_usage_bp = Blueprint("api_usage", __name__)


@csrf.exempt
@nocache
@api_usage_bp.route("/api/usage", methods=["GET"])
def api_usage_status():
    """
      scope-aware 사용량 조회
    - 로그인: 월간 window + scope
    - 게스트: 일간 window + scope
    """
    print("[USAGE][HEADERS] Origin=", request.headers.get("Origin"))
    print("[USAGE][HEADERS] Host=", request.headers.get("Host"), "XFH=", request.headers.get("X-Forwarded-Host"),
          "XFP=", request.headers.get("X-Forwarded-Proto"))

    def _json_resp(payload, set_aid=None, status=200):
        resp = make_response(jsonify(payload), status)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        if set_aid is not None:
            set_guest_cookie(resp, set_aid)
        return resp

    try:
        if "_origin_allowed" in globals() and not origin_allowed():
            return _json_resp({"error": "forbidden_origin"}, status=403)
    except Exception:
        pass

    #  scope 파라미터 (기본 rewrite)
    scope = (request.args.get("scope") or "rewrite").strip().lower()
    if scope not in USAGE_SCOPES:
        scope = "rewrite"

    # ----- 로그인 사용자 -----
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if uid:
        try:
            sub = Subscription.query.filter_by(user_id=uid, status="active").first()
            tier = "pro" if sub else "free"
            limit = LIMITS["pro"]["monthly"] if tier == "pro" else LIMITS["free"]["monthly"]

            #  Usage.window_start는 Date — 범위 조회 사용
            now = _utcnow()
            month_start, month_end = _month_window(now)

            used = (
                db.session.query(func.coalesce(func.sum(Usage.count), 0))
                .filter(
                    Usage.user_id == uid,
                    Usage.tier == tier,
                    Usage.scope == scope,  # scope 필터
                    Usage.window_start >= month_start,
                    Usage.window_start < month_end,
                )
                .scalar()
            )
            return _json_resp({"used": int(used or 0), "limit": int(limit), "tier": tier, "scope": scope})
        except Exception:
            return _json_resp({"used": 0, "limit": LIMITS["free"]["monthly"], "tier": "free", "scope": scope})

    # ----- 게스트 -----
    try:
        tier = "guest"
        limit = LIMITS["guest"]["daily"]
        aid, need_set = ensure_guest_cookie()

        now = _utcnow()
        day_start, day_end = _day_window(now)

        used = (
            db.session.query(func.coalesce(func.sum(GuestUsage.count), 0))
            .filter(
                GuestUsage.guest_key == aid,
                GuestUsage.scope == scope,  # scope 필터
                GuestUsage.window_start >= day_start,
                GuestUsage.window_start < day_end,
            )
            .scalar()
        )

        return _json_resp(
            {"used": int(used or 0), "limit": int(limit), "tier": tier, "scope": scope},
            set_aid=aid if need_set else None
        )
    except Exception:
        return _json_resp({"used": 0, "limit": LIMITS["guest"]["daily"], "tier": "guest", "scope": scope})
