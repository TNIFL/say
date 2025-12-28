from flask import current_app


YMD_RE = r"^\d{4}-\d{2}-\d{2}$"
PATH_ALLOW = ["", "/", "/login", "/signup", "/subscribe", "/history"]
# ===== 입력 검증: 허용 값(enum) =====
CATEGORY_ALLOW = [
    "general",
    "work",
    "support",
    "apology",
    "inquiry",
    "thanks",
    "request",
    "guidance",
    "report/approval",
    "feedback",
]
TONE_ALLOW = [
    "soft",
    "polite",
    "concise",
    "report",
    "friendly",
    "warmly",
    "calmly",
    "formally",
    "clearly",
    "without_emotion",
]
PROVIDER_ALLOW = ["claude", "openai", "gemini"]
USAGE_SCOPES = {"rewrite", "summarize"}

# -------------------- 입력 양식 스키마 --------------------
polish_input_schema = {
    "type": "object",
    "properties": {
        "input_text": {"type": "string", "minLength": 1, "maxLength": 4000},
        "selected_categories": {"type": "array", "items": {"type": "string"}},
        "selected_tones": {"type": "array", "items": {"type": "string"}},
        "honorific_checked": {"type": ["boolean", "string", "null"]},
        "opener_checked": {"type": ["boolean", "string", "null"]},
        "emoji_checked": {"type": ["boolean", "string", "null"]},
        "provider": {"type": "string"},
    },
    "required": ["input_text"],
    "additionalProperties": True,
}

login_schema = {
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "minLength": 2, "maxLength": 30},
        "password": {"type": "string", "minLength": 4, "maxLength": 100},
        "remember": {"type": ["string", "null"], "enum": ["on", None]},
    },
    "required": ["user_id", "password"],
    "additionalProperties": True,
}

signup_schema = {
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "minLength": 2, "maxLength": 30},
        "email": {"type": "string", "format": "email"},
        "password": {"type": "string", "minLength": 4, "maxLength": 100},
        "confirm": {"type": "string", "minLength": 4, "maxLength": 100},
        "agree": {"type": ["string", "boolean", "null"]},
    },
    "required": ["user_id", "email", "password", "confirm"],
    "additionalProperties": True,
}

feedback_schema = {
    "type": "object",
    "properties": {
        "email": {"type": ["string", "null"], "maxLength": 100},
        "user_id": {"type": ["string", "null"], "maxLength": 30},
        "category": {
            "type": "string",
            "enum": ["general", "bug", "ux", "idea", "other"],
        },
        "message": {"type": "string", "minLength": 1, "maxLength": 2000},
        "page": {"type": ["string", "null"], "maxLength": 255},
    },
    "required": ["message"],
    "additionalProperties": True,
}

admin_visits_query_schema = {
    "type": "object",
    "properties": {
        "from": {"type": ["string", "null"], "pattern": YMD_RE},
        "to": {"type": ["string", "null"], "pattern": YMD_RE},
        "path": {"type": ["string", "null"], "enum": PATH_ALLOW},
        "user": {"type": ["string", "null"], "maxLength": 120},
    },
    "additionalProperties": True,
}

admin_data_query_schema = {
    "type": "object",
    "properties": {
        "date_from": {"type": ["string", "null"], "pattern": YMD_RE},
        "date_to": {"type": ["string", "null"], "pattern": YMD_RE},
        "days": {"type": ["string", "null"], "pattern": r"^\d{1,3}$"},
        "path": {"type": ["string", "null"]},
        "user_id": {"type": ["string", "null"], "maxLength": 120},
    },
    "additionalProperties": True,
}
# ===== JSON API( /api/polish ) POST 스키마 =====

api_polish_schema = {
    "type": "object",
    "properties": {
        "input_text": {"type": "string", "minLength": 1, "maxLength": 4000},
        "selected_categories": {
            "type": "array",
            "items": {"type": "string", "enum": CATEGORY_ALLOW},
            "maxItems": 10,
        },
        "selected_tones": {
            "type": "array",
            "items": {"type": "string", "enum": TONE_ALLOW},
            "maxItems": 5,
        },
        "honorific_checked": {"type": ["boolean", "string", "null"]},
        "opener_checked": {"type": ["boolean", "string", "null"]},
        "emoji_checked": {"type": ["boolean", "string", "null"]},
        "provider": {"type": "string", "enum": PROVIDER_ALLOW},
    },
    "required": ["input_text"],
    "additionalProperties": True,
}

# ===== 피드백 폼( /feedback ) POST 스키마 =====
feedback_schema_ = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["general", "bug", "ux", "idea", "other"],
        },
        "user_id": {"type": ["string", "null"], "maxLength": 64},
        "email": {
            "type": ["string", "null"],
            "maxLength": 254,
            "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        },
        "message": {"type": "string", "minLength": 1, "maxLength": 4000},
        "page": {"type": ["string", "null"], "maxLength": 256},
    },
    "required": ["category", "message"],
    "additionalProperties": True,
}

# ===== 메인 폼( / ) POST 스키마 (HTML form) =====
polish_form_schema = {
    "type": "object",
    "properties": {
        "input_text": {"type": "string", "minLength": 1, "maxLength": 4000},
        "categories": {
            "type": "array",
            "items": {"type": "string", "enum": CATEGORY_ALLOW},
            "maxItems": 10,
        },
        "tones": {
            "type": "array",
            "items": {"type": "string", "enum": TONE_ALLOW},
            "maxItems": 5,
        },
        "honorific": {"type": ["string", "boolean", "null"]},
        "opener": {"type": ["string", "boolean", "null"]},
        "emoji": {"type": ["string", "boolean", "null"]},
        "provider": {"type": "string", "enum": PROVIDER_ALLOW},
    },
    "required": ["input_text"],
    "additionalProperties": True,
}