# utils/time_windows.py
from datetime import datetime, timedelta, timezone, date

def utcnow():
    return datetime.utcnow().replace(tzinfo=timezone.utc)

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
