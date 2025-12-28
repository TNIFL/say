from flask import jsonify, Blueprint

from auth.entitlements import get_current_user, has_active_subscription
from auth.guards import outputs_for_tier, resolve_tier
from core.extensions import csrf
from domain.policies import FEATURES_BY_TIER

api_auth_status_bp = Blueprint("api_auth_status", __name__)

# 크롬 확장 팝업에서 사용
@csrf.exempt
@api_auth_status_bp.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    u = get_current_user()
    if not u:
        return jsonify({"logged_in": False, "tier": "guest"}), 200
    tier = resolve_tier()
    return jsonify({
        "logged_in": True,
        "tier": tier,
        "user_id": u.user_id,
        "email": u.email,
        "email_verified": bool(u.email_verified),
        "features": list(FEATURES_BY_TIER.get(tier, set())),
        "n_outputs": outputs_for_tier()
    }), 200