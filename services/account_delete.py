# services/account_delete.py
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_

from domain.models import (
    db,
    User,
    RewriteLog,
    UserTemplate,
    Feedback,
    Visit,
    Usage,
    PasswordResetToken,
    Subscription,
    PaymentMethod,
)


# -------------------------
# Utils
# -------------------------
def utcnow():
    return datetime.utcnow()


def _anonymized_email() -> str:
    # RFC2606 reserved domain (실제 메일 발송 불가)
    return f"deleted+{uuid.uuid4().hex}@example.invalid"


def _disabled_password_hash() -> str:
    # 로그인 불가능한 임의 값
    return "deleted:" + secrets.token_hex(32)


# ============================================================
# 1) 탈퇴 요청 (30일 유예 시작)
# ============================================================
def request_account_delete(user_pk: int, *, reason: str | None = None) -> dict:
    """
    탈퇴 요청
    - 즉시 로그인/결제/사용 차단
    - 데이터는 보존
    - 30일 내 복구 가능
    """
    now = utcnow()
    purge_after = now + timedelta(days=30)

    user = User.query.get(user_pk)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    uid = user.user_id

    # 1) 활성 구독 즉시 취소 (보존)
    subs = Subscription.query.filter(
        and_(
            Subscription.user_id == uid,
            Subscription.status.in_(("trial", "active", "past_due", "incomplete")),
        )
    ).all()

    for sub in subs:
        sub.status = "canceled"
        sub.canceled_at = now
        sub.next_billing_at = None
        sub.retry_at = None
        sub.cancel_at_period_end = False

    # 2) 결제수단 비활성화 (보존)
    PaymentMethod.query.filter(
        PaymentMethod.user_id == uid
    ).update(
        {PaymentMethod.status: "inactive"},
        synchronize_session=False,
    )

    # 3) 사용자 비활성화 + 유예 마킹
    user.is_active = False
    user.deleted_at = now
    user.purge_after = purge_after

    db.session.commit()

    print("[ACCOUNT_DELETE_REQUEST]", {
        "user_pk": user_pk,
        "user_id": uid,
        "purge_after": purge_after.isoformat(),
        "reason": reason,
    })

    return {
        "ok": True,
        "purge_after": purge_after.isoformat(),
        "canceled_subscriptions": len(subs),
    }


# ============================================================
# 2) 탈퇴 복구 (30일 이내)
# ============================================================
def restore_account(user_pk: int) -> dict:
    """
    탈퇴 복구
    - 30일 내만 가능
    - 구독/결제수단은 복구 불가 (재가입 필요)
    """
    now = utcnow()

    user = User.query.get(user_pk)
    if not user or not user.deleted_at:
        return {"ok": False, "error": "not_deleted"}

    if user.purge_after and now > user.purge_after:
        return {"ok": False, "error": "purge_expired"}

    user.is_active = True
    user.deleted_at = None
    user.purge_after = None

    db.session.commit()

    print("[ACCOUNT_RESTORE]", {
        "user_pk": user_pk,
        "user_id": user.user_id,
    })

    return {"ok": True}


# ============================================================
# 3) 탈퇴 확정 (30일 경과 후) — 크론용
# ============================================================
def purge_expired_accounts(limit: int = 100) -> dict:
    """
    30일 유예가 끝난 계정을 완전 탈퇴 처리
    - 개인정보/콘텐츠 삭제
    - 피드백은 익명화
    - 결제/구독/웹훅은 보존
    """
    now = utcnow()

    users = User.query.filter(
        User.deleted_at.isnot(None),
        User.purge_after <= now,
    ).limit(limit).all()

    purged = 0

    for user in users:
        _finalize_delete(user)
        purged += 1

    db.session.commit()

    print("[ACCOUNT_PURGE]", {"count": purged})
    return {"ok": True, "purged": purged}


def _finalize_delete(user: User):
    """
    내부용: 완전 탈퇴 처리
    """
    uid = user.user_id

    # 1) 보안 토큰 즉시 삭제
    PasswordResetToken.query.filter(
        PasswordResetToken.user_pk == user.id
    ).delete(synchronize_session=False)

    # 2) 사용자 콘텐츠 삭제
    RewriteLog.query.filter(
        (RewriteLog.user_pk == user.id) | (RewriteLog.user_id == uid)
    ).delete(synchronize_session=False)

    UserTemplate.query.filter(
        UserTemplate.user_id == uid
    ).delete(synchronize_session=False)

    Usage.query.filter(
        Usage.user_id == uid
    ).delete(synchronize_session=False)

    Visit.query.filter(
        Visit.user_id == uid
    ).delete(synchronize_session=False)

    # 3) 피드백 익명화 (삭제 안함)
    Feedback.query.filter(
        Feedback.user_id == uid
    ).update(
        {
            Feedback.user_id: None,
            Feedback.email: None,
        },
        synchronize_session=False,
    )

    # 4) 사용자 계정 익명화 + 비활성화
    user.is_active = False
    user.is_admin = False
    user.email_verified = False

    user.user_job = None
    user.user_job_detail = None

    user.email = _anonymized_email()
    user.password_hash = _disabled_password_hash()

    print("[ACCOUNT_FINAL_DELETE]", {
        "user_pk": user.id,
        "user_id": uid,
    })
