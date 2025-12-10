# build_prompt.py
import category_templates as ct


def build_prompt(
    input_text,
    selected_categories,
    selected_tones,
    honorific_checked,
    opener_checked,
    emoji_checked
):
    system_prompt = ct.SYSTEM_PROMPT_BASE

    def pick_category(sel):
        if isinstance(sel, list):
            for c in sel:
                if c in ct.CATEGORY_GUIDE_MAP:
                    return c
            return "general"
        return sel if sel in ct.CATEGORY_GUIDE_MAP else "general"

    category_key = pick_category(selected_categories)
    user_guide = ct.CATEGORY_GUIDE_MAP[category_key]

    tones_str = (
        ", ".join(selected_tones)
        if isinstance(selected_tones, list) else (selected_tones or "")
    ).strip()

    # ✅ 옵션 컨텍스트를 최상단에 요약 표기 (모델 가이드 강화)
    options_block = f"""
    [컨텍스트]
    - 카테고리: {category_key}
    - 어조: {tones_str or "기본"}
    - 존댓말 유지: {"예" if honorific_checked else "아니오"}
    - 완충문/인사 추가: {"예" if opener_checked else "아니오"}
    - 이모지 허용: {"예" if emoji_checked else "아니오"}
    """.strip()

    final_user_prompt = f"""
    {options_block}
    
    {user_guide}
    
    # 원문 (수정 대상)
    {input_text}
    
    [결과만 출력]
    """.strip()

    return system_prompt, final_user_prompt

