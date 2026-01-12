# models.py (Nicepay-ready, backward-compatible)
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, Numeric, UniqueConstraint

db = SQLAlchemy()


def utcnow():
    # NOTE: 현재 프로젝트가 naive UTC를 쓰는 전제. (필요 시 timezone-aware로 일괄 전환)
    return datetime.utcnow()


# =========================
#       Core: Users
# =========================
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    user_job = db.Column(db.String(80), nullable=True)
    user_job_detail = db.Column(db.String(400), nullable=True)

    display_name = db.Column(db.String(50), nullable=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # 내부 서비스 식별자(기존 그대로)
    user_id = db.Column(db.String(255), unique=True, nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    # 회원 탈퇴
    deleted_at = db.Column(db.DateTime, nullable=True)
    # 유예기간(30일)
    purge_after = db.Column(db.DateTime, nullable=True)
    # 관계
    rewrites = db.relationship(
        "RewriteLog",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="RewriteLog.user_pk",
    )

    # 결제수단(빌키) - user_id 기반 join(기존 호환)
    payment_methods = db.relationship(
        "PaymentMethod",
        primaryjoin="User.user_id==foreign(PaymentMethod.user_id)",
        lazy=True,
        viewonly=True,
    )

    subscriptions = db.relationship(
        "Subscription",
        backref="user_obj",
        lazy=True,
        primaryjoin="User.user_id==foreign(Subscription.user_id)",
        viewonly=True,
    )

    payments = db.relationship(
        "Payment",
        backref="user_obj",
        lazy=True,
        primaryjoin="User.user_id==foreign(Payment.user_id)",
        viewonly=True,
    )

    templates = db.relationship(
        "UserTemplate",
        backref="user_obj",
        lazy=True,
        primaryjoin="User.user_id==foreign(UserTemplate.user_id)",
        viewonly=True,
    )

    __table_args__ = (
        Index("idx_users_created_at", "created_at"),
    )


# =========================
#       Core: GOOGLE SSO User
# =========================

class OAuthIdentity(db.Model):
    __tablename__ = "oauth_identities"

    id = db.Column(db.BigInteger, primary_key=True)

    provider = db.Column(db.String(32), nullable=False)          # "google"
    provider_sub = db.Column(db.String(255), nullable=False)     # OIDC sub (고유 ID)

    user_pk = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("provider", "provider_sub", name="uq_oauth_provider_sub"),
        Index("idx_oauth_user_pk", "user_pk"),
    )

# =========================
#     Product: Rewrite
# =========================
class RewriteLog(db.Model):
    __tablename__ = "rewrite_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_pk = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_id = db.Column(db.String(255), nullable=True, index=True)

    input_text = db.Column(db.Text, nullable=False)
    output_text = db.Column(db.Text)

    categories = db.Column(JSONB, nullable=False, default=list)
    tones = db.Column(JSONB, nullable=False, default=list)

    honorific = db.Column(db.Boolean, default=False, nullable=False)
    opener = db.Column(db.Boolean, default=False, nullable=False)
    emoji = db.Column(db.Boolean, default=False, nullable=False)

    model_name = db.Column(db.String(64))
    provider = db.Column(db.String(32))  # "openai", "claude", ...
    request_ip = db.Column(db.String(45))

    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)

    latency_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utcnow, index=True, nullable=False)

    __table_args__ = (
        Index("idx_rewritelog_created_at", "created_at"),
        Index("idx_rewritelog_user_created", "user_id", "created_at"),
        Index("idx_rewritelog_model_created", "model_name", "created_at"),
        Index("idx_rewritelog_provider_created", "provider", "created_at"),
    )


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), index=True, nullable=True)
    email = db.Column(db.String(255), nullable=True)

    category = db.Column(db.String(50), nullable=False, default="general")
    message = db.Column(db.Text, nullable=False)
    page = db.Column(db.String(255), nullable=True)

    resolved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    admin_reply = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)


