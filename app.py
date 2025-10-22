# app.py
from flask import Flask, render_template, request, session, redirect, url_for
from dotenv import load_dotenv
from openai import OpenAI
from flask_migrate import Migrate
import os

from config import Config  # 환경설정 (SECRET_KEY, DATABASE_URL 등)
from models import db, RewriteLog, Feedback, User  # SQLAlchemy 인스턴스
from login import auth_bp  # 로그인 블루프린트
from signup import signup_bp  # 회원가입 블루프린트

load_dotenv()

migrate = Migrate()


def create_app():
    app = Flask(__name__)
    # 환경설정 로드
    app.config.from_object(Config)

    # 세션 키
    app.secret_key = app.config.get("SECRET_KEY", "dev-secret-change-me")

    # DB & Migrate 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # OpenAI 클라이언트 (앱 속성으로 보관)
    app.openai_client = OpenAI(api_key=os.getenv("GPT_API_KEY"))

    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)

    # ===== 메인 라우트 =====
    @app.route("/", methods=["GET", "POST"])
    def polish():
        input_text = ""
        output_text = ""
        selected_categories = []
        selected_tones = []
        honorific_checked = False
        opener_checked = False
        emoji_checked = False

        if request.method == "POST":
            input_text = (request.form.get("input_text") or "").strip()
            selected_categories = request.form.getlist("categories")
            selected_tones = request.form.getlist("tones")
            honorific_checked = bool(request.form.get("honorific"))
            opener_checked = bool(request.form.get("opener"))
            emoji_checked = bool(request.form.get("emoji"))

            prompt = f"""
            너는 문장 표현을 자연스럽고 사람답게 다듬는 한국어 글쓰기 비서야.

            사용자가 쓴 문장은 종종 감정이 섞이거나, 너무 직설적이거나, 형식적일 수 있어.
            너의 역할은 그 문장을 '상대방이 편하게 받아들일 수 있는 자연스러운 말'로 고쳐주는 거야.

            다듬을 때는 아래 원칙을 꼭 지켜줘:
            1. 내용의 사실이나 의도는 바꾸지 않아야 해.
            2. 감정적인 표현(짜증, 비꼼, 불만 등)은 부드럽게 풀어서 전달해.
            3. 너무 AI스럽거나 고객센터식 톤(“확인 도와드리겠습니다”)은 절대 사용하지 말고,
               사람이 일상 대화에서 쓰는 말투로 자연스럽게 표현해.
            4. 문장은 완벽하게 다듬되, 약간의 숨 고르기(쉼표, 짧은 문장 나눔)는 유지해.
            5. 길이는 원문과 비슷하게 유지해 (±15% 이내).
            6. 어색한 공감문(“이해합니다”, “그럴 수 있겠어요”)은 피하고,
               실제로 상황을 이해한 듯한 톤을 사용해.

            가능하면 ‘누군가가 직접 손으로 다듬은 듯한 문장’을 만들어야 해.
            문체는 너무 격식 있지 않게, 말하듯이 자연스럽게.  
            ‘문어체가 아닌 구어체 기반의 공손한 글쓰기’가 이상적이야.

            ---

            🗂 카테고리: {', '.join(selected_categories) or '일반'}
            💬 말투: {', '.join(selected_tones) or '부드럽게'}
            🙇 존댓말 유지: {'예' if honorific_checked else '아니오'}
            🙏 완충문/인사 추가: {'예' if opener_checked else '아니오'}
            🙂 이모지 허용: {'예' if emoji_checked else '아니오'}

            ---

            📝 원문:
            {input_text}

            ---

            결과는 오직 다듬어진 문장만 출력해.
            너무 딱딱하지 않게, ‘사람이 쓴 것처럼 부드럽고 자연스럽게’ 표현해줘.
            """

            if input_text:
                try:
                    completion = app.openai_client.chat.completions.create(
                        model="gpt-4.1",
                        messages=[
                            {"role": "system", "content": "너는 한국어 문체 교정 전문가야."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.4,
                        max_tokens=300,
                    )
                    output_text = (completion.choices[0].message.content or "").strip()

                    # 사용량(토큰) 추출은 있으면 저장, 없으면 None
                    usage = getattr(completion, "usage", None)
                    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
                    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
                    total_tokens = getattr(usage, "total_tokens", None) if usage else None

                except OpenAI.APIError as APIError:
                    output_text = f"[오류] {APIError}"
                except OpenAI.RateLimitError as ratelimitError:
                    output_text = f"[오류] {ratelimitError}"
                finally:
                    # DB에 로그 저장 (오류가 나도 입력/옵션은 남길 수 있게 finally에서 처리)
                    try:
                        sess = session.get("user") or {}
                        user_id = sess.get("user_id")

                        # 실제 클라이언트 IP (프록시 뒤에 있으면 X-Forwarded-For 참조)
                        request_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

                        log = RewriteLog(
                            user_id=user_id,
                            input_text=input_text,
                            output_text=output_text,
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
                        # 로그 저장 실패해도 서비스 흐름은 유지
                        print("[rewrite log save error]", log_err)

        return render_template(
            "mainpage.html",
            input_text=input_text,
            output_text=output_text,
            selected_categories=selected_categories,
            selected_tones=selected_tones,
            honorific_checked=honorific_checked,
            opener_checked=opener_checked,
            emoji_checked=emoji_checked,
        )

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        """피드백 작성/저장"""
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
                # 폼 비우고 성공 메시지만 표시
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
        # 로그인 여부 확인
        user = session.get("user")
        if not user:
            return redirect(url_for("auth.login_page"))  # 로그인 안 한 경우 로그인 페이지로

        user_id = user.get("user_id")

        # DB에서 해당 유저의 기록 가져오기 (최신순)
        logs = RewriteLog.query.filter_by(user_id=user_id).order_by(RewriteLog.created_at.desc()).all()

        return render_template("history.html", logs=logs, user=user)

    # app.py 안의 create_app() 내부, 다른 route들과 같은 레벨에 추가
    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/disclaimer")
    def disclaimer():
        return render_template("disclaimer.html")


    return app





if __name__ == "__main__":
    app = create_app()
    # 개발 중 최초 1회는 마이그레이션 대신 간단 생성도 가능:
    # with app.app_context():
    #     db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
