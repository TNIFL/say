from prompt_management.build_prompt import build_prompt

import time
from flask import session, request, current_app
from domain.models import db, RewriteLog, User
from utils.retry import _retry


def call_openai_and_log(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
        *,
        n_outputs=1,
):
    outputs = []
    prompt_tokens = completion_tokens = total_tokens = None
    model_name = "gpt-4.1"

    system_prompt, final_user_prompt = build_prompt(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
    )

    start = time.perf_counter()
    try:
        def _do():
            temp = 0.4 if int(n_outputs) == 1 else 0.85
            top_p = 1.0 if int(n_outputs) == 1 else 0.95
            return current_app.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            final_user_prompt
                            if int(n_outputs) == 1
                            else final_user_prompt
                                 + "\n\n같은 의미를 유지하되, 문장 표현이 서로 다른 한국어 문장 1개를 만들어주세요.\n"
                                   "단어 선택, 어순, 문체, 문장 길이 등을 다양하게 바꿔주세요.\n"
                                   "너무 유사하거나 번역투 느낌이 나는 결과는 피해주세요."
                        ),
                    },
                ],
                temperature=temp,
                top_p=top_p,
                presence_penalty=0.6 if int(n_outputs) > 1 else 0.0,
                frequency_penalty=0.4 if int(n_outputs) > 1 else 0.0,
                max_tokens=300,
                n=max(1, int(n_outputs)),
            )

        completion = _retry(_do)
        for ch in (completion.choices or []):
            content = getattr(getattr(ch, "message", None), "content", None)
            text = (content or "").strip()
            if text:
                outputs.append(text)
        usage = getattr(completion, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
    except Exception:
        outputs = []
    latency_ms = int((time.perf_counter() - start) * 1000)

    # 로그 저장
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
            model_name=model_name,
            request_ip=request_ip,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        if uid:
            u = User.query.filter_by(user_id=uid).first()
            if u:
                log.user_pk = u.id

        if hasattr(RewriteLog, "model_latency_ms"):
            setattr(log, "model_latency_ms", latency_ms)

        db.session.add(log)
        db.session.commit()
    except Exception as log_err:
        db.session.rollback()
        print("[rewrite log save error]", log_err)

    return outputs