class Visit(db.Model):
    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), index=True, nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    path = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_visits_path_created", "path", "created_at"),
        Index("idx_visits_user_created", "user_id", "created_at"),
    )


# =========================
#   Payment Methods (NICEPAY 빌키=BID)
# =========================
class PaymentMethod(db.Model):
    """
    NICEPAY 정기결제(빌링) 결제수단
    - billing_key: NICEPAY BID(빌키)  <-- 기존 컬럼명 유지(호환)
    - (옵션) tx_tid/auth_token/signature: 빌키 발급(인증) 과정 추적용
    - brand/last4/expiry_ym: CS/만료 알림용 메타
    """
    __tablename__ = "payment_methods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    # provider 기본값 nicepay로 변경
    provider = db.Column(db.String(16), nullable=False, default="nicepay", index=True)

    # NICEPAY BID(빌키)
    billing_key = db.Column(db.String(128), nullable=False, unique=True)

    # (선택) 빌키 발급 인증 단계에서 내려오는 값들(감사/디버깅)
    # - TxTid: 빌키 발급(인증) 응답 거래 ID
    # - AuthToken/Signature: 위변조 검증 및 후속 API 호출에 사용되는 토큰/서명
    tx_tid = db.Column(db.String(40), nullable=True, index=True)
    last_auth_token = db.Column(db.String(80), nullable=True)
    last_signature = db.Column(db.String(128), nullable=True)
    last_order_id = db.Column(db.String(64), nullable=True, index=True)  # orderId(Moid)

    # 카드 메타(가능한 범위에서 마스킹/요약값만)
    brand = db.Column(db.String(32))
    last4 = db.Column(db.String(8))
    expiry_ym = db.Column(db.String(7))  # "2027-05"
    card_code = db.Column(db.String(16), nullable=True, index=True)  # 카드사 코드(있으면)
    card_name = db.Column(db.String(64), nullable=True)

    status = db.Column(db.String(16), nullable=False, default="active")  # active/inactive
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_pm_user_status", "user_id", "status"),
        Index("idx_pm_provider_user", "provider", "user_id"),
    )


# =========================
#   Subscriptions
# =========================
class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    # 내부 구독 상태(서비스 로직 기준 유지)
    status = db.Column(db.String(32), nullable=False, index=True)  # trial/active/past_due/canceled
    plan_name = db.Column(db.String(64), nullable=False)
    plan_amount = db.Column(Numeric(12, 2), nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    canceled_at = db.Column(db.DateTime, nullable=True, index=True)
    next_billing_at = db.Column(db.DateTime, nullable=True, index=True)

    # 매월 같은 날 청구 기준일(1~31)
    anchor_day = db.Column(db.SmallInteger, nullable=True, index=True)

    # 현재 결제 주기(대시보드/정산/분쟁 대비)
    current_period_start = db.Column(db.Date, nullable=True, index=True)
    current_period_end = db.Column(db.Date, nullable=True, index=True)

    # 기간 종료 시 취소
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False, index=True)

    # 실패 횟수 3 회 되면 자동으로 구독 해지
    fail_count = db.Column(db.Integer, nullable=False, default=0, index=True)
    retry_at = db.Column(db.DateTime, nullable=True, index=True)
    last_failed_at = db.Column(db.DateTime, nullable=True, index=True)


    # 기본 결제수단(FK)
    default_payment_method_id = db.Column(
        db.Integer, db.ForeignKey("payment_methods.id"), nullable=True, index=True
    )

    default_payment_method = db.relationship(
        "PaymentMethod",
        foreign_keys=[default_payment_method_id],
        lazy=True,
    )

    __table_args__ = (
        Index("idx_sub_status", "status"),
        Index("idx_sub_created", "created_at"),
        Index("idx_sub_canceled", "canceled_at"),
        Index("idx_sub_user_anchor", "user_id", "anchor_day"),
        Index("idx_sub_retry", "status", "retry_at"),
    )


