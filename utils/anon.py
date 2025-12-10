# utils/anon.py
import os
import secrets
from itsdangerous import URLSafeSerializer
from flask import current_app, request

COOKIE_NAME = "aid"

def _serializer():
    secret = current_app.config.get("SECRET_KEY") or os.environ.get("SECRET_KEY") or "dev-secret"
    return URLSafeSerializer(secret_key=secret, salt="anon-key-v1")

def ensure_anon_cookie(response=None):
    """요청에 anon 쿠키가 없으면 발급하고, 있으면 검증 후 유지.
       response가 None이면 키만 반환."""
    s = _serializer()
    key = request.cookies.get(COOKIE_NAME)
    if key:
        try:
            s.loads(key)  # 서명 검증
            return key, response
        except Exception:
            pass
    raw = secrets.token_urlsafe(24)
    signed = s.dumps(raw)
    if response is None:
        return signed, None
    response.set_cookie(
        COOKIE_NAME, signed, max_age=60*60*24*365, httponly=True, secure=True, samesite="Lax"
    )
    return signed, response
