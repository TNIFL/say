# utils/billing_dates.py
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

def to_utc_naive(dt_aware: datetime) -> datetime:
    """aware datetime -> naive UTC datetime (DB timezone=False 전제)"""
    return dt_aware.astimezone(timezone.utc).replace(tzinfo=None)

def next_billing_kst(now_kst: datetime, anchor_day: int) -> datetime:
    """
    now_kst 기준으로 '다음 달 anchor_day'의 KST datetime 반환.
    - dateutil이 말일(28/29/30/31) 보정을 자동 처리.
    - 시간은 now_kst의 시:분:초를 유지.
    """
    # 다음 달로 이동한 뒤 day를 anchor_day로 맞춤(말일 보정 포함)
    base = now_kst.replace(day=1)
    nxt = base + relativedelta(months=+1, day=anchor_day,
                               hour=now_kst.hour, minute=now_kst.minute, second=now_kst.second,
                               microsecond=0)
    return nxt
