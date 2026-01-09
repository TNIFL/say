# -------------------- 라우트 --------------------
import os
import time

from flask import Blueprint, jsonify, g, request

from auth.entitlements import get_current_user
from auth.guards import require_feature, outputs_for_tier, resolve_tier
from auth.quota import enforce_quota
from core.extensions import csrf, limiter
from core.http_utils import _sleep_floor
from domain.schema import api_polish_schema
from security.security import require_safe_input

from services.ai.output_postprocess import _ensure_exact_count
from services.ai.router import _get_ai_outputs

api_polish_bp = Blueprint("api_polish", __name__)


@csrf.exempt
@limiter.limit("60/minute")
@api_polish_bp.route("/api/polish", methods=["POST"])
@require_safe_input(api_polish_schema, form=False, for_llm_fields=["input_text"])
@require_feature("rewrite.single")   # 기능 권한
@enforce_quota("rewrite")            # scope=rewrite
def api_polish():
    """
    정책:
    - Origin 허용/차단은 전역 origin_guard에서만 처리 (라우트 내부 중복 제거)
    - 사용자 식별은 get_current_user() 단일 경로(토큰/세션 통합) 사용
    - 입력 검증 실패/업스트림 실패 시 명시적 에러 코드 반환
    """
    start_t = time.perf_counter()

    try:
        user = get_current_user()
        tier = resolve_tier()

        # safe_input은 require_safe_input 데코레이터가 g.safe_input에 넣어줌
        data = getattr(g, "safe_input", None) or {}

        input_text = (data.get("input_text") or "").strip()
        selected_categories = data.get("selected_categories") or []
        selected_tones = data.get("selected_tones") or []
        honorific_checked = bool(data.get("honorific_checked"))
        opener_checked = bool(data.get("opener_checked"))
        emoji_checked = bool(data.get("emoji_checked"))

        # provider 기본값 방어
        provider_default = (os.getenv("PROVIDER_DEFAULT") or "openai").lower()
        provider = (data.get("provider") or provider_default)
        provider = (provider.lower() if isinstance(provider, str) else provider_default)

        context_source = (data.get("context_source") or "").strip()
        context_label = (data.get("context_label") or "").strip()

        # (옵션) 로깅: 민감정보는 절대 찍지 말 것
        uid = getattr(user, "user_id", None) if user else None
        print("[POLISH] uid=", uid, "tier=", tier, "scope=rewrite", "provider=", provider)

        # 입력 검증
        if not input_text:
            _sleep_floor(start_t)
            return jsonify({"error": "empty_input", "message": "사용자 입력이 없습니다."}), 400

        # 문자 길이 기준(운영 정책). 필요하면 4000을 환경변수로 빼도 됨.
        if len(input_text) > 4000:
            _sleep_floor(start_t)
            return jsonify({"error": "too_long", "message": "입력 길이가 너무 깁니다."}), 413

        if provider not in ("openai", "gemini", "claude"):
            provider = provider_default

        # 출력 개수는 티어 기준
        n_outputs = outputs_for_tier()

        # 사용자 직업 정보(있으면 프롬프트 품질 개선)
        user_job = getattr(user, "user_job", "") if user else ""
        user_job_detail = getattr(user, "user_job_detail", "") if user else ""

        # AI 호출
        outputs = _get_ai_outputs(
            provider=provider,
            input_text=input_text,
            selected_categories=selected_categories,
            selected_tones=selected_tones,
            honorific_checked=honorific_checked,
            opener_checked=opener_checked,
            emoji_checked=emoji_checked,
            n_outputs=n_outputs,
            user_job=user_job,
            user_job_detail=user_job_detail,
            # context_source/context_label을 실제 프롬프트에 쓴다면 router쪽에 전달하도록 확장 가능
        )

        outputs = _ensure_exact_count(outputs, n_outputs)
        _sleep_floor(start_t)
        return jsonify({"outputs": outputs, "output_text": outputs[0]}), 200

    except Exception as e:
        print("[POLISH][ERROR]", type(e).__name__, str(e))
        _sleep_floor(start_t)
        return jsonify({"error": "polish_failed", "message": "순화 처리 중 오류가 발생했습니다."}), 500
