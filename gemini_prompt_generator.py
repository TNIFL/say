# gemini.py
import os
from typing import Tuple, Dict, Any
from google import genai

from google.genai.types import GenerationConfig


def _extract_usage(resp) -> Dict[str, Any]:
    prompt = completion = total = None
    usage = getattr(resp, "usage", None)
    if usage:
        prompt = getattr(usage, "prompt_token_count", None)
        completion = getattr(usage, "candidates_token_count", None) or getattr(usage, "output_token_count", None)
        total = getattr(usage, "total_token_count", None)
        if hasattr(usage, "get"):
            prompt = prompt or usage.get("prompt_token_count")
            completion = completion or usage.get("candidates_token_count") or usage.get("output_token_count")
            total = total or usage.get("total_token_count")
    if (prompt is None or completion is None or total is None) and hasattr(resp, "to_dict"):
        try:
            d = resp.to_dict()
            u = d.get("usage", {}) if isinstance(d, dict) else {}
            prompt = prompt or u.get("prompt_token_count")
            completion = completion or u.get("candidates_token_count") or u.get("output_token_count")
            total = total or u.get("total_token_count")
        except Exception:
            pass
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def call_gemini(system_prompt, final_user_prompt) -> Tuple[str, Dict[str, Any]]:
    """Google Gemini 모델로 문장 다듬기 (DB 토큰 로깅 호환 반환)"""
    print("[Gemini] gemini_generate 호출됨")

    # 0) 환경변수/모델 점검
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Gemini][ERROR] GEMINI_API_KEY 환경변수가 비어 있음")
        return "", {"provider": "gemini", "model": None, "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

    # 사용자가 지정한 모델이 있으면 우선 사용, 없으면 안전한 기본값으로
    # pro 모델이 권한/리전 문제로 자주 실패하니 기본은 flash로 둠

    model = "gemini-2.5-pro"
    client = genai.Client(api_key=api_key)

    # 1차 시도: 지정(또는 기본) 모델
    print("1st 시도")
    try:
        print(f"[Gemini] model={model}")
        config = GenerationConfig(
            # system_instruction=system_prompt,
            temperature=0.7  # 다른 설정값들은 유지
        )

        # 2. generate_content 메서드에 system_instruction을 직접 전달
        resp = client.models.generate_content(
            system_instruction=system_prompt,  # 👈 여기에 system_prompt 문자열을 넣습니다.
            model=model,
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": final_user_prompt}]
                }
            ],
            config=config  # 👈 config 객체는 다른 설정값만 전달
        )
        text = (getattr(resp, "text", "") or "").strip()
        print("[Gemini] 1st call OK")
        usage = _extract_usage(resp)
        return text, {
            "provider": "gemini",
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    except Exception as e:
        # 모델 이름 오류 / 권한 / 리전 문제 가능성 → 안전 모델로 1회 폴백
        print("[Gemini][ERROR] 1st call failed:", repr(e))

    # 2차 폴백: 가장 호환성 좋은 플래시 계열
    fallback_model = "gemini-2.0-flash"
    if model != fallback_model:
        try:
            print(f"[Gemini] fallback model={fallback_model}")
            resp = client.models.generate_content(
                contents=final_user_prompt,
                system_instruction=system_prompt
            )
            text = (getattr(resp, "text", "") or "").strip()
            print("[Gemini] fallback OK, text length:", len(text))
            usage = _extract_usage(resp)
            return text, {
                "provider": "gemini",
                "model": fallback_model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        except Exception as e2:
            print("[Gemini][ERROR] fallback failed:", repr(e2))

    # 최종 실패
    return "", {
        "provider": "gemini",
        "model": model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }
