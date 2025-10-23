# app.py
from flask_cors import CORS
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort  # ★ jsonify/abort 한 줄로
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
                "chrome-extension://*",     # 개발 단계 (운영에선 확장 ID로 좁히기)
                "http://127.0.0.1:*",       # 로컬 프론트(있다면)
                "http://localhost:*",
                "https://say-production.up.railway.app/"   # 운영 프론트
            ],
            "methods": ["POST"],
            "allow_headers": ["Content-Type"]
        }
    })

    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)

    # ---------- 공통 유틸: 프롬프트/호출/로그 ----------

    def build_prompt(input_text, selected_categories, selected_tones,
                     honorific_checked, opener_checked, emoji_checked):
        """ / 와 /api/polish 가 완전히 같은 규칙을 쓰도록 공통화 """
        return f"""
            너는 문장 표현을 자연스럽고 사람답게 다듬는 한국어 글쓰기 비서야.

            사용자가 쓴 문장은 종종 감정이 섞이거나, 너무 직설적이거나, 형식적일 수 있어.
            너의 역할은 그 문장을 '상대방이 편하게 받아들일 수 있는 자연스러운 말'로 고쳐주는 거야.

            다듬을 때는 아래 원칙을 꼭 지켜줘:
            1. 내용의 사실이나 의도는 바꾸지 않아야 해.
            2. 감정적인 표현(짜증, 비꼼, 불만 등)은 부드럽게 풀어서 전달해.
            3. 너무 AI스러운 톤은 사용하지 말고,
               사람이 일상 대화에서 쓰는 말투로 자연스럽게 표현해.
            4. 문장은 완벽하게 다듬되, 약간의 숨 고르기(쉼표, 짧은 문장 나눔)는 유지해. 다만 너무 많이 사용하지는 마
            5. 길이는 원문과 비슷하게 유지해 (±15% 이내).
            6. 어색한 공감문(“이해합니다”, “그럴 수 있겠어요”)은 피하고,
               실제로 상황을 이해한 듯한 톤을 사용해.
            <사람 말투 규칙>

            1. 문장의 초점은 ‘상대’가 아니라 ‘나’의 입장이나 표현으로 옮겨라.
               - 예: “이해하실 수 있을지 궁금합니다.” → “제가 잘 전달했는지 궁금하네요.”
               - 이유: 상대를 평가하는 뉘앙스를 피하고, 자연스러운 겸손함을 전달.

            2. ‘혹시’는 완곡하지만, 문두에 두면 불필요한 거리감을 만들 수 있다.
               - 예: “혹시 전달이 잘 됐을까요?” → “전달이 잘 됐을까 궁금하네요.”
               - 단, 요청·부탁문에서는 유지 (“혹시 가능하실까요?” 등).

            3. 감정이 섞이지 않은 예의 바른 구어체를 선호한다.

            4. 공감 문장은 ‘기계적 표현’ 대신 실제 사람의 반응처럼.
               - “이해합니다” → “그럴 수도 있겠네요.”
               - “불편하셨죠?” → “조금 번거로우셨을 것 같아요.”

            5. 감정이 실린 어휘 대신 상황 설명형으로 전환.
               - “답답하네요” → “조금 더 명확하게 정리해볼게요.”
               - “이 부분이 이상해요” → “이 부분은 다시 확인해보면 좋을 것 같아요.”

            6. 문장은 짧고 리듬감 있게. 문어체보다는 구어체.
               - 문장이 20자 이상이면 쉼표로 호흡을 넣어라.
               - 같은 조사 반복 시 자연스럽게 순서를 바꾼다. (예: “~을, ~을” → “~을, 그리고 ~을”)

            7. 부정·단호한 어조는 최대한 회피하고, ‘제안’ 형태로 말한다.
               - “그건 잘못됐어요.” → “이 부분은 조금 다르게 보는 게 좋을 것 같아요.”
               - “그건 안 됩니다.” → “그건 조금 어려울 수 있을 것 같아요.”

            8. 결과물은 “친절하지만 부담스럽지 않은 말투”,
                즉 “직장 동료나 지인이 읽어도 자연스러운 톤”으로 마무리하라.

            가능하면 ‘누군가가 직접 손으로 다듬은 듯한 문장’을 만들어야 해.
            문체는 너무 격식 있지 않게, 말하듯이 자연스럽게.
            ‘문어체가 아닌 구어체 기반의 공손한 글쓰기’가 이상적이야.

            예:
            - '고객응대' → 응대용 정중함 + 감정 절제
            - '사과' → 짧고 진심어린 사과 + 불필요한 이유 설명 없음
            - '커뮤니티' → 자연스러운 친구 대화체, 짧고 유머러스
            - '보고/결재' → 문장 단정, 조사 간결, 책임 명시
            - '위로' → 공감 중심, 짧은 호흡, 따뜻한 어조

            위의 예시도 참조 해서 대화를 생성해
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
            아 그리고 너무 , / . / "" / * 등 특수기호를 남발하지마
            Ai가 작성한 답변같이 보이는 경우가 많아
            절대 ai가 작성한 답변처럼 보이지 않게 하는게 핵심이야
        """.strip()

    def call_openai_and_log(input_text, selected_categories, selected_tones,
                            honorific_checked, opener_checked, emoji_checked):
        """ OpenAI 호출 + 로그 저장 (공통) """
        prompt = build_prompt(input_text, selected_categories, selected_tones,
                              honorific_checked, opener_checked, emoji_checked)

        output_text = ""
        prompt_tokens = completion_tokens = total_tokens = None

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

        if request.method == "POST":
            input_text = (request.form.get("input_text") or "").strip()
            selected_categories = request.form.getlist("categories")
            selected_tones = request.form.getlist("tones")
            honorific_checked = bool(request.form.get("honorific"))
            opener_checked = bool(request.form.get("opener"))
            emoji_checked = bool(request.form.get("emoji"))

            if input_text:
                output_text = call_openai_and_log(
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
        )

    # ===== 확장/웹 공용 JSON API =====
    @app.route("/api/polish", methods=["POST"])
    def api_polish():
        try:
            data = request.get_json(silent=True) or {}  # ★ silent=True로 JSON parsing 부드럽게
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

        output_text = call_openai_and_log(
            input_text, selected_categories, selected_tones,
            honorific_checked, opener_checked, emoji_checked
        )
        if not output_text:
            # 상류(OpenAI) 오류 등으로 결과가 비었을 때
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
