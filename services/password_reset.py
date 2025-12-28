import hashlib
import secrets

from domain.models import PasswordResetToken, db, User
from utils.time_utils import _utcnow

from flask import request
from datetime import timedelta, timezone

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_password_reset_token(user, *, ttl_seconds=60 * 5):
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    now = _utcnow()
    row = PasswordResetToken(
        user_pk=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(seconds=ttl_seconds),
        created_at=now,
        created_ip=(request.remote_addr or None),
        created_ua=(request.headers.get("User-Agent") or None)[:500],
    )
    db.session.add(row)
    db.session.commit()
    return raw


def verify_password_reset_token(raw: str):
    token_hash = _hash_token(raw)
    row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not row:
        return None, None, "invalid"
    if row.used_at is not None:
        return None, None, "used"
    # Fix: Ensure row.expires_at is timezone-aware before comparison
    expires_at_aware = row.expires_at
    if expires_at_aware.tzinfo is None:  # If it's naive
        expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)  # Assume it's UTC naive

    if expires_at_aware < _utcnow():  # Compare aware datetimes
        return None, None, "expired"
    user = User.query.get(row.user_pk)
    if not user:
        return None, None, "invalid"
    return row, user, "ok"


def consume_password_reset_token(row):
    row.used_at = _utcnow()
    db.session.add(row)
    db.session.commit()
