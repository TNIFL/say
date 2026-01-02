# services/extension_oauth.py
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from domain.models import db, ExtensionAuthCode, ExtensionToken
from utils.time_utils import utcnow


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _base64url_sha256(verifier: str) -> str:
    """
    PKCE S256 검증: 서버에서는 확장이 보내준 verifier를 sha256 -> base64url 로 만들어 비교해야 한다.
    다만 여기서는 extension이 보내주는 code_challenge 자체를 서버가 저장해두고,
    token 교환 시 verifier를 받아 다시 code_challenge를 계산해 비교한다.
    """
    import base64
    h = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(h).decode("utf-8").rstrip("=")


def issue_auth_code(
    *,
    user_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str | None,
    ttl_minutes: int = 5,
) -> str:
    """
    authorize 단계: 1회용 code 발급 (5분 TTL 권장)
    """
    now = utcnow()
    code = secrets.token_urlsafe(32)

    row = ExtensionAuthCode(
        code=code,
        user_id=user_id,
        code_challenge=code_challenge,
        code_challenge_method="S256",
        redirect_uri=redirect_uri,
        state=state,
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    db.session.add(row)
    db.session.commit()

    print("[EXT_OAUTH][issue_code]", {"user_id": user_id, "expires_at": str(row.expires_at)})
    return code


def exchange_code_for_token(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    note: str | None = None,
    token_expires_days: int | None = None,
) -> dict:
    """
    token 단계: code + verifier로 PKCE 검증 후 access token 발급
    """
    now = utcnow()

    row = ExtensionAuthCode.query.filter_by(code=code).first()
    if not row:
        return {"ok": False, "error": "invalid_code"}

    if row.used_at is not None:
        return {"ok": False, "error": "code_already_used"}

    if row.expires_at <= now:
        return {"ok": False, "error": "code_expired"}

    if row.redirect_uri != redirect_uri:
        return {"ok": False, "error": "redirect_uri_mismatch"}

    # PKCE 검증
    computed = _base64url_sha256(code_verifier)
    if computed != row.code_challenge:
        return {"ok": False, "error": "pkce_failed"}

    # code 1회용 처리
    row.used_at = now
    db.session.commit()

    # access token 발급(평문은 1회만 반환, DB에는 hash 저장)
    raw_token = secrets.token_urlsafe(32)
    token_hash = _sha256_hex(raw_token)

    expires_at = None
    if token_expires_days is not None:
        expires_at = now + timedelta(days=int(token_expires_days))

    t = ExtensionToken(
        user_id=row.user_id,
        token_hash=token_hash,
        created_at=now,
        expires_at=expires_at,
        note=note or "chrome-oauth",
    )
    db.session.add(t)
    db.session.commit()

    print("[EXT_OAUTH][issue_token]", {"user_id": row.user_id, "expires_at": str(expires_at)})

    return {
        "ok": True,
        "access_token": raw_token,
        "token_type": "Bearer",
        "expires_at": expires_at.isoformat() if expires_at else None,
        "user_id": row.user_id,
    }


def find_user_id_by_bearer_token(raw_token: str) -> str | None:
    if not raw_token or len(raw_token) < 10:
        return None

    token_hash = _sha256_hex(raw_token)
    now = utcnow()

    row = ExtensionToken.query.filter_by(token_hash=token_hash).first()
    if not row:
        return None
    if row.revoked_at is not None:
        return None
    if row.expires_at is not None and row.expires_at <= now:
        return None

    row.last_used_at = now
    db.session.commit()
    return row.user_id