# =========================
#   Payments (NICEPAY 승인/취소/실패 추적)
# =========================
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # 누가/무엇(구독) 결제인지
    user_id = db.Column(db.String(255), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"), nullable=True, index=True)

    # provider 기본값 nicepay로 변경
    provider = db.Column(db.String(16), nullable=False, default="nicepay", index=True)

    # 가맹점 주문번호:
    # - NICEPAY JS SDK / API 2.0: orderId
    # - 구 WebAPI: Moid
    # 기존 컬럼명(order_id) 유지
    order_id = db.Column(db.String(64), nullable=False, unique=True, index=True)

    # 멱등키(요청 단위로 UNIQUE) - 내부 서비스/잡에서 생성
    idempotency_key = db.Column(db.String(80), nullable=False, unique=True, index=True)

    amount = db.Column(Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="KRW")

    # 내부 결제 상태(서비스 로직 기준)
    # 권장 예: pending / authorized / captured / failed / canceled / refunded
    status = db.Column(db.String(32), nullable=False, index=True)

    # PSP 거래 식별자:
    # - NICEPAY: tid (거래key)
    # 기존 컬럼명(psp_transaction_id) 유지
    psp_transaction_id = db.Column(db.String(64), nullable=True, index=True)

    # 실패 코드/메시지(서비스에서 표준화해서 보관)
    failure_code = db.Column(db.String(64), nullable=True)
    failure_message = db.Column(db.Text, nullable=True)

    # ---------- NICEPAY 인증(결제창) 단계 원본 필드(옵션) ----------
    # 결제창 인증 응답(authResultCode=0000 등), authToken, signature 등 추적용
    auth_result_code = db.Column(db.String(16), nullable=True, index=True)
    auth_result_message = db.Column(db.Text, nullable=True)
    auth_token = db.Column(db.String(80), nullable=True)     # 결제창 인증 토큰
    signature = db.Column(db.String(128), nullable=True)     # 위변조 검증용 서명
    client_id = db.Column(db.String(64), nullable=True, index=True)

    # ---------- 전문 저장(민감정보 마스킹 전제) ----------
    raw_request = db.Column(JSONB, nullable=True)
    raw_response = db.Column(JSONB, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    subscription = db.relationship(
        "Subscription",
        foreign_keys=[subscription_id],
        lazy=True,
    )

    __table_args__ = (
        Index("idx_pay_user_created", "user_id", "created_at"),
        Index("idx_pay_status_created", "status", "created_at"),
        Index("idx_pay_provider_txid", "provider", "psp_transaction_id"),
        Index("idx_pay_provider_order", "provider", "order_id"),
    )


# =========================
#   Webhook/Notify Events (NICEPAY 결제통보/콜백 멱등 로그)
# =========================
class WebhookEvent(db.Model):
    """
    NICEPAY는 연동 방식에 따라 '결제통보(Notify)/ReturnURL 콜백' 형태로 이벤트가 들어옵니다.
    - event_id: payload/headers 등을 해시하여 가맹점이 생성(멱등키). (UNIQUE)
    - signature_valid: 서명 검증 결과(구현 시)
    - processed: 비즈니스 로직 반영 여부(멱등 처리)
    """
    __tablename__ = "webhook_events"

    id = db.Column(db.Integer, primary_key=True)

    provider = db.Column(db.String(16), nullable=False, default="nicepay", index=True)
    event_id = db.Column(db.String(128), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(64), nullable=True, index=True)

    signature_valid = db.Column(db.Boolean, nullable=False, default=True)

    # 원문 보관(민감정보 마스킹/최소화 권장)
    payload = db.Column(JSONB, nullable=True)

    processed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    processed_at = db.Column(db.DateTime, nullable=True, index=True)
    received_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_wh_provider_received", "provider", "received_at"),
        Index("idx_wh_type_received", "event_type", "received_at"),
    )


# =========================
#    Usage Quotas (로그인/구독 — 월간)
# =========================
class Usage(db.Model):
    __tablename__ = "usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    tier = db.Column(db.String(16), nullable=False, index=True)  # "free" | "pro"
    scope = db.Column(db.String(32), nullable=False, default="rewrite", index=True)
    window_start = db.Column(db.Date, nullable=False, index=True)
    count = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "tier", "scope", "window_start",
                         name="uq_usage_user_tier_scope_window"),
        Index("idx_usage_user_window", "user_id", "window_start"),
        Index("ix_usage_scope_window", "scope", "window_start"),
    )


