import category_templates as ct


def build_prompt(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked):
    # 1. System Prompt (불변)
    system_prompt = ct.SYSTEM_PROMPT_BASE

    def pick_category(sel):
        if isinstance(sel, list):
            for c in sel:
                if c in ct.CATEGORY_GUIDE_MAP:
                    return c
            return 'general'
        return sel if sel in ct.CATEGORY_GUIDE_MAP else 'general'

    # 2. 카테고리별 고유 지침 가져오기 (Default는 'general')
    category_key = pick_category(selected_categories)

    # 3. User Prompt에 들어갈 내용 조합
    # 톤, 존댓말, 완충문 등은 kwargs에서 가져옵니다.

    user_guide = ct.CATEGORY_GUIDE_MAP[category_key]

    tones_str = ", ".join(selected_tones) if isinstance(selected_tones, list) else str(selected_tones or "")

    # 4. 최종 User Prompt 템플릿 완성
    final_user_prompt = f"""
    {user_guide}

    # 작성 가이드 (선택 사항)
    - 어조: {tones_str}
    - 존댓말 유지: {'예' if {honorific_checked} else '아니오'}
    - 완충문/인사 추가: {'예' if {opener_checked} else '아니오'}
    - 이모지 허용: {'예' if {emoji_checked} else '아니오'}

    # 원문 (수정 대상)
    {input_text}

    [결과만 출력]
    """

    # 반환: API 호출에 사용할 system_prompt와 user_prompt를 분리하여 반환
    return system_prompt, final_user_prompt
