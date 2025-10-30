# app.py
from flask_cors import CORS
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort  # ★ jsonify/abort 한 줄로
from dotenv import load_dotenv
from openai import OpenAI
from flask_migrate import Migrate
import os

import build_prompt
from generator import claude_prompt_generator
from config import Config  # 환경설정 (SECRET_KEY, DATABASE_URL 등)
from models import db, RewriteLog, Feedback, User  # SQLAlchemy 인스턴스
from login import auth_bp  # 로그인 블루프린트
from signup import signup_bp  # 회원가입 블루프린트
from build_prompt import build_prompt

load_dotenv()
migrate = Migrate()
PROVIDER_DEFAULT = os.getenv("PROVIDER_DEFAULT", "openai").lower()  # ★ NEW


def create_app():
    app = Flask(__name__)
    # 환경설정 로드
    app.config.from_object(Config)

    # (선택) 확장에서 쿠키 세션을 쓸 경우 권장
    # app.config.update(
    #     SESSION_COOKIE_SAMESITE="None",  # ★ 확장에서 credentials: "include" 시 필수
    #     SESSION_COOKIE_SECURE=True       # ★ HTTPS 필수
    # )

    # 세션 키
    app.secret_key = app.config.get("SECRET_KEY", "dev-secret-change-me")

    # DB & Migrate 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # OpenAI 클라이언트 (앱 속성으로 보관)
    app.openai_client = OpenAI(api_key=os.getenv("GPT_API_KEY"))

    # ★ CORS 초기화: /api/* 만 허용 (운영에서 origins 화이트리스트로 좁히세요)
    CORS(app, supports_credentials=True, resources={
        r"/api/*": {
            "origins": [
                "chrome-extension://*",  # 개발 단계 (운영에선 확장 ID로 좁히기)
                "http://127.0.0.1:*",  # 로컬 프론트(있다면)
                "http://localhost:*",
                "https://www.lexinoa.com/"  # 운영 프론트
            ],
            "methods": ["POST"],
            "allow_headers": ["Content-Type"]
        }
    })

    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)

    # ---------- 공통 유틸: 프롬프트/호출/로그 ----------

    def call_openai_and_log(input_text, selected_categories, selected_tones,
                            honorific_checked, opener_checked, emoji_checked):
        """ OpenAI 호출 + 로그 저장 (공통) """

        output_text = ""
        prompt_tokens = completion_tokens = total_tokens = None
        system_prompt, final_user_prompt = build_prompt(input_text, selected_categories, selected_tones,
                                                        honorific_checked, opener_checked, emoji_checked)

        try:
            completion = app.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_user_prompt},
                ],
                temperature=0.4,
                max_tokens=300,
            )

            output_text = (completion.choices[0].message.content or "").strip()
            usage = getattr(completion, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
            total_tokens = getattr(usage, "total_tokens", None) if usage else None
        except Exception as e:  # ★ 라이브러리 예외 스펙 변동 대비
            # API 에러는 클라이언트에 자세히 노출하지 않음
            output_text = ""

        # 로그는 실패해도 서비스 흐름 유지
        try:
            sess = session.get("user") or {}
            user_id = sess.get("user_id")
            request_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            log = RewriteLog(
                user_id=user_id,
                input_text=input_text,
                output_text=output_text or "(에러/빈 응답)",
                categories=selected_categories,
                tones=selected_tones,
                honorific=honorific_checked,
                opener=opener_checked,
                emoji=emoji_checked,
                model_name="gpt-4.1",
                request_ip=request_ip,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            if user_id:
                user = User.query.filter_by(user_id=user_id).first()
                if user:
                    log.user_pk = user.id
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            print("[rewrite log save error]", log_err)

        return output_text

    """
    # ★ NEW: Gemini 호출 + 로그 저장
    def call_gemini_and_log(input_text, selected_categories, selected_tones,
                            honorific_checked, opener_checked, emoji_checked):
        # Google Gemini 호출 + 기존 DB 로깅 형식에 맞춰 저장 
        output_text = ""
        prompt_tokens = completion_tokens = total_tokens = None
        model_name = "gemini-2.5-pro"  # 기본값

        try:
            # gemini_prompt_generator.gemini_generate는
            # (text) 또는 (text, usage_dict) 반환 둘 다 대응
            system_prompt, final_user_prompt = build_prompt(input_text, selected_categories, selected_tones,
                                                            honorific_checked, opener_checked, emoji_checked)
            result = call_gemini(system_prompt, final_user_prompt)
            if isinstance(result, tuple):
                output_text, usage = result
                if isinstance(usage, dict):
                    model_name = usage.get("model", model_name)
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    total_tokens = usage.get("total_tokens")
            else:
                output_text = result
        except Exception as e:
            output_text = ""

        # 로그는 실패해도 서비스 흐름 유지
        try:
            sess = session.get("user") or {}
            user_id = sess.get("user_id")
            request_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            log = RewriteLog(
                user_id=user_id,
                input_text=input_text,
                output_text=output_text or "(에러/빈 응답)",
                categories=selected_categories,
                tones=selected_tones,
                honorific=honorific_checked,
                opener=opener_checked,
                emoji=emoji_checked,
                model_name=f"gemini:{model_name}",  # ★ provider 표시
                request_ip=request_ip,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            if user_id:
                user = User.query.filter_by(user_id=user_id).first()
                if user:
                    log.user_pk = user.id
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            print("[rewrite log save error]", log_err)

        return output_text
    """

    def call_claude_and_log(input_text,
                            selected_categories,
                            selected_tones,
                            honorific_checked,
                            opener_checked,
                            emoji_checked):
        """ Claude AI 호출 + 기존 DB 로깅 형식에 맞춰 저장 """
        output_text = ""
        prompt_tokens = completion_tokens = total_tokens = None
        model_name = "Claude"
        try:
            system_prompt, final_user_prompt = build_prompt(
                input_text, selected_categories, selected_tones, honorific_checked, opener_checked, emoji_checked)
            result = claude_prompt_generator.call_claude(system_prompt, final_user_prompt)
            if isinstance(result, tuple):
                output_text, usage = result
                if isinstance(usage, dict):
                    model_name = usage.get("model", model_name)
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    total_tokens = usage.get("total_tokens")
            else:
                output_text = result
        except Exception as e:
            output_text = str(e)

        # 로그는 실패해도 서비스 흐름 유지
        try:
            sess = session.get("user") or {}
            user_id = sess.get("user_id")
            request_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            log = RewriteLog(
                user_id=user_id,
                input_text=input_text,
                output_text=output_text or "(에러/빈 응답)",
                categories=selected_categories,
                tones=selected_tones,
                honorific=honorific_checked,
                opener=opener_checked,
                emoji=emoji_checked,
                model_name=f"claude:{model_name}",  # ★ provider 표시
                request_ip=request_ip,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            if user_id:
                user = User.query.filter_by(user_id=user_id).first()
                if user:
                    log.user_pk = user.id
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            print("[rewrite log save error]", log_err)

        return output_text

    # (선택) 간단 페이로드 크기 제한
    @app.before_request
    def guard_payload_size():
        if request.content_length and request.content_length > 256 * 1024:
            abort(413)

    # ===== 메인 라우트(템플릿) =====
    @app.route("/", methods=["GET", "POST"])
    def polish():
        input_text = ""
        output_text = ""
        selected_categories = []
        selected_tones = []
        honorific_checked = False
        opener_checked = False
        emoji_checked = False
        provider_current = PROVIDER_DEFAULT  # ★ NEW: 템플릿에 내려줄 현재 provider

        if request.method == "POST":
            input_text = (request.form.get("input_text") or "").strip()
            selected_categories = request.form.getlist("categories")
            selected_tones = request.form.getlist("tones")
            honorific_checked = bool(request.form.get("honorific"))
            opener_checked = bool(request.form.get("opener"))
            emoji_checked = bool(request.form.get("emoji"))
            provider_current = (request.form.get("provider") or PROVIDER_DEFAULT).lower()  # ★ CHG

            # 값 정규화 (오타 대비)
            if provider_current not in ("openai", "gemini", "claude"):  # ★ NEW
                provider_current = PROVIDER_DEFAULT
            if input_text:
                """
                if provider_current == "gemini":
                    output_text = call_gemini_and_log(
                        input_text, selected_categories, selected_tones,
                        honorific_checked, opener_checked, emoji_checked
                    )
                """
                if provider_current == "openai":
                    output_text = call_openai_and_log(
                        input_text, selected_categories, selected_tones,
                        honorific_checked, opener_checked, emoji_checked
                    )
                elif provider_current == "claude":
                    output_text = call_claude_and_log(
                        input_text, selected_categories, selected_tones,
                        honorific_checked, opener_checked, emoji_checked
                    )

        return render_template(
            "mainpage.html",
            input_text=input_text,
            output_text=output_text or "",
            selected_categories=selected_categories,
            selected_tones=selected_tones,
            honorific_checked=honorific_checked,
            opener_checked=opener_checked,
            emoji_checked=emoji_checked,
            provider_current=provider_current,  # ★ NEW: 템플릿에서 초기 토글 복원에 사용 가능
        )

    # ===== 확장/웹 공용 JSON API =====
    @app.route("/api/polish", methods=["POST"])
    def api_polish():
        try:
            data = request.get_json(silent=True) or {}
        except Exception:
            return jsonify({"error": "invalid_json"}), 400

        input_text = (data.get("input_text") or "").strip()
        if not input_text:
            return jsonify({"error": "empty_input"}), 400
        if len(input_text) > 4000:
            return jsonify({"error": "too_long"}), 413

        selected_categories = data.get("selected_categories") or []
        selected_tones = data.get("selected_tones") or []
        honorific_checked = bool(data.get("honorific_checked"))
        opener_checked = bool(data.get("opener_checked"))
        emoji_checked = bool(data.get("emoji_checked"))

        provider = (data.get("provider") or PROVIDER_DEFAULT).lower()  # ★ CHG
        if provider not in ("openai", "gemini", "claude"):  # ★ NEW
            provider = PROVIDER_DEFAULT
        """
        if provider == "gemini":
            output_text = call_gemini_and_log(
                input_text, selected_categories, selected_tones,
                honorific_checked, opener_checked, emoji_checked
            )
            """
        if provider == "openai":
            output_text = call_openai_and_log(
                input_text, selected_categories, selected_tones,
                honorific_checked, opener_checked, emoji_checked
            )
        elif provider == "claude":
            output_text = call_claude_and_log(
                input_text, selected_categories, selected_tones,
                honorific_checked, opener_checked, emoji_checked
            )

        if not output_text:
            return jsonify({"error": "upstream_error"}), 502

        return jsonify({"output_text": output_text}), 200

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        success = None
        error = None

        # 기본값(로그인 시 이메일/아이디 프리필)
        sess = session.get("user", {}) or {}
        default_email = sess.get("email") or ""
        default_user_id = sess.get("user_id") or ""

        # referrer(어느 페이지에서 왔는지)
        default_page = request.args.get("from") or request.referrer or "/"

        if request.method == "POST":
            email = (request.form.get("email") or "").strip()
            user_id = (request.form.get("user_id") or "").strip() or default_user_id
            category = (request.form.get("category") or "general").strip()
            message = (request.form.get("message") or "").strip()
            page = (request.form.get("page") or default_page).strip()

            if not message:
                error = "피드백 내용을 입력해 주세요."
                return render_template(
                    "feedback.html",
                    error=error,
                    email=email or default_email,
                    user_id=user_id,
                    category=category,
                    message=message,
                    page=page,
                )

            try:
                fb = Feedback(
                    user_id=user_id or None,
                    email=email or default_email or None,
                    category=category or "general",
                    message=message,
                    page=page or None,
                )
                db.session.add(fb)
                db.session.commit()
                success = "소중한 의견 감사합니다! 반영에 노력하겠습니다."
                return render_template(
                    "feedback.html",
                    success=success,
                    email=default_email,
                    user_id=default_user_id,
                    category="general",
                    message="",
                    page=default_page,
                )
            except Exception as e:
                db.session.rollback()
                error = f"저장 중 오류가 발생했습니다: {e}"
                return render_template(
                    "feedback.html",
                    error=error,
                    email=email or default_email,
                    user_id=user_id,
                    category=category,
                    message=message,
                    page=page,
                )

        # GET
        return render_template(
            "feedback.html",
            email=default_email,
            user_id=default_user_id,
            category="general",
            message="",
            page=default_page,
        )

    @app.route("/health")
    def health():
        return "ok", 200

    @app.route("/history")
    def user_history():
        user = session.get("user")
        if not user:
            return redirect(url_for("auth.login_page"))

        user_id = user.get("user_id")
        logs = RewriteLog.query.filter_by(user_id=user_id).order_by(RewriteLog.created_at.desc()).all()
        return render_template("history.html", logs=logs, user=user)

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/disclaimer")
    def disclaimer():
        return render_template("disclaimer.html")

    # ===== 구독/가격 페이지 =====
    @app.route("/subscribe", methods=["GET"])
    def subscribe_page():
        # templates/subscribe.html (캔버스에 만들어둔 파일명) 렌더
        return render_template("subscribe.html")

    # 가격 페이지 별칭 (선택): /pricing → /subscribe
    @app.route("/pricing", methods=["GET"])
    def pricing_alias():
        return redirect(url_for("subscribe_page"))

    # 결제 체크아웃 진입 (스텁)
    # 추후 결제 연동 전까지 404 방지를 위해 임시 페이지/문구 반환
    @app.route("/subscribe/checkout", methods=["GET"])
    def subscribe_checkout():
        # 결제 연동 시: return render_template("checkout.html")
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<style>body{font-family:system-ui, -apple-system, Segoe UI, Roboto, Noto Sans KR;"
            "background:#0f1115;color:#e9edf3;display:grid;place-items:center;height:100vh;margin:0}</style>"
            "<div style='text-align:center'>"
            "<h1 style='margin:0 0 8px'>결제 체크아웃 준비중</h1>"
            "<p style='opacity:.8'>곧 결제 모듈이 연결됩니다.<br>"
            "<a href='/' style='color:#91f2c3;text-decoration:none'>메인으로 돌아가기</a></p>"
            "</div>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
