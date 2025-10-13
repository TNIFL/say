# login.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from models import User  # 실제 DB에서 사용자 확인
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        # 1) 이메일 대신 user_id로 입력받기
        user_id = (request.form.get("user_id") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        # 2) DB에서 user_id로 사용자 조회
        user = User.query.filter_by(user_id=user_id).first()

        # 3) 존재 여부 및 비밀번호 확인
        if user and check_password_hash(user.password_hash, password):
            session["user"] = {"user_id": user.user_id, "email": user.email}
            session.permanent = remember
            return redirect(url_for("polish"))
        else:
            return render_template(
                "login.html",
                user_id=user_id,
                remember=remember,
                error="아이디 또는 비밀번호가 올바르지 않습니다.",
            )

    # GET
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("polish"))
