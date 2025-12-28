import secrets


from flask import request
from flask import current_app
from itsdangerous import URLSafeSerializer

GUEST_SALT = "guest-key-v1"


def guest_serializer(secret_key: str):
    return URLSafeSerializer(secret_key=secret_key or "dev-secret", salt=GUEST_SALT)


def ensure_guest_cookie():
    """
    게스트 식별 쿠키(aid)를 '항상 같은 규칙'으로 보장한다.
    - 유효한 서명 쿠키가 있으면: (키, False)
    - 없거나(미보유) / 서명 무효이면: (새 키, True)
    """
    s = guest_serializer(current_app.config.get("SECRET_KEY"))

    cur = request.cookies.get(current_app.config["AID_COOKIE"])
    if cur:
        try:
            s.loads(cur)  # 서명 검증 (성공하면 cur 그대로 사용)
            return cur, False
        except Exception:
            pass  # 무효 → 새로 발급

    raw = secrets.token_urlsafe(24)
    signed = s.dumps(raw)
    return signed, True


def set_guest_cookie(resp, aid_value: str):
    # http 로컬 개발환경에서도 동작하도록 secure 자동 전환
    is_secure = request.is_secure or current_app.config.get("PREFERRED_URL_SCHEME", "https") == "https"
    resp.set_cookie(
        current_app.config["AID_COOKIE"],
        aid_value,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
    )
    return resp


