import os


def _read_text_or_file(val: str) -> str:
    if not val:
        return ""
    # 파일 경로가 존재하면 파일에서 읽고, 아니면 그대로 내용으로 간주
    try:
        if os.path.exists(val):
            with open(val, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return val
