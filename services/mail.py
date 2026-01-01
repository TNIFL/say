import os
from threading import Thread

import requests
from flask import current_app
from itsdangerous import SignatureExpired, BadSignature

from domain.models import User
from services.auth_tokens import _verify_serializer


def _base_url() -> str:
    # 배포 환경에서 외부 링크 만들 때 사용 (없으면 현재 요청 host가 아니라 여기 값으로 고정 가능)
    return (os.getenv("APP_BASE_URL") or "").rstrip("/")


def _get_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


# =========================
# Resend sender
# =========================
def _send_resend_email_sync(*, to_email: str, subject: str, text: str, html: str | None = None) -> bool:
    """
    Resend API로 이메일 발송.
    필수 환경변수:
      - RESEND_API_KEY
      - MAIL_FROM (예: 'Lexinoa <no-reply@mail.lexinoa.com>')
    선택 환경변수:
      - RESEND_TIMEOUT_SECONDS (기본 10)
    """
    try:
        api_key = _get_env("RESEND_API_KEY")
        from_email = _get_env("MAIL_FROM")
        timeout = int(os.getenv("RESEND_TIMEOUT_SECONDS", "10"))

        payload: dict = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
        }

        # Resend는 text/html 둘 다 가능. html 없으면 text만 보냄.
        if html:
            payload["html"] = html
            payload["text"] = text  # 클라이언트 호환을 위해 같이 넣는 편 권장
        else:
            payload["text"] = text

        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )

        if resp.status_code >= 400:
            # Resend 응답 바디에 에러 이유가 들어 있음(로그로 남기기)
            print("[MAIL][RESEND][HTTP_ERROR]", resp.status_code, resp.text)
            return False

        data = resp.json() if resp.content else {}
        # Resend는 보통 {"id": "..."} 형태 반환
        print(f"[MAIL][RESEND] ok to={to_email} id={data.get('id')}")
        return True

    except requests.RequestException as e:
        print("[MAIL][RESEND][REQUEST_ERROR]", repr(e))
        return False
    except Exception as e:
        print("[MAIL][RESEND][ERROR]", repr(e))
        return False


# ---- Password reset ----
def _send_email_reset_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 비밀번호 재설정 링크"
    text = f"아래 링크로 접속하여 비밀번호를 재설정하세요 (5분 유효)\n{link}"

    # (선택) HTML 버전 - 필요 없으면 html=None로 둬도 됨
    html = f"""
    <p>안녕하세요, Lexinoa입니다.</p>
    <p>아래 링크로 접속하여 비밀번호를 재설정하세요. (5분 유효)</p>
    <p><a href="{link}">비밀번호 재설정하기</a></p>
    <p>요청하지 않으셨다면 이 메일을 무시하셔도 됩니다.</p>
    """

    ok = _send_resend_email_sync(to_email=email, subject=subject, text=text, html=html)
    if ok:
        print(f"[PASSWORD RESET] To: {email}\nLink: {link}\n")
    return ok


def send_email_reset_link_async(email: str, link: str) -> None:
    Thread(target=_send_email_reset_link_sync, args=(email, link), daemon=True).start()


# ---- Email verify ----
def _send_email_verify_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 이메일 인증 링크"
    text = f"아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)\n{link}"

    html = f"""
    <p>안녕하세요, Lexinoa입니다.</p>
    <p>아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)</p>
    <p><a href="{link}">이메일 인증하기</a></p>
    """

    ok = _send_resend_email_sync(to_email=email, subject=subject, text=text, html=html)
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
