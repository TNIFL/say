from flask import render_template, Blueprint, current_app

from generator import claude_prompt_generator
from services.ai.claude_service import _as_text_from_claude_result
from utils.retry import _retry

import os

summarize_bp = Blueprint("summarize", __name__)

@summarize_bp.route("/summarize")
def summarize_page():
    return render_template("summarize.html")

def _build_summarize_prompt_korean(text: str):
    return (
        "아래 한국어 원문을 핵심만 간결하게 요약해 주세요.\n"
        "- 불필요한 수식/감탄사/사족 금지\n"
        "- 핵심 사실, 결론, 근거 위주\n"
        "- 350자 이내\n"
        "- 출력 형식: (1) 불릿 3~5개 또는 (2) 문장 2~3개 중 하나만\n"
        "- 이모지 사용 금지\n\n"
        f"[원문]\n{text.strip()}\n\n"
        "[출력]"
    )

# ---- 입력 검증 스키마 (폼/JSON) ----
summarize_form_schema = {
    "type": "object",
    "properties": {
        "input_text": {"type": "string", "minLength": 1, "maxLength": 8000},
    },
    "required": ["input_text"],
    "additionalProperties": True,
}

# JS는 { text: "..." }로 보냄. 두 키 다 허용.
api_summarize_schema = {
    "type": "object",
    "properties": {
        "input_text": {"type": "string", "minLength": 1, "maxLength": 8000},
        "text": {"type": "string", "minLength": 1, "maxLength": 8000},
        "provider": {"type": "string", "enum": ["claude", "openai", "gemini"]},
    },
    "oneOf": [
        {"required": ["input_text"]},
        {"required": ["text"]},
    ],
    "additionalProperties": True,
}

def _call_provider_summarize(text: str, provider: str = None) -> str:
    PROVIDER_DEFAULT = os.getenv("PROVIDER_DEFAULT")
    provider = (provider or PROVIDER_DEFAULT).lower()
    prompt = _build_summarize_prompt_korean(text)
    out_text = ""

    if provider == "claude":
        try:
            def _do():
                return claude_prompt_generator.call_claude(
                    "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다.",
                    prompt,
                )

            result = _retry(_do)
            out_text = _as_text_from_claude_result(result).strip()
        except Exception:
            out_text = ""
    elif provider == "openai":
        try:
            if not hasattr(current_app, "openai_client") or current_app.openai_client is None:
                raise RuntimeError("OpenAI client not configured")
            completion = current_app.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                top_p=0.9,
                max_tokens=400,
                n=1,
            )
            out_text = (completion.choices[0].message.content or "").strip()
        except Exception:
            out_text = ""
    else:
        # 기본은 Claude
        try:
            def _do():
                return claude_prompt_generator.call_claude(
                    "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다.",
                    prompt,
                )

            result = _retry(_do)
            out_text = _as_text_from_claude_result(result).strip()
        except Exception:
            out_text = ""

    return out_text[:1200].strip()