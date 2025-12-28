import os
from datetime import timedelta
import socket
from flask import Flask, redirect, Blueprint, current_app
from werkzeug.middleware.proxy_fix import ProxyFix

import routes
from core.config import Config
from core.context import init_context_processors
from core.extensions import init_extensions
from core.hooks import register_hooks
from security.headers import init_security_headers



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_extensions(app)
    init_security_headers(app)
    init_context_processors(app)
    socket.setdefaulttimeout(5)

    app.secret_key = app.config.get("SECRET_KEY")
    assert app.secret_key and app.secret_key != "dev-secret-change-me", \
        "SECURITY: 환경변수 SECRET_KEY를 강력한 값으로 설정하세요."

    # 쿠키 기본 설정
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )
    # dev/prod 분기
    app.config["SESSION_COOKIE_SECURE"] = (app.config.get("ENV") != "development")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    routes.register_routes(app)
    register_hooks(app)

    # app.py 또는 create_app() 안쪽 (app 생성 후)
    import traceback
    from flask import request

    @app.after_request
    def _log_bad_requests(resp):
        if resp.status_code == 400:
            try:
                print("\n=== [400 DEBUG] ===")
                print("PATH:", request.path)
                print("METHOD:", request.method)
                print("Content-Type:", request.content_type)
                print("Headers:", dict(request.headers))
                print("Args:", request.args.to_dict())
                # JSON 파싱 실패해도 원문을 찍기 위해 raw data를 출력
                print("Raw body:", request.get_data(as_text=True))
                print("Resp data:", resp.get_data(as_text=True))
                print("=== [/400 DEBUG] ===\n")
            except Exception as e:
                print("[400 DEBUG] logging failed:", e)
        return resp

    # 로그에서 DB URL 확인
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    current_app.logger.info(f"[DB] SQLALCHEMY_DATABASE_URI={db_uri}")
    current_app.logger.info(f"[DB] DATABASE_URL env exists? {'DATABASE_URL' in os.environ}")

    @app.get("/health")
    def health():
        return {"ok": True}, 200

    return app
