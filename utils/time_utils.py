# utils/time_utils.py
from datetime import datetime, timedelta, timezone, date

# 시간
KST = timezone(timedelta(hours=9))

def utcnow():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

def _utcnow():
    return datetime.now(timezone.utc)

def _to_utc_aware(dt):
    if dt is None:
        return None
    return (
        dt.replace(tzinfo=timezone.utc)
        if (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None)
        else dt.astimezone(timezone.utc)
    )

def _day_window(dt: datetime):
    start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def _month_window(dt: datetime):
    start = date(dt.year, dt.month, 1)
    if dt.month == 12:
        end = date(dt.year + 1, 1, 1)
    else:
        end = date(dt.year, dt.month + 1, 1)
    return start, end


def day_window(dt: datetime):
    start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end

def month_window(dt: datetime):
    start = date(dt.year, dt.month, 1)
    if dt.month == 12:
        end = date(dt.year + 1, 1, 1)
    else:
        end = date(dt.year, dt.month + 1, 1)
    return start, end


def _compute_anchor_day(now_kst=None):
    kst = now_kst or datetime.now(KST)
    return kst.day