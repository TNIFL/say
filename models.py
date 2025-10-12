# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.String(255), unique=True, nullable=False, index=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    rewrites = db.relationship(
        "RewriteLog",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="RewriteLog.user_pk",  # 관계는 user_pk 기준
    )


class RewriteLog(db.Model):
    __tablename__ = "rewrite_logs"

    id = db.Column(db.Integer, primary_key=True)

    # 관계용 FK (users.id)
    user_pk = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # 사람이 쓰는 아이디(문자열)도 별도로 저장
    user_id = db.Column(db.String(50), nullable=True, index=True)

    input_text = db.Column(db.Text, nullable=False)
    output_text = db.Column(db.Text)

    categories = db.Column(db.JSON, nullable=False, default=list)
    tones = db.Column(db.JSON, nullable=False, default=list)

    honorific = db.Column(db.Boolean, default=False, nullable=False)
    opener = db.Column(db.Boolean, default=False, nullable=False)
    emoji = db.Column(db.Boolean, default=False, nullable=False)

    model_name = db.Column(db.String(64))
    request_ip = db.Column(db.String(45))
    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    # 로그인 안 한 사용자도 허용 (세션 user_id 없을 수 있음)
    user_id = db.Column(db.String(255), index=True, nullable=True)
    email = db.Column(db.String(255), nullable=True)

    category = db.Column(db.String(50), nullable=False, default="general")  # general, ux, bug, idea 등
    message = db.Column(db.Text, nullable=False)                            # 피드백 본문
    page = db.Column(db.String(255), nullable=True)                         # 제출 위치(선택)

    resolved = db.Column(db.Boolean, default=False, nullable=False)         # 처리 여부(추후 관리자용)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
