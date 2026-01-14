import os
from datetime import timedelta
import socket
from flask import Flask, Response, session
from flask_babel import Babel
from werkzeug.middleware.proxy_fix import ProxyFix

import routes
from auth.entitlements import load_current_user
from core.config import Config
from core.context import init_context_processors
from core.extensions import init_extensions, oauth
from core.hooks import register_hooks
from security.headers import init_security_headers

from flask_babel import gettext, get_locale

from core.extensions import babel


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_extensions(app)
    oauth.init_app(app)
    init_security_headers(app)
    init_context_processors(app)
    socket.setdefaulttimeout(5)

    app.secret_key = app.config.get("SECRET_KEY")
    assert app.secret_key and app.secret_key != "dev-secret-change-me", \
        "SECURITY: 환경변수 SECRET_KEY를 강력한 값으로 설정하세요."

    # 쿠키 기본 설정
    is_dev = (app.config.get("ENV") == "development")

    # 확장 프로그램(크롬 extension)에서 credentials: "include" 로 세션 쿠키가 붙으려면
    # 프로덕션에서는 SameSite=None + Secure 가 사실상 필수
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    if is_dev:
        # 로컬 개발에서는 https가 아니므로 Secure/None 조합이 깨질 수 있어 Lax 유지
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        app.config["SESSION_COOKIE_SECURE"] = False
    else:
        # 운영(https)에서는 확장 프로그램에서도 세션 쿠키가 전송되도록 None + Secure 강제
        app.config["SESSION_COOKIE_SAMESITE"] = "None"
        app.config["SESSION_COOKIE_SECURE"] = True

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    @app.before_request
    def _load_user_global():
        load_current_user()

    def select_locale():
        q = request.args.get("lang")
        if q in ("ko", "en"):
            return q

        s = session.get("lang")
        if s in ("ko", "en"):
            return s

        c = request.cookies.get("lang")
        if c in ("ko", "en"):
            return c

        return request.accept_languages.best_match(["ko", "en"]) or "en"

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
    # print("[DB] SQLALCHEMY_DATABASE_URI=", app.config.get("SQLALCHEMY_DATABASE_URI"))
    # print("[DB] DATABASE_URL env exists?", "DATABASE_URL" in os.environ)
    @app.get("/health")
    def health():
        return {"ok": True}, 200

    @app.route("/ads.txt")
    def ads_txt():
        return app.send_static_file("ads.txt")

    @app.route("/robots.txt")
    def robots_txt():
        return Response(
            "User-agent: *\nDisallow:\n",
            mimetype="text/plain"
        )


    @app.get("/_i18n_test")
    def _i18n_test():
        return f"locale={get_locale()} | " + gettext("문장 교정")

    print("DEBUG app.root_path =", app.root_path)
    print("DEBUG expected mo =", os.path.join(app.root_path, "translations", "en", "LC_MESSAGES", "messages.mo"))
    print("DEBUG exists? =",
          os.path.exists(os.path.join(app.root_path, "translations", "en", "LC_MESSAGES", "messages.mo")))
    print("DEBUG BABEL_TRANSLATION_DIRECTORIES =", app.config.get("BABEL_TRANSLATION_DIRECTORIES"))

    return app


