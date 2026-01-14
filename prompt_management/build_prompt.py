# build_prompt.py
from __future__ import annotations

from prompt_management import category_templates


def _normalize_lang(lang: str | None) -> str:
    """
    Normalize language codes to a small set we support in prompt templates.
    Examples: "en", "en-US", "EN_us" -> "en"
              "ko", "ko-KR" -> "ko"
    """
    raw = (lang or "ko").strip().lower()
    if raw.startswith("en"):
        return "en"
    return "ko"


def _get_system_prompt(lang: str) -> str:
    """
    Prefer language-specific system prompt if available.
    Falls back to legacy SYSTEM_PROMPT_BASE for backward compatibility.
    """
    by_lang = getattr(category_templates, "SYSTEM_PROMPT_BASE_BY_LANG", None)
    if isinstance(by_lang, dict):
        return by_lang.get(lang) or by_lang.get("ko") or by_lang.get("en") or ""
    return getattr(category_templates, "SYSTEM_PROMPT_BASE", "")


def _get_category_guide_map(lang: str):
    """
    Prefer language-specific category guide map if present.
    Otherwise, use legacy CATEGORY_GUIDE_MAP.
    """
    by_lang = getattr(category_templates, "CATEGORY_GUIDE_MAP_BY_LANG", None)
    if isinstance(by_lang, dict):
        m = by_lang.get(lang)
        if isinstance(m, dict) and m:
            return m
    return getattr(category_templates, "CATEGORY_GUIDE_MAP", {})


def build_prompt(
    input_text,
    selected_categories,
    selected_tones,
    honorific_checked,
    opener_checked,
    emoji_checked,
    user_job="",
    user_job_detail="",
    context_source="",
    context_label="",
    target_lang: str = "ko",
):
    """
    Builds (system_prompt, user_prompt) for Claude.

    target_lang:
      - "ko" or "en" (also accepts "en-US", "ko-KR" etc.)
      - Ensures all prompt scaffolding (labels/instructions) matches the selected language.
    """
    lang = _normalize_lang(target_lang)

    system_prompt = _get_system_prompt(lang)
    category_guide_map = _get_category_guide_map(lang)

    def pick_category(sel):
        if isinstance(sel, list):
            for c in sel:
                if c in category_guide_map:
                    return c
            return "general"
        return sel if sel in category_guide_map else "general"

    category_key = pick_category(selected_categories)
    user_guide = category_guide_map.get(category_key, category_guide_map.get("general", ""))

    tones_str = (
        ", ".join(selected_tones)
        if isinstance(selected_tones, list)
        else (selected_tones or "")
    ).strip()

    user_job = (user_job or "").strip()
    user_job_detail = (user_job_detail or "").strip()

    # Language-specific scaffolding
    if lang == "en":
        options_block = f"""
[Context]
- Category: {category_key}
- Tone: {tones_str or "Default"}
- Keep honorifics/politeness: {"Yes" if honorific_checked else "No"}
- Add softener/greeting: {"Yes" if opener_checked else "No"}
- Emojis allowed: {"Yes" if emoji_checked else "No"}
- Job role: {user_job}
- Job description: {user_job_detail}
- Writing environment (platform): {context_label or "General site"} ({context_source or "generic"})
""".strip()

        original_label = "# Original (to rewrite)"
        output_only = "[Output only the result]"
    else:
        options_block = f"""
[컨텍스트]
- 카테고리: {category_key}
- 어조: {tones_str or "기본"}
- 존댓말 유지: {"예" if honorific_checked else "아니오"}
- 완충문/인사 추가: {"예" if opener_checked else "아니오"}
- 이모지 허용: {"예" if emoji_checked else "아니오"}
- 직업: {user_job}
- 직업 설명: {user_job_detail}
- 작성 환경(플랫폼): {context_label or "일반 사이트"} ({context_source or "generic"})
""".strip()

        original_label = "# 원문 (수정 대상)"
        output_only = "[결과만 출력]"

    final_user_prompt = f"""
{options_block}

{user_guide}

{original_label}
{input_text}

{output_only}
""".strip()

    return system_prompt, final_user_prompt
