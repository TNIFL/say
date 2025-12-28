# 비밀번호 재설정 링크 보내주는 함수
import os, smtplib
from email.message import EmailMessage
from threading import Thread

from flask import current_app
from itsdangerous import SignatureExpired, BadSignature

from domain.models import User
from services.auth_tokens import _verify_serializer


def _send_email_reset_link_sync(email, link):
    """
    SMTP 설정이 없으면 콘솔에 링크만 출력합니다.
    실제 SMTP 쓰려면: smtplib/메일서비스 연동으로 교체.
    """
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM", "lexinoakr@gmail.com")
    msg["To"] = email
    msg["Subject"] = "[Lexinoa] 비밀번호 재설정 링크"
    msg.set_content(f"아래 링크로 접속하여 비밀번호를 재설정하세요 (5분 유효)\n{link}")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")

    try:
        with smtplib.SMTP(host, port, timeout=5) as s:
            s.starttls(context=None)
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
        print(f"[PASSWORD RESET] To: {email}\nLink: {link}\n")
        return True
    except Exception as e:
        print("[MAIL][ERROR]", repr(e))
        return False


def send_email_reset_link_async(email, link):
    Thread(target=_send_email_reset_link_sync, args=(email, link), daemon=True).start()


def _send_email_verify_link_sync(email, link):
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM", "lexinoakr@gmail.com")
    msg["To"] = email
    msg["Subject"] = "[Lexinoa] 이메일 인증 링크"
    msg.set_content(f"아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)\n{link}")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")

    try:
        with smtplib.SMTP(host, port, timeout=5) as s:
            s.starttls(context=None)
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
        print(f"[EMAIL VERIFY] To: {email}\nLink: {link}\n")
    except Exception as e:
        print("[MAIL][ERROR][VERIFY]", repr(e))


def send_email_verify_link_async(email, link):
    Thread(target=_send_email_verify_link_sync, args=(email, link), daemon=True).start()


def create_email_verify_token(user):
    s = _verify_serializer(current_app)
    payload = {"uid": user.user_id, "email": user.email}
    return s.dumps(payload)


def verify_email_token(raw):
    s = _verify_serializer(current_app)
    try:
        cfg = current_app.config
        data = s.loads(raw, max_age=cfg.get("VERIFY_TTL_SECONDS"))
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"

    uid = (data or {}).get("uid")
    mail = (data or {}).get("email")
    if not uid or not mail:
        return None, "invalid"

    user = User.query.filter_by(user_id=uid).first()
    if not user or user.email.lower() != str(mail).lower():
        return None, "invalid"
    return user, "ok"

