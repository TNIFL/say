import os
import smtplib
from email.message import EmailMessage
from threading import Thread

from flask import current_app
from itsdangerous import SignatureExpired, BadSignature

from domain.models import User
from services.auth_tokens import _verify_serializer


def _base_url() -> str:
    # 배포 환경에서 외부 링크 만들 때 사용 (없으면 현재 요청 host가 아니라 여기 값으로 고정 가능)
    return (os.getenv("APP_BASE_URL") or "").rstrip("/")


def _get_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _send_ses_smtp_email_sync(*, to_email: str, subject: str, text: str) -> bool:
    """
    Amazon SES SMTP로 텍스트 이메일 발송.
    필수 환경변수:
      - SES_SMTP_HOST (예: email-smtp.ap-northeast-2.amazonaws.com)
      - SES_SMTP_PORT (예: 587)
      - SES_SMTP_USERNAME
      - SES_SMTP_PASSWORD
      - MAIL_FROM (예: no-reply@lexinoa.com)

    주의:
      - SES Sandbox면 To 주소가 SES에서 Verified된 이메일이어야 함.
      - MAIL_FROM 도메인(lexinoa.com)은 SES에서 Verified 되어 있어야 함.
    """
    try:
        host = _get_env("SES_SMTP_HOST")
        port = int(_get_env("SES_SMTP_PORT", "587"))
        username = _get_env("SES_SMTP_USERNAME")
        password = _get_env("SES_SMTP_PASSWORD")
        from_email = _get_env("MAIL_FROM")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(text)

        # SES SMTP: STARTTLS 권장 (587)
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.send_message(msg)

        print(f"[MAIL][SES_SMTP] ok to={to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        # 아이디/비번 오류, 또는 리전/호스트 불일치 시 자주 발생
        print("[MAIL][SES_SMTP][AUTH_ERROR]", repr(e))
        return False

    except smtplib.SMTPException as e:
        print("[MAIL][SES_SMTP][SMTP_ERROR]", repr(e))
        return False

    except Exception as e:
        print("[MAIL][SES_SMTP][ERROR]", repr(e))
        return False


# ---- Password reset ----
def _send_email_reset_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 비밀번호 재설정 링크"
    text = f"아래 링크로 접속하여 비밀번호를 재설정하세요 (5분 유효)\n{link}"
    ok = _send_ses_smtp_email_sync(to_email=email, subject=subject, text=text)
    if ok:
        print(f"[PASSWORD RESET] To: {email}\nLink: {link}\n")
    return ok


def send_email_reset_link_async(email: str, link: str) -> None:
    Thread(target=_send_email_reset_link_sync, args=(email, link), daemon=True).start()


# ---- Email verify ----
def _send_email_verify_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 이메일 인증 링크"
    text = f"아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)\n{link}"
    ok = _send_ses_smtp_email_sync(to_email=email, subject=subject, text=text)
    if ok:
        print(f"[EMAIL VERIFY] To: {email}\nLink: {link}\n")
    return ok


def send_email_verify_link_async(email: str, link: str) -> None:
    Thread(target=_send_email_verify_link_sync, args=(email, link), daemon=True).start()


# ---- Tokens ----
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
