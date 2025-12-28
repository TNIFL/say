# policies.py
TIERS = ("guest", "free", "pro")

FEATURES_BY_TIER = {
    "guest": {"rewrite.single"},
    "free": {"rewrite.single", "rewrite.multi", "preview.compare3", "chrome.ext", "tone.autodetect"},
    "pro":  {"*"},  # 모든 기능 허용
}

LIMITS = {
    "guest": {"daily": 5},
    "free": {"monthly": 30},
    "pro":  {"monthly": 1000},  # 페어유스 상한
}
