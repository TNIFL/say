# routes/rewrite.py
from flask import Blueprint, request, jsonify, g, render_template, session
from auth.guards import require_feature, enforce_quota, outputs_for_tier, resolve_tier
from domain.schema import polish_input_schema
from domain.models import User
from security.security import require_safe_input

import os

from services.ai.output_postprocess import _ensure_exact_count
from services.ai.router import _get_ai_outputs

mainpage_bp = Blueprint("rewrite", __name__)


@mainpage_bp.route("/", methods=["GET", "POST"])
@require_safe_input(polish_input_schema, form=True, for_llm_fields=["input_text"])
@require_feature("rewrite.single")  # 비로그인: 기능 허용 검증
def polish():
    """
    메인 페이지 — 문장 다듬기 기능
    """
    input_text = ""
    output_text = ""
    outputs = []
    selected_categories = []
    selected_tones = []
    honorific_checked = False
    opener_checked = False
    emoji_checked = False
    provider_current = os.getenv("PROVIDER_DEFAULT")

    # 로그인 사용자 직업 컨텍스트 (없으면 빈 문자열)
    sess = session.get("user") or {}
    uid = sess.get("user_id")

    user = User.query.filter_by(user_id=uid).first() if uid else None
    user_job = (user.user_job or "") if user else ""
    user_job_detail = (user.user_job_detail or "") if user else ""
    print("polish 진입")
    if g.safe_input:
        data = g.safe_input
        input_text = (data.get("input_text") or "").strip()
        selected_categories = (
                data.get("selected_categories") or data.get("categories") or []
        )
        selected_tones = data.get("selected_tones") or data.get("tones") or []
        honorific_checked = bool(data.get("honorific_checked") or data.get("honorific"))
        opener_checked = bool(data.get("opener_checked") or data.get("opener"))
        emoji_checked = bool(data.get("emoji_checked") or data.get("emoji"))
        provider_current = (data.get("provider") or os.getenv("PROVIDER_DEFAULT")).lower()

        if provider_current not in ("openai", "gemini", "claude"):
            provider_current = os.getenv("PROVIDER_DEFAULT")

        if input_text:
            print(input_text)
            n_outputs = outputs_for_tier()
            outputs = _get_ai_outputs(
                provider=provider_current,
                input_text=input_text,
                selected_categories=selected_categories,
                selected_tones=selected_tones,
                honorific_checked=honorific_checked,
                opener_checked=opener_checked,
                emoji_checked=emoji_checked,
                n_outputs=n_outputs,
                user_job=user_job,
                user_job_detail=user_job_detail,
            )

    outputs = _ensure_exact_count(outputs, outputs_for_tier())
    output_text = outputs[0] if outputs else ""
    print(resolve_tier())
    return render_template(
        "mainpage.html",
        input_text=input_text,
        output_text=output_text or "",
        outputs=outputs,
        selected_categories=selected_categories,
        selected_tones=selected_tones,
        honorific_checked=honorific_checked,
        opener_checked=opener_checked,
        emoji_checked=emoji_checked,
        provider_current=provider_current,
        is_pro=(resolve_tier() == "pro"),
    )

@mainpage_bp.post("/api/rewrite/single")
@require_feature("rewrite.single")
@enforce_quota("rewrite")
def rewrite_single():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty_text"}), 400
    # === 실제 리라이트 로직 자리 ===
    print("rewirte_single 에러")
    output = f"[single] refined: {text}"
    return jsonify({"ok": True, "output": output})

@mainpage_bp.post("/api/rewrite/multi")
@require_feature("rewrite.multi")
@enforce_quota("rewrite")
def rewrite_multi():
    print("rewrite_multi 진입")
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"error": "empty_items"}), 400
    print("rewrite_multi 에러")
    outputs = [f"[multi] refined: {str(x).strip()}" for x in items[:10]]  # 데모
    return jsonify({"ok": True, "outputs": outputs})

@mainpage_bp.post("/api/preview/compare3")
@require_feature("preview.compare3")
@enforce_quota("preview")
def preview_compare3():
    print("preview_compare3 진입")
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty_text"}), 400
    candidates = [
        f"[c1] {text} (정중)",
        f"[c2] {text} (캐주얼)",
        f"[c3] {text} (비즈니스)"
    ]
    return jsonify({"ok": True, "candidates": candidates})
