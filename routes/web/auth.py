from secrets import token_urlsafe
from flask import Blueprint, render_template, request, redirect, url_for, session, g
from werkzeug.security import check_password_hash
from domain.models import User, db
from security.security import require_safe_input
from domain.schema import login_schema, signup_schema
from werkzeug.security import generate_password_hash

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
# require_safe_input -> 이 라우트에서 입력받는 정보들은 login_schema 를 지켜야한다
@require_safe_input(login_schema, form=True)
def login_page():
    if request.method == "POST":
        data = g.safe_input
        user_id = data["user_id"]
        password = data["password"]
        remember = bool(data.get("remember") == "on")

        # 세션 초기화
        session.clear()

        # DB 조회 및 검증
        user = User.query.filter_by(user_id=user_id).first()
        if user and check_password_hash(user.password_hash, password):
            session["user"] = {
                "user_id": user.user_id,
                "email": user.email
            }
            session.permanent = remember
            session["csrf_guard"] = token_urlsafe(24)
            return redirect("/")
        else:
            return render_template(
                "login.html",
                user_id=user_id,
                remember=remember,
                error="아이디 또는 비밀번호가 올바르지 않습니다.",
            )

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


@auth_bp.route("/signup", methods=["GET", "POST"])
@require_safe_input(signup_schema, form=True)
def signup():
    # GET 요청은 검증 생략 → g.safe_input == None
    if g.safe_input is None:
        return render_template("signup.html")

    data = g.safe_input
    user_id = (data.get("user_id") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm") or ""
    agree = bool(data.get("agree"))

    # --- 추가 수동 검증 ---
    if not user_id:
        return render_template("signup.html", error="아이디를 입력해주세요.", user_id=user_id, email=email)
    if not email or not password:
        return render_template("signup.html", error="이메일과 비밀번호를 입력해 주세요.", user_id=user_id, email=email)
    if "@" not in email:
        return render_template("signup.html", error="올바른 이메일 형식이 아닙니다.", user_id=user_id, email=email)
    if len(password) < 8:
        return render_template("signup.html", error="비밀번호는 8자 이상이어야 합니다.", user_id=user_id, email=email)
    if password != confirm:
        return render_template("signup.html", error="비밀번호 확인이 일치하지 않습니다.", user_id=user_id, email=email)
    if not agree:
        return render_template("signup.html", error="이용약관에 동의해 주세요.", user_id=user_id, email=email)

    # --- 중복 이메일 체크 ---
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return render_template("signup.html", error="이미 가입된 이메일입니다.", user_id=user_id, email=email)

    try:
        # --- 비밀번호 해시 + DB 저장 ---
        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        new_user = User(user_id=user_id, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        # --- 가입 즉시 로그인 처리 ---
        session["user"] = {"user_id": user_id, "email": email}
        return redirect(url_for("rewrite.polish"))
    except Exception as e:
        db.session.rollback()
        return render_template("signup.html", error=f"회원가입 중 오류가 발생했습니다: {e}")
