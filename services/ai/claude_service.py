from domain.models import RewriteLog, User, db
from generator import claude_prompt_generator
from prompt_management.build_prompt import build_prompt
from utils.retry import _retry

from flask import session, request
from flask_babel import get_locale


def _normalize_lang(lang: str | None) -> str:
    """
    Normalize lang into 'ko' or 'en'.
    Accepts values like 'en', 'en-US', 'ko-KR', etc.
    """
    raw = (lang or "ko").strip().lower()
    if raw.startswith("en"):
        return "en"
    return "ko"


def _variant_instruction(count: int, lang: str) -> str:
    """
    Language-specific variant generation instruction.
    Ensures Claude outputs in the selected language.
    """
    if lang == "en":
        return (
            f"Based on the original message, produce {count} alternative English rewrites "
            f"with the same meaning but different phrasing.\n"
            f"Each rewrite must be a single line (no paragraphs).\n"
            f"Output format exactly:\n"
            f"1) Sentence 1\n2) Sentence 2\n3) Sentence 3\n"
            f"(Continue numbering if count > 3)\n"
            f"Important: Output must be in English only."
        )

    # default: ko
    return (
        f"위 문장을 바탕으로, 같은 의미를 유지하되 표현 방식이 다른 "
        f"한국어 문장 {count}개를 만들어주세요.\n"
        f"각 문장은 한 줄짜리로, 단락 없이 깔끔하게 써주세요.\n"
        f"출력 형식은:\n"
        f"1) 문장1\n2) 문장2\n3) 문장3\n형태로 주세요.\n"
        f"(count가 3보다 크면 번호를 이어서 출력)\n"
        f"중요: 최종 출력은 반드시 한국어로만 작성해."
    )


def _current_lang_from_babel() -> str:
    """
    Uses Flask-Babel's resolved locale (driven by ?lang / cookie / Accept-Language).
    Falls back to 'ko'.
    """
    try:
        loc = get_locale()
        return _normalize_lang(str(loc) if loc else "ko")
    except Exception:
        return "ko"


def call_claude_and_log(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
        *,
        n_outputs=1,
        user_job="",
        user_job_detail="",
        context_source="",
        context_label="",
):
    """
    Claude 호출 (결과 개수 고정형)

    - 현재 선택된 i18n 언어(Flask-Babel locale)에 맞춰:
      1) build_prompt의 scaffold 라벨(원문/출력 등) 언어 적용
      2) 변형 생성 지시(variant instruction) 언어 적용
      3) 결과를 해당 언어로 강제
    - 함수명/시그니처 유지 (요구사항)
    """
    outputs = []
    model_name = "claude"

    try:
        lang = _current_lang_from_babel()

        system_prompt, final_user_prompt = build_prompt(
            input_text,
            selected_categories,
            selected_tones,
            honorific_checked,
            opener_checked,
            emoji_checked,
            user_job=user_job,
            user_job_detail=user_job_detail,
            context_source=context_source,
            context_label=context_label,
            target_lang=lang,  # build_prompt.py에 추가한 파라미터
        )

        count = max(1, int(n_outputs))

        variant_prompt = (
            f"{final_user_prompt}\n\n"
            f"{_variant_instruction(count, lang)}"
        )

        def _do():
            return claude_prompt_generator.call_claude(system_prompt, variant_prompt)

        result = _retry(_do)
        text = _as_text_from_claude_result(result).strip()

        # 기존 파싱 로직 유지 (번호/불릿 제거)
        lines = [l.strip(" -•*0123456789.)\t") for l in text.splitlines() if l.strip()]
        outputs = [l for l in lines if len(l) > 1][:count]

        while len(outputs) < count:
            outputs.append(outputs[-1] if outputs else "(빈 결과)")

    except Exception as e:
        outputs = [f"(Claude 오류) {e}"]

    # 로그 저장 (첫 번째 결과만 기록)
    try:
        sess = session.get("user") or {}
        uid = sess.get("user_id")
        request_ip = request.remote_addr
        log = RewriteLog(
            user_pk=None,
            user_id=uid,
            input_text=input_text,
            output_text=(outputs[0] if outputs else "(에러/빈 응답)"),
            categories=selected_categories or [],
            tones=selected_tones or [],
            honorific=bool(honorific_checked),
            opener=bool(opener_checked),
            emoji=bool(emoji_checked),
            model_name=f"claude:{model_name}",
            request_ip=request_ip,
        )
        if uid:
            u = User.query.filter_by(user_id=uid).first()
            if u:
                log.user_pk = u.id
        db.session.add(log)
        db.session.commit()
    except Exception as log_err:
        db.session.rollback()
        print("[rewrite log save error]", log_err)

    return outputs


def _as_text_from_claude_result(result) -> str:
    """
    claude_prompt_generator.call_claude(...) 반환값 정규화
    """
    if result is None:
        return ""
    if isinstance(result, tuple) and len(result) >= 1:
        return str(result[0] or "")
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("text") or result.get("content") or "")
    return str(result or "")
