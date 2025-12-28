from functools import wraps

from flask import render_template, jsonify, request, Blueprint, abort, g, redirect, url_for

from core.http_utils import nocache
from datetime import datetime, timedelta, timezone
from domain.models import Feedback, db
from domain.schema import admin_visits_query_schema, admin_data_query_schema
from security.security import _safe_args
from utils.time_utils import _utcnow, KST
from sqlalchemy import func, and_

# ===== 관리자 GET 쿼리 검증 헬퍼 =====
import json
from jsonschema import validate as _jsonschema_validate, ValidationError as _JsErr

admin_bp = Blueprint("admin", __name__)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not g.get("is_admin", False):
            return abort(403)
        return view_func(*args, **kwargs)

    return wrapper

# ------ 관리자 대시보드 페이지/데이터 ------
@admin_bp.route("/admin/analytics", methods=["GET"])
@admin_required
def admin_analytics_page():
    return render_template("admin_analytics.html")


@admin_bp.route("/admin/usage", methods=["GET"])
@admin_required
def admin_usage_page():
    return render_template("admin_usage.html")


@admin_bp.route("/admin/feedback", methods=["GET"])
@admin_required
@nocache
def admin_feedback_page():
    return render_template("admin_feedback.html")


@admin_bp.route("/admin/feedback/<int:fid>/resolve", methods=["POST"])
@admin_required
def admin_feedback_resolve(fid):
    fb = Feedback.query.get_or_404(fid)
    fb.resolved = not fb.resolved
    db.session.commit()
    return jsonify({"ok": True, "resolved": fb.resolved})


@admin_bp.route("/admin/feedback/data", methods=["GET"])
@admin_required
@nocache
def admin_feedback_data():
    from sqlalchemy import or_

    category = (request.args.get("category") or "").strip()
    s_resolved = (request.args.get("resolved") or "").strip().lower()
    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        size = int(request.args.get("page_size", 20))
        size = max(1, min(100, size))
    except Exception:
        size = 20

    conds = []
    if category:
        conds.append(Feedback.category == category)
    if q:
        like = f"%{q}%"
        conds.append(or_(
            Feedback.email.ilike(like),
            Feedback.user_id.ilike(like),
            Feedback.message.ilike(like),
        ))
    # resolved 필터는 admin_reply 존재 여부로 판단 (모델에 별도 필드 없어도 동작)
    if s_resolved in ("true", "false"):
        want = (s_resolved == "true")
        if want:
            conds.append(Feedback.admin_reply.isnot(None))
        else:
            conds.append(Feedback.admin_reply.is_(None))

    base = Feedback.query
    if conds:
        from sqlalchemy import and_
        base = base.filter(and_(*conds))

    total = base.count()
    rows = (
        base.order_by(Feedback.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    def row_json(r: Feedback):
        return {
            "id": r.id,
            "created_at": r.created_at.astimezone().strftime("%Y-%m-%d %H:%M") if r.created_at else None,
            "category": r.category,
            "email": r.email,
            "user_id": r.user_id,
            "page": r.page,
            "message": r.message,
            "resolved": bool(r.admin_reply),
            "admin_reply": r.admin_reply,
            "replied_at": r.replied_at.astimezone().strftime("%Y-%m-%d %H:%M") if r.replied_at else None,
        }

    return jsonify({
        "items": [row_json(r) for r in rows],
        "page": page,
        "page_size": size,
        "total": total,
        "page_count": (total + size - 1) // size
    }), 200


@admin_bp.route("/admin/feedback/<int:fid>", methods=["GET"])
@admin_required
@nocache
def admin_feedback_detail(fid):
    row = Feedback.query.get(fid)
    if not row:
        return render_template("admin_feedback_detail.html", error="존재하지 않는 항목입니다."), 404
    return render_template("admin_feedback_detail.html", item=row)


@admin_bp.route("/admin/feedback/<int:fid>/reply", methods=["POST"])
@admin_required
def admin_feedback_reply(fid):
    print(fid)
    row = Feedback.query.get(fid)
    if not row:
        abort(404)

    reply = (request.form.get("admin_reply") or "").strip()
    row.admin_reply = reply if reply else None
    row.replied_at = _utcnow() if reply else None

    db.session.add(row)
    db.session.commit()

    return redirect(url_for("admin.admin_feedback_detail", fid=fid) + "?saved=1")



def safe_args(schema, *, source=None):
    q = {
        k: (
            request.args.getlist(k)
            if len(request.args.getlist(k)) > 1
            else request.args.get(k)
        )
        for k in request.args.keys()
    }
    for k, v in list(q.items()):
        if isinstance(v, str) and v.strip() == "":
            q[k] = None
    try:
        _jsonschema_validate(instance=q, schema=schema)
    except _JsErr as e:
        abort(400, description=f"유효하지 않은 쿼리: {e.message}")
    return q


def _truthy(v):
    return str(v).lower() in {"on", "true", "1", "yes"}

