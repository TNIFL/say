# auth.py
from typing import Optional
from flask import g
from models import User, Subscription
from utils.time_windows import utcnow

def get_current_user() -> Optional[User]:
    # 실제 로그인 연동에서 g.current_user를 세팅했다고 가정
    return getattr(g, "current_user", None)

def has_active_subscription(user: User) -> bool:
    if not user:
        return False
    now = utcnow().replace(tzinfo=None)  # DB naive DateTime 대비
    sub = (Subscription.query
           .filter_by(user_id=user.user_id, status="active")
           .first())
    if not sub:
        return False
    if sub.next_billing_at and sub.next_billing_at < now:
        return False
    return True
