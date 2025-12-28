# -------------------- 라우트 --------------------
from auth.guards import require_feature, outputs_for_tier, resolve_tier
from auth.quota import enforce_quota
from core.extensions import csrf, limiter

from flask import Blueprint, jsonify, g, session

from core.hooks import origin_allowed
from core.http_utils import _sleep_floor
from domain.schema import api_polish_schema
from domain.models import User
from security.security import require_safe_input

import time, os

from services.ai.output_postprocess import _ensure_exact_count
from services.ai.router import _get_ai_outputs

api_polish_bp = Blueprint("api_polish", __name__)

# JSON API — CSRF 제외 + Origin 화이트리스트 검사 + 레이트리밋
@csrf.exempt
@limiter.limit("60/minute")
@api_polish_bp.route("/api/polish", methods=["POST"])
@require_safe_input(api_polish_schema, form=False, for_llm_fields=["input_text"])
@require_feature("rewrite.single")  # 기능 권한
@enforce_quota("rewrite")  # scope=rewrite
def api_polish():
    print("[POLISH] uid=", (session.get("user") or {}).get("user_id"), "tier=", resolve_tier(), "scope=rewrite")

    start_t = time.perf_counter()
    if not origin_allowed():
        _sleep_floor(start_t)
        return jsonify({"error": "forbidden_origin"}), 403

    data = g.safe_input
    input_text = (data.get("input_text") or "").strip()
    selected_categories = data.get("selected_categories", [])
    selected_tones = data.get("selected_tones", [])
    honorific_checked = bool(data.get("honorific_checked"))
    opener_checked = bool(data.get("opener_checked"))
    emoji_checked = bool(data.get("emoji_checked"))
    provider = (data.get("provider") or os.getenv("PROVIDER_DEFAULT")).lower()
    if not input_text:
        _sleep_floor(start_t)
        return jsonify({"error": "empty_input", "message": "사용자 입력이 없습니다."}), 400
    if len(input_text) > 4000:
        _sleep_floor(start_t)
        return jsonify({"error": "too_long"}), 413
    if provider not in ("openai", "gemini", "claude"):
        provider = os.getenv("PROVIDER_DEFAULT")

    n_outputs = outputs_for_tier()
    # 사용자의 직업, 직업 설명을 가져와야 하니 user 를 가져온다
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    user = User.query.filter_by(user_id=uid).first() if uid else None
    user_job = user.user_job if user else ""
    user_job_detail = user.user_job_detail if user else ""

    outputs = _get_ai_outputs(
        provider,
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
        n_outputs,
        user_job=user_job,
        user_job_detail=user_job_detail,
    )

    outputs = _ensure_exact_count(outputs, n_outputs)
    resp = jsonify({"outputs": outputs, "output_text": outputs[0]}), 200
    _sleep_floor(start_t)
    return resp

