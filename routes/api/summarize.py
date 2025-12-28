from flask import jsonify, request, session, Blueprint, g

from auth.guards import require_feature, enforce_quota
from core.extensions import csrf, limiter
import json, os

from core.hooks import origin_allowed
from domain.models import RewriteLog, db, User
from routes.web.summerize import _call_provider_summarize

api_summarize_bp = Blueprint("api_summarize", __name__)

@csrf.exempt
@limiter.limit("60/minute")
@require_feature("summarize")
@enforce_quota("summarize")
@api_summarize_bp.route("/api/summarize", methods=["POST"])
def api_summarize():
    # 1) Origin 검사(있다면)
    if not origin_allowed():
        return jsonify({"error": "forbidden_origin"}), 403

    # 2) 안전 입력 가져오기: g.safe_input 우선, 없으면 직접 JSON 파싱 (최후의 보루)
    data = getattr(g, "safe_input", None)
    data = getattr(g, "safe_input", None)
    if data is None:
        data = request.get_json(silent=True)
        if data is None:
            try:
                data = json.loads(request.data or b"{}")
            except Exception:
                return jsonify({"error": "json_required",
                                "hint": "send JSON with Content-Type: application/json"}), 400

    input_text = (data.get("input_text") or data.get("text") or "").strip()
    provider = (data.get("provider") or os.getenv("PROVIDER_DEFAULT")).lower()

    if not input_text:
        return jsonify({"error": "empty_input"}), 400

    # 4) 생성 호출
    output = _call_provider_summarize(input_text, provider)

    # 5) 로그 저장 (예외 무시)
    try:
        sess = session.get("user") or {}
        uid = sess.get("user_id")
        log = RewriteLog(
            user_pk=None,
            user_id=uid,
            input_text=input_text,
            output_text=output or "(빈 응답)",
            categories=["summary"],
            tones=["concise", "clearly"],
            honorific=False, opener=False, emoji=False,
            model_name=f"summarize:{provider}",
            request_ip=request.remote_addr,
        )
        if uid:
            u = User.query.filter_by(user_id=uid).first()
            if u: log.user_pk = u.id
        db.session.add(log);
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({
        "output": output,
        "outputs": [output] if output else [],
        "output_text": output,
    }), 200
