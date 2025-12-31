from flask import request, render_template, url_for, redirect, Blueprint, current_app, session
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func

import time, os

from auth.entitlements import get_current_user
from core.extensions import csrf, limiter

from domain.models import db, User
from services.mail import (
    _send_email_reset_link_sync,
    create_email_verify_token,
    _send_email_verify_link_sync,
    verify_email_token,
)
from services.password_reset import (
    create_password_reset_token,
    verify_password_reset_token,
    consume_password_reset_token,
)
from services.recaptcha import verify_recaptcha_v2

password_reset_bp = Blueprint("password_reset", __name__)


def _sleep_min_elapsed(start: float, min_seconds: float = 1.5) -> None:
    elapsed = time.perf_counter() - start
    if elapsed < min_seconds:
        time.sleep(min_seconds - elapsed)


def _get_reset_ttl_seconds() -> int:
    # env는 문자열이므로 int로 변환 + 기본값 제공
    raw = os.getenv("RESET_TOKEN_TTL_SECONDS", "1800")
    try:
        return int(raw)
    except ValueError:
        return 1800


# 비밀번호 재설정
@password_reset_bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5/minute;20/hour")
def forgot_password():
    if request.method == "POST":
        start = time.perf_counter()
        email = (request.form.get("email") or "").strip().lower()
        recaptcha_response = request.form.get("g-recaptcha-response")

        if not verify_recaptcha_v2(recaptcha_response, request.remote_addr):
            _sleep_min_elapsed(start)
            return render_template(
                "forgot.html",
                error="자동 등록 방지를 통과하지 못했습니다.",
                email=email,
                recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY"),
            )

        if not email:
            _sleep_min_elapsed(start)
            return render_template(
                "forgot.html",
                error="이메일을 입력해 주세요.",
                email=email,
                recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY"),
            )

        user = User.query.filter(func.lower(User.email) == email).first()
        if user:
            ttl = _get_reset_ttl_seconds()
            raw = create_password_reset_token(user, ttl_seconds=ttl)

            link = url_for("password_reset.reset_password", token=raw, _external=True)

            try:
                ok = _send_email_reset_link_sync(user.email, link)
                current_app.logger.info("[MAIL reset] called email=%s ok=%s", user.email, ok)
                if not ok:
                    raise RuntimeError("send returned false")
            except Exception as e:
                current_app.logger.exception("[MAIL reset] failed email=%s err=%r", user.email, e)
                _sleep_min_elapsed(start)
                return render_template(
                    "forgot.html",
                    error="비밀번호 재설정 이메일 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                    email=email,
                    recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY"),
                )

        # 사용자 존재 여부와 무관하게 동일 메시지(계정 존재 유무 유추 방지)
        _sleep_min_elapsed(start)
        return render_template(
            "forgot.html",
            message="입력하신 주소로 안내 메일을 보냈습니다. (수신함/스팸함 확인)",
            recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY"),
        )

    return render_template("forgot.html", recaptcha_site_key=os.getenv("RECAPTCHA_SITE_KEY"))


@password_reset_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "GET":
        row, user, status = verify_password_reset_token(token)
        if status != "ok":
            msg = "유효하지 않은 링크입니다." if status in ("invalid", "used") else "링크가 만료되었습니다."
            code = 400
            flag = {"invalid": True} if status in ("invalid", "used") else {"expired": True}
            return render_template("reset.html", error=msg, **flag), code
        return render_template("reset.html", token=token)

    row, user, status = verify_password_reset_token(token)
    if status != "ok":
        msg = "유효하지 않은 링크입니다." if status in ("invalid", "used") else "링크가 만료되었습니다."
        return render_template("reset.html", error=msg), 400

    p1 = request.form.get("password") or ""
    p2 = request.form.get("password2") or ""
    if len(p1) < 8:
        return render_template("reset.html", error="비밀번호는 8자 이상이어야 합니다.", token=token)
    if p1 != p2:
        return render_template("reset.html", error="비밀번호가 일치하지 않습니다.", token=token)
    if user.password_hash and check_password_hash(user.password_hash, p1):
        return render_template("reset.html", error="사용할 수 없는 비밀번호 입니다.", token=token)

    user.password_hash = generate_password_hash(p1)
    db.session.add(user)
    db.session.commit()
    consume_password_reset_token(row)

    return redirect(url_for("auth.login_page") + "?reset=ok")


# (A) 인증 안내 페이지
@password_reset_bp.route("/verify/require", methods=["GET"])
def verify_require():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login_page"))

    if user.email_verified:
        nxt = request.args.get("next") or "/me"
        return redirect(nxt)

    # 첫 진입이면 자동 발송(세션 플래그로 중복 방지)
    # 사용자가 새로고침/뒤로가기해도 계속 발송 폭주하지 않도록 함
    sent_flag = session.get("_verify_mail_sent")
    if not sent_flag:
        token = create_email_verify_token(user)
        link = url_for("password_reset.verify_confirm", token=token, _external=True)
        ok = _send_email_verify_link_sync(user.email, link)
        session["_verify_mail_sent"] = True
        return render_template(
            "verify_notice.html",
            email=user.email,
            sent=bool(ok),
            next=request.args.get("next") or "",
        )

    return render_template("verify_notice.html", email=user.email, next=request.args.get("next") or "")


# (B) 인증 메일 보내기 (POST)
@password_reset_bp.route("/verify/send", methods=["POST"])
@limiter.limit("3 per minute")
def verify_send():
    user = get_current_user()
    if not user:
        return redirect(url_for("auth.login_page"))

    if user.email_verified:
        return redirect(request.args.get("next") or "/mypage")

    token = create_email_verify_token(user)
    link = url_for("password_reset.verify_confirm", token=token, _external=True)

    try:
        ok = _send_email_verify_link_sync(user.email, link)
        if not ok:
            return render_template(
                "verify_notice.html",
                email=user.email,
                sent=False,
                next=request.args.get("next") or ""
            ), 200

        return render_template("verify_notice.html", email=user.email, sent=True, next=request.args.get("next") or "")

    except Exception as e:
        current_app.logger.exception("[MAIL verify] failed email=%s err=%r", user.email, e)
        return render_template(
            "verify_notice.html",
            email=user.email,
            sent=False,
            error="인증 메일 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            next=request.args.get("next") or "",
        ), 500

    return render_template(
        "verify_notice.html",
        email=user.email,
        sent=True,
        next=request.args.get("next") or "",
    )


# (C) 인증 완료 콜백
@password_reset_bp.route("/verify/<token>", methods=["GET"])
def verify_confirm(token):
    user, status = verify_email_token(token)
    if status != "ok":
        msg = "유효하지 않은 링크입니다." if status == "invalid" else "인증 링크가 만료되었습니다."
        return render_template("verify_result.html", ok=False, message=msg), 400

    if not user.email_verified:
        user.email_verified = True
        db.session.add(user)
        db.session.commit()

    # 인증 완료 시 로그인 세션 생성
    session.clear()
    session["user"] = {"user_id": user.user_id, "email": user.email}

    session.pop("_verify_mail_sent", None)

    return render_template("verify_result.html", ok=True, message="이메일 인증이 완료되었습니다.")
