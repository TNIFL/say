"""
security.py — 입력 검증 및 프롬프트 인젝션 방지 유틸
Lexinoa (Flask)
"""

import re
import html
from functools import wraps
from flask import request, abort, g
from jsonschema import validate, ValidationError

# -------------------- 설정 상수 --------------------
MAX_PAYLOAD_BYTES = 256 * 1024  # 256KB 제한

# -------------------- 유틸 함수 --------------------
def _form_to_dict(formdata):
    """MultiDict → 일반 dict 변환 (getlist 포함)"""
    result = {}
    for k in formdata.keys():
        vals = formdata.getlist(k)
        result[k] = vals if len(vals) > 1 else (vals[0] if vals else None)
    return result


def _sanitize_payload(value, for_llm=False):
    """
    문자열/리스트/딕셔너리를 재귀적으로 정화.
    for_llm=True: prompt injection 탐지 활성화.
    """
    if isinstance(value, str):
        protected = {}

        # [ ... ] 로 감싼 부분은 보호
        def _protect(m):
            key = f"__PROT{len(protected)}__"
            protected[key] = m.group(0)
            return key

        temp = re.sub(r"\[[^\[\]]*\]", _protect, value)

        # HTML 인젝션 방지
        temp = html.escape(temp, quote=True)
        temp = temp.replace("{", "&#123;").replace("}", "&#125;")

        # LLM 프롬프트 인젝션 탐지
        if for_llm:
            lower_temp = temp.lower()
            banned_patterns = [
                "ignore previous instructions",
                "system prompt",
                "act as",
                "inject",
                "jailbreak",
                "roleplay",
                "###",
                "```",
            ]
            for pat in banned_patterns:
                if pat in lower_temp:
                    abort(400, description="LLM prompt injection detected.")

        # 보호 구간 복원
        for key, orig in protected.items():
            temp = temp.replace(key, orig)

        return temp

    elif isinstance(value, list):
        return [_sanitize_payload(v, for_llm=for_llm) for v in value]

    elif isinstance(value, dict):
        return {k: _sanitize_payload(v, for_llm=for_llm) for k, v in value.items()}

    return value


def _validate_schema(data, schema):
    """JSON Schema 검증 (필수 필드, 타입 등)"""
    if not schema:
        return
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        abort(400, description=f"유효성 검사 실패: {e.message}")


def _safe_args(schema=None):
    """GET 쿼리 파라미터에 대해 안전하게 변환 + 검증"""
    args = {}
    for k, v in request.args.items():
        v = v.strip()
        if v:
            args[k] = v
    _validate_schema(args, schema)
    return args


# -------------------- 메인 데코레이터 --------------------
def require_safe_input(json_schema=None, *, form=False, for_llm_fields=None, only_methods=("POST","PUT","PATCH")):
    """
    안전한 입력 검증 데코레이터 (자동 배열 변환 포함)
      - json_schema : JSON 스키마(dict)
      - form=True   : request.form 검사 (HTML 폼)
      - for_llm_fields : LLM 프롬프트 인젝션 탐지 대상 필드 이름 리스트
      - only_methods : 검증을 적용할 메서드 (기본: POST/PUT/PATCH)
    """
    for_llm_fields = set(for_llm_fields or [])
    only_methods = tuple(only_methods or ())

    def deco(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if only_methods and request.method.upper() not in only_methods:
                g.safe_input = None
                return f(*args, **kwargs)

            # 용량 제한
            cl = request.content_length
            if cl and cl > MAX_PAYLOAD_BYTES:
                abort(413, description="요청 본문이 너무 큽니다.")

            # ---- 입력 소스별 파싱 ----
            if form:
                # ✅ HTML form → dict 변환
                payload = _form_to_dict(request.form)

                # ✅ 체크박스 보정
                bool_fields = {"honorific_checked", "opener_checked", "emoji_checked"}
                for b in bool_fields:
                    if b not in payload:
                        payload[b] = False
                    elif isinstance(payload[b], str):
                        payload[b] = payload[b].lower() in ("on", "true", "1", "yes")

            else:
                if not request.is_json:
                    abort(400, description="JSON 요청이 필요합니다.")
                payload = request.get_json(force=True) or {}

            # ---- sanitize + LLM 필드 검사 ----
            safe = {}
            for k, v in payload.items():
                safe[k] = _sanitize_payload(v, for_llm=(k in for_llm_fields))

            # ---- 자동 배열 변환 ----
            if json_schema and "properties" in json_schema:
                for key, prop in json_schema["properties"].items():
                    if key in safe and prop.get("type") == "array":
                        val = safe[key]
                        if isinstance(val, str):
                            safe[key] = [val]
                        elif val is None:
                            safe[key] = []
                        elif not isinstance(val, list):
                            safe[key] = [val]

            # ---- 스키마 검증 ----
            _validate_schema(safe, json_schema)

            # ---- Flask g 에 저장 ----
            g.safe_input = safe
            return f(*args, **kwargs)
        return wrapped
    return deco



# -------------------- 예시 스키마 --------------------
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
