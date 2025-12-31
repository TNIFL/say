from typing import Optional
from flask import g
from domain.models import User, Subscription
from utils.time_utils import utcnow
from flask import session
from datetime import datetime

# 현재 사용자를 db에서 가져와 g(flask 전역 공간) 에 저장하는 훅
# 실제 사용할 때 에는 load_current_user를 계속 불러오면 성능저하가 일어나니
# load_current_user를 호출 후 g 에 저장 후
# auth/entitlements 의 get_current_user() 를 불러와 사용

# app.py 가 시작 할 때 load_current_user() 를 호출 후
# 필요 할 때 마다 get_current_user() 로 가져옴
# 세팅할 때 사용
# TODO:: 현재 유저를 가져올 때 정확히 가져오게 해야함
# TODO:: 어드민 계정인데 Guest 로 불러와지는 경우가 있음
# TODO:: flask 의 전역공간인 g 에 현재 유저 티어를 정확하게 저장 시켜야함
def load_current_user():
    sess = session.get("user") or {}
    uid = sess.get("user_id")

    if not uid:
        g.current_user = None
        print("[AUTH][load_current_user] guest")
        return None

    user = User.query.filter_by(user_id=uid).first()
    g.current_user = user

    print(
        "[AUTH][load_current_user]",
        "uid=", uid,
        "found=", bool(user),
        "email=", getattr(user, "email", None)
    )
    return user



# 조회 할 때 사용
def get_current_user() -> Optional[User]:
    # 실제 로그인 연동에서 g.current_user를 세팅했다고 가정
    return getattr(g, "current_user", None)

def has_active_subscription(user: User) -> bool:
    if not user:
        return False

    now = datetime.utcnow()  # naive UTC

    sub = (
        Subscription.query
        .filter(
            Subscription.user_id == user.user_id,
            Subscription.status.in_(("active", "past_due")),  # 재시도 중 포함
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub:
        return False

    # next_billing_at 없는 구독은 불완전 상태로 보고 False(보수적)
    if not sub.next_billing_at:
        return False

    # 다음 결제일이 지났으면, 현재 기간이 끝난 것으로 보고 False
    if sub.next_billing_at <= now:
        return False

    return True