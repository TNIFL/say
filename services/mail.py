import os
import json
import urllib.request
import urllib.error
from email.message import EmailMessage
from threading import Thread

from flask import current_app
from itsdangerous import SignatureExpired, BadSignature

from domain.models import User
from services.auth_tokens import _verify_serializer


RESEND_API_URL = "https://api.resend.com/emails"


def _base_url() -> str:
    # 배포 환경에서 외부 링크 만들 때 사용 (없으면 현재 요청 host가 아니라 여기 값으로 고정 가능)
    return (os.getenv("APP_BASE_URL") or "").rstrip("/")


def _send_resend_email_sync(*, to_email: str, subject: str, text: str) -> bool:
    """
    Resend HTTP API로 메일 발송.
    - True: 요청 성공(Resend가 2xx 반환)
    - False: 실패(네트워크/인증/검증/레이트리밋 등)
    """
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("MAIL_FROM", "Lexinoa <onboarding@resend.dev>")

    if not api_key:
        print("[MAIL][ERROR] RESEND_API_KEY is missing")
        return False

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            # 2xx면 성공 취급
            if 200 <= resp.status < 300:
                print(f"[MAIL][RESEND] ok status={resp.status} to={to_email}")
                return True
            print(f"[MAIL][RESEND][ERROR] status={resp.status} body={body}")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        print(f"[MAIL][RESEND][HTTPError] code={e.code} body={body}")
        return False
    except Exception as e:
        print("[MAIL][RESEND][ERROR]", repr(e))
        return False


# ---- Password reset ----
def _send_email_reset_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 비밀번호 재설정 링크"
    text = f"아래 링크로 접속하여 비밀번호를 재설정하세요 (5분 유효)\n{link}"
    ok = _send_resend_email_sync(to_email=email, subject=subject, text=text)
    if ok:
        print(f"[PASSWORD RESET] To: {email}\nLink: {link}\n")
    return ok


def send_email_reset_link_async(email: str, link: str) -> None:
    Thread(target=_send_email_reset_link_sync, args=(email, link), daemon=True).start()


# ---- Email verify ----
def _send_email_verify_link_sync(email: str, link: str) -> bool:
    subject = "[Lexinoa] 이메일 인증 링크"
    text = f"아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)\n{link}"
    ok = _send_resend_email_sync(to_email=email, subject=subject, text=text)
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
