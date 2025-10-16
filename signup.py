# signup.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash
from models import db, User  # ✅ SQLAlchemy 모델 불러오기

signup_bp = Blueprint("signup", __name__)

@signup_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user_id = (request.form.get("user_id") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        agree = bool(request.form.get("agree"))

        # --- 기본 검증 ---
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

        # --- 비밀번호 해시 및 DB 저장 ---
        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        new_user = User(user_id=user_id, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        # --- 가입 즉시 로그인 처리 ---
        session["user"] = {"user_id": user_id, "email": email}
        return redirect(url_for("polish"))

    # GET 요청
    return render_template("signup.html")
