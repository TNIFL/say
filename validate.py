import re


def validate_user_id(uid):
    return re.match(r'^[a-z0-9_.-]{3,30}$', uid)
