from flask import request, Blueprint
from auth.entitlements import get_current_user, load_current_user
from auth.guards import resolve_tier
from core.extensions import csrf, limiter
from core.hooks import origin_allowed
from core.http_utils import _json_err, _json_ok
from domain.models import UserTemplate, db

api_user_templates_bp = Blueprint("api_user_templates", __name__)


@csrf.exempt
@limiter.limit("60/minute")
@api_user_templates_bp.route("/api/user_templates", methods=["GET", "POST"])
def api_user_templates():
    if not origin_allowed():
        return _json_err("forbidden_origin", status=403)

    user = get_current_user()
    if not user:
        return _json_err("login_required", status=401)
    tier = resolve_tier()
    print("[TIER] resolve_tier() =", tier, "user_id=", user.user_id, "email=", user.email)
    if resolve_tier() != "pro":
        return _json_err("pro_required", status=403)

    if request.method == "GET":
        rows = (
            UserTemplate.query.filter_by(user_id=user.user_id)
            .order_by(UserTemplate.updated_at.desc())
            .all()
        )
        return _json_ok({"items": [r.to_dict() for r in rows]})

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "").strip() or None
    tone = (data.get("tone") or "").strip() or None
    honorific = bool(data.get("honorific"))
    opener = bool(data.get("opener"))
    emoji = bool(data.get("emoji"))

    if not title:
        return _json_err("title_required", "제목은 필수입니다.", status=400)

    tpl = UserTemplate(
        user_id=user.user_id,
        title=title,
        category=category,
        tone=tone,
        honorific=honorific,
        opener=opener,
        emoji=emoji,
    )
    db.session.add(tpl)
    db.session.commit()
    return _json_ok({"item": tpl.to_dict()}, status=200)


@csrf.exempt
@limiter.limit("60/minute")
@api_user_templates_bp.route("/api/user_templates/<int:tpl_id>", methods=["DELETE"])
def api_user_templates_delete(tpl_id):
    if not origin_allowed():
        return _json_err("forbidden_origin", status=403)

    user = get_current_user()
    if not user:
        return _json_err("login_required", status=401)
    if resolve_tier() != "pro":
        return _json_err("pro_required", status=403)

    tpl = UserTemplate.query.filter_by(id=tpl_id, user_id=user.user_id).first()
    if not tpl:
        return _json_err("not_found", "해당 템플릿을 찾을 수 없습니다.", status=404)

    db.session.delete(tpl)
    db.session.commit()
    return _json_ok({"deleted_id": tpl_id}, status=200)
