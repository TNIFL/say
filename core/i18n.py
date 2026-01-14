from flask import request, current_app

def select_locale() -> str:
    """
    우선순위:
    1) ?lang=en
    2) 쿠키 lang=en
    3) Accept-Language 헤더
    4) 기본값 ko
    """
    supported = current_app.config.get("LANGUAGES", ["ko", "en"])

    # 1) Query param
    q = request.args.get("lang", "").strip().lower()
    if q in supported:
        return q

    # 2) Cookie
    c = request.cookies.get("lang", "").strip().lower()
    if c in supported:
        return c

    # 3) Header
    best = request.accept_languages.best_match(supported)
    if best:
        return best

    # 4) Default
    return supported[0]
