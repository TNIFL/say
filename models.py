# models.py
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB  # PostgreSQL 사용 시 권장
from sqlalchemy import Index, Numeric, UniqueConstraint, ForeignKey, LargeBinary

db = SQLAlchemy()


def utcnow():
    return datetime.utcnow()


# =========================
#       Core: Users
# =========================
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.String(255), unique=True, nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # 관계
    rewrites = db.relationship(
        "RewriteLog",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="RewriteLog.user_pk",
    )

    # ✅ NEW: 결제수단(빌링키) 뷰 전용 관계
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

    latency_ms = db.Column(db.Integer)  # 평균 응답시간 계산용
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
#   NEW: Payment Methods (빌링키 보관)
# =========================
class PaymentMethod(db.Model):
    """
    토스 빌링키 기반 자동결제용 결제수단
    - billing_key: 토스 측 위임키(문자열)
    - brand/last4/expiry_ym: 고객 문의/만료 안내용 메타
    """
    __tablename__ = "payment_methods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    provider = db.Column(db.String(16), nullable=False, default="toss", index=True)

    # 보관 방식 1) 평문 문자열 (실서비스에선 애플리케이션 레벨 암호화 권장)
    billing_key = db.Column(db.String(128), nullable=False, unique=True)

    # 보관 방식 2) 암호문 저장이 필요하면 위 필드 대신 아래 필드 사용
    # billing_key_ciphertext = db.Column(LargeBinary, nullable=False)
    # kms_key_id = db.Column(db.String(64), nullable=True)

    brand = db.Column(db.String(32))
    last4 = db.Column(db.String(8))
    expiry_ym = db.Column(db.String(7))  # "2027-05"

    status = db.Column(db.String(16), nullable=False, default="active")  # active/inactive
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_pm_user_status", "user_id", "status"),
    )


# =========================
#   CHANGED: Subscriptions (앵커일/기간/기본 결제수단)
# =========================
class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, index=True)  # trial/active/past_due/canceled
    plan_name = db.Column(db.String(64), nullable=False)
    plan_amount = db.Column(Numeric(12, 2), nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    canceled_at = db.Column(db.DateTime, nullable=True, index=True)
    next_billing_at = db.Column(db.DateTime, nullable=True)

    # 매월 같은 날 청구 기준일(1~31). 말일 이슈는 운영 로직에서 마지막 날로 이월.
    anchor_day = db.Column(db.SmallInteger, nullable=True, index=True)

    # 현재 결제 주기의 범위(대시보드/정산 대조/분쟁에 유용)
    current_period_start = db.Column(db.Date, nullable=True, index=True)
    current_period_end = db.Column(db.Date, nullable=True, index=True)

    # 기본 결제수단(FK)
    default_payment_method_id = db.Column(
        db.Integer, db.ForeignKey("payment_methods.id"), nullable=True, index=True
    )

    __table_args__ = (
        Index("idx_sub_status", "status"),
        Index("idx_sub_created", "created_at"),
        Index("idx_sub_canceled", "canceled_at"),
        Index("idx_sub_user_anchor", "user_id", "anchor_day"),
    )


# =========================
#   CHANGED: Payments (주문/멱등/전문/실패코드/PSP-ID)
# =========================
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # 누가/무엇(구독) 결제인지
    user_id = db.Column(db.String(255), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"), nullable=True, index=True)

    # 결제 공급자/주문 식별
    provider = db.Column(db.String(16), nullable=False, default="toss", index=True)

    # 상점 고유 주문 ID (멱등을 위해 UNIQUE 권장)
    order_id = db.Column(db.String(64), nullable=False, unique=True, index=True)

    # 멱등키(요청 단위로 UNIQUE)
    idempotency_key = db.Column(db.String(80), nullable=False, unique=True, index=True)

    # 금액/통화/상태
    amount = db.Column(Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="KRW")
    status = db.Column(db.String(32), nullable=False, index=True)  # pending/captured/failed/refunded/...

    # PSP(토스) 식별자 및 결과 메타
    psp_transaction_id = db.Column(db.String(64), nullable=True, index=True)
    failure_code = db.Column(db.String(64), nullable=True)
    failure_message = db.Column(db.Text, nullable=True)

    # 전문(민감정보 마스킹하여 저장)
    raw_request = db.Column(JSONB, nullable=True)
    raw_response = db.Column(JSONB, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_pay_user_created", "user_id", "created_at"),
        Index("idx_pay_status_created", "status", "created_at"),
        Index("idx_pay_provider_txid", "provider", "psp_transaction_id"),
    )


# =========================
#   NEW: Webhook Events (단일 진실 원천, 멱등)
# =========================
class WebhookEvent(db.Model):
    """
    토스 웹훅 멱등/감사 로그
    - event_id: 헤더/바디 조합으로 고유값 구성(UNIQUE)
    - signature_valid: 서명/전송ID 검증 결과
    - processed: 비즈니스 로직 반영 여부(멱등)
    """
    __tablename__ = "webhook_events"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(128), nullable=False, unique=True, index=True)
    event_type = db.Column(db.String(64), nullable=True, index=True)

    signature_valid = db.Column(db.Boolean, nullable=False, default=True)
    payload = db.Column(JSONB, nullable=True)

    processed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    processed_at = db.Column(db.DateTime, nullable=True, index=True)
    received_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)


# =========================
#    NEW: Usage Quotas (로그인/구독 — 월간)
# =========================
class Usage(db.Model):
    """
    기능별 월간 사용량
      - scope: "rewrite" | "summarize" (기능 구분)
      - window_start: 매월 1일(UTC) 00:00:00 (Date)
    """
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
#    NEW: AnonymousUsage (비로그인 — 일간)
# =========================
class AnonymousUsage(db.Model):
    """
    비로그인 일간 사용량
      - scope: "rewrite" | "summarize"
      - window_start: 매일(UTC) 00:00:00 (DateTime)
    """
    __tablename__ = "anon_usage"

    id = db.Column(db.Integer, primary_key=True)
    anon_key = db.Column(db.String(255), nullable=False, index=True)
    ip = db.Column(db.String(45), nullable=True)
    scope = db.Column(db.String(32), nullable=False, default="rewrite", index=True)
    window_start = db.Column(db.DateTime, nullable=False, index=True)
    count = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("anon_key", "scope", "window_start",
                         name="uq_anon_key_scope_window"),
        Index("idx_anon_window", "window_start"),
        Index("ix_anon_scope_window", "scope", "window_start"),
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
