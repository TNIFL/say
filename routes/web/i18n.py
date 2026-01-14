from flask import Blueprint, request, redirect, session, current_app
from urllib.parse import urlparse

i18n_bp = Blueprint("i18n", __name__)


def _safe_next_url(next_url: str) -> str:
    if not next_url:
        return "/"
    p = urlparse(next_url)
    if p.scheme or p.netloc:
        return "/"
    return next_url if next_url.startswith("/") else "/" + next_url

@i18n_bp.get("/i18n/set_language/<lang_code>")
def set_language(lang_code):
    lang = "ko" if lang_code == "ko" else "en"
    next_url = _safe_next_url(request.args.get("next", "/"))

    # 세션 저장
    session["lang"] = lang
    session.permanent = True

    resp = redirect(next_url)

    # 쿠키도 저장 (로컬 http에서는 Secure=False가 필수)
    is_dev = (current_app.config.get("ENV") == "development")
    resp.set_cookie(
        "lang",
        lang,
        max_age=60 * 60 * 24 * 365,
        samesite="Lax" if is_dev else "None",
        secure=False if is_dev else True
    )
    return resp