# =========================
#    GuestUsage (비로그인 — 일간)
# =========================
class GuestUsage(db.Model):
    __tablename__ = "guest_usage"

    id = db.Column(db.Integer, primary_key=True)
    guest_key = db.Column(db.String(255), nullable=False, index=True)
    ip = db.Column(db.String(45), nullable=True)
    scope = db.Column(db.String(32), nullable=False, default="rewrite", index=True)
    window_start = db.Column(db.DateTime, nullable=False, index=True)
    count = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("guest_key", "scope", "window_start",
                         name="uq_guest_key_scope_window"),
        Index("idx_guest_window", "window_start"),
        Index("ix_guest_scope_window", "scope", "window_start"),
    )


# =========================
#    System Alerts
# =========================
class SystemAlert(db.Model):
    __tablename__ = "system_alerts"

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(16), nullable=False, index=True)  # info / warn / error
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)


# =========================
#   User Template Library
# =========================
class UserTemplate(db.Model):
    __tablename__ = "user_templates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    tone = db.Column(db.String(50), nullable=True)

    honorific = db.Column(db.Boolean, default=False, nullable=False)
    opener = db.Column(db.Boolean, default=False, nullable=False)
    emoji = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_user_templates_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "title", name="uq_user_template_user_title"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "category": self.category,
            "tone": self.tone,
            "honorific": self.honorific,
            "opener": self.opener,
            "emoji": self.emoji,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# =========================
#   Password Reset Tokens
# =========================
class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_pk = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    token_hash = db.Column(db.String(64), unique=True, index=True, nullable=False)  # sha256(hex)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    created_ip = db.Column(db.String(45), nullable=True)
    created_ua = db.Column(db.Text, nullable=True)

    user = db.relationship("User", backref=db.backref("password_reset_tokens", lazy=True))


# =========================
#   Extension OAuth (Auth Code + Access Token)
# =========================
class ExtensionAuthCode(db.Model):
    """
    확장 OAuth에서 authorize 단계에서 발급되는 1회용 code 저장.
    - code는 DB에 평문 저장(짧은 TTL + 1회용) 또는 hash 저장 둘 다 가능.
      여기서는 구현 단순화를 위해 평문 + 짧은 TTL + 사용 처리로 운영.
    """
    __tablename__ = "extension_auth_codes"

    id = db.Column(db.BigInteger, primary_key=True)

    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)

    # PKCE 검증용 (S256)
    code_challenge = db.Column(db.String(128), nullable=False)
    code_challenge_method = db.Column(db.String(10), nullable=False, default="S256")

    redirect_uri = db.Column(db.Text, nullable=False)
    state = db.Column(db.String(128), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    used_at = db.Column(db.DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("idx_ext_code_user_created", "user_id", "created_at"),
        Index("idx_ext_code_expires", "expires_at"),
    )


class ExtensionToken(db.Model):
    """
    크롬 확장 프로그램 전용 인증 토큰.
    - DB에는 평문 토큰을 저장하지 않고 sha256(hex) 해시만 저장한다.
    - Authorization: Bearer <token> 로 들어온 token을 sha256으로 해시한 뒤 token_hash로 매칭.
    """
    __tablename__ = "extension_tokens"

    id = db.Column(db.BigInteger, primary_key=True)

    user_id = db.Column(db.String(255), nullable=False, index=True)

    # sha256 hex(64)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    note = db.Column(db.String(200), nullable=True)

    __table_args__ = (
        Index("idx_extension_tokens_user_id", "user_id"),
        Index("idx_extension_tokens_revoked", "revoked_at"),
        Index("idx_extension_tokens_expires_at", "expires_at"),
    )
