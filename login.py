from secrets import token_urlsafe
from flask import Blueprint, render_template, request, redirect, url_for, session, g
from werkzeug.security import check_password_hash
from models import User
from security import require_safe_input, login_schema

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
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
            return redirect(url_for("polish"))
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
    return redirect(url_for("polish"))
