#비밀번호 재설정을 위한 함수
from flask import current_app
from itsdangerous import URLSafeTimedSerializer


def _reset_serializer(app):
    cfg = current_app.config
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=cfg.get("RESET_SALT"))


def _verify_serializer(app):
    cfg = current_app.config
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=cfg.get("VERIFY_SALT"))
