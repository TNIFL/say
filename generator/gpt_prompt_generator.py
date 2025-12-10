# gpt.py
import os
from openai import OpenAI


def gpt_generator(system_prompt, final_user_prompt):
    """OpenAI GPT 모델로 문장 다듬기"""
    print("gpt 로 실행입니다.")
    client = OpenAI(api_key=os.getenv("GPT_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1")

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_user_prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )

    text = (completion.choices[0].message.content or "").strip()
    usage = getattr(completion, "usage", None)
    return text, {
        "provider": "openai",
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "total_tokens": getattr(usage, "total_tokens", None) if usage else None
    }
