import os
from dotenv import load_dotenv
from typing import Tuple, Dict, Any

# 환경변수 로드
load_dotenv()

import anthropic
#빠른 모델
#claude-haiku-4-5-20251001
#깊게 생각하는 모델
#claude-sonnet-4-5-20250929

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



def call_claude(system_prompt, final_user_prompt) -> Tuple[str, Dict[str, Any]]:
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    if not client:
        print("[Claude][Error] ANTIHROPIC_API_KEY is empty")
        return "", {"provider": "claude", "model": None}

    model = "claude-sonnet-4-5-20250929"  # 최신 안정 모델로 변경 권장

    usage_data = None
    error_message = ""  # output_text에 저장할 에러 메시지 초기화
    try:
        print(f"[Claude] model={model}")
        # 2. messages.create의 인자 위치 수정 (max_tokens를 최상위로)
        message = client.messages.create(
            model=model,
            max_tokens=1024,  # <-- max_tokens을 최상위로 이동
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": final_user_prompt  # <-- 사용자 프롬프트는 'user' role로 전달
                }
            ]
        )
        # Claude 응답에서 텍스트 추출
        text = ""
        if message.content and message.content[0].type == 'text':
            text = (message.content[0].text or "").strip()

        # 4. usage 정보는 message 객체에서 직접 접근 후 추출
        usage_data = _extract_usage(message)

        print(f"[Claude] 1st call OK")
        print(text)
        return text, {
            "provider": "claude",
            "model": model,
            "prompt_tokens": usage_data.get("prompt_tokens"),
            "completion_tokens": usage_data.get("completion_tokens"),
            "total_tokens": usage_data.get("total_tokens")
        }
    except Exception as e:
        # 5. 에러 발생 시, 에러 메시지를 문자열로 저장
        error_message = str(e)
        print(f"[Claude][Error] 1st call failed: {error_message}")

    # 6. 실패 시, 오류 메시지와 초기화된 usage_data를 반환
    return error_message, {  # 텍스트 대신 오류 메시지를 output_text에 저장하도록 반환 (DB 에러 방지)
        "provider": "Claude",
        "model": model,
        "prompt_tokens": usage_data.get("prompt_tokens") if usage_data else None,
        "completion_tokens": usage_data.get("completion_tokens") if usage_data else None,
        "total_tokens": usage_data.get("total_tokens") if usage_data else None
    }