from flask import jsonify, Blueprint, request

from auth.entitlements import get_current_user
from auth.guards import resolve_tier
from core.extensions import csrf
from domain.models import RewriteLog

api_history_bp = Blueprint("api_history", __name__)

# 크롬 확장 팝업에서 사용
@csrf.exempt
@api_history_bp.route("/api/history", methods=["GET"])
def api_history():
    user = get_current_user()
    if not user:
        return jsonify({"error": "login_required"}), 401
    # Pro만 허용(요구사항 반영)
    if resolve_tier() != "pro":
        return jsonify({"error": "pro_required"}), 403
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
    except Exception:
        limit = 20
    rows = (
        RewriteLog.query.filter_by(user_id=user.user_id)
        .order_by(RewriteLog.created_at.desc())
        .limit(limit).all()
    )
    items = [{
        "id": r.id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "input_text": r.input_text,
        "output_text": r.output_text,
        "categories": r.categories,
        "tones": r.tones,
        "model": r.model_name
    } for r in rows]
    return jsonify({"items": items}), 200