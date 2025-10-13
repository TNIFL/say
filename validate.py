import re


def validate_user_id(uid):
    return re.match(r'^[a-z0-9_.-]{3,30}$', uid)


def validate_user_password(password):
    return re.match(r'^[a-z0-9_.-]{3,30}$', password)
