
import hashlib
from datetime import datetime, timedelta, timezone, date
from functools import wraps
import os, time, secrets
import random
import smtplib
import socket
from threading import Thread
import base64
import uuid

import requests
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, session, redirect, url_for,
    jsonify, abort, g, current_app, make_response
)
from flask_cors import CORS
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeSerializer
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from email.message import EmailMessage
from sqlalchemy import func, and_
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from models import (
    db,
    RewriteLog,
    Feedback,
    User,
    Subscription,
    Usage,
    AnonymousUsage as GuestUsage,  # ✅ DB 모델은 alias로 사용
    UserTemplate,
    Payment,
    Visit,
    PasswordResetToken
)
from login import auth_bp
from signup import signup_bp
from build_prompt import build_prompt
from generator import claude_prompt_generator
from toss_error import translate_toss_error

# -------------------- 기본 설정 --------------------
load_dotenv()
migrate = Migrate()
csrf = CSRFProtect()

# 비밀번호 재설정
RESET_SALT = "password-reset-v1"
RESET_TTL = 60 * 5  # 5m(메일인증 시간)

# ✅ Redis 저장소 기반 레이트리밋(운영 필수)
REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per hour"],  # 기본 전역 리미트
        storage_uri=REDIS_URL,            # ✅ Redis 연동
    )
else:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per hour"],
        storage_uri="memory://",          # ✅ 개발/임시용
    )

KST = timezone(timedelta(hours=9))
PROVIDER_DEFAULT = os.getenv("PROVIDER_DEFAULT", "claude").lower()

# NOTE: 운영에선 DB의 users.is_admin만 신뢰 권장
ADMIN_ID = os.getenv("ADMIN_ID", "")

# CORS 허용 도메인(확장/프런트). 쉼표로 구분
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "https://www.lexinoa.com").split(",")
    if o.strip()
]

# API 허용 오리진(Origin/Referer에서 검사)
API_ALLOWED_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv(
        "API_ALLOWED_ORIGINS",
        "https://www.lexinoa.com,http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:5000",
    ).split(",")
    if o.strip()
]

# =========================
#  [추가] 티어/권한/한도 정책
# =========================
TIERS = ("guest", "free", "pro")

FEATURES_BY_TIER = {
    "guest": {"rewrite.single", "summarize"},  # 비로그인: 단일문장만
    "free": {"rewrite.single", "summarize", "chrome.ext"},
    "pro": {"*"},  # 구독: 모든 기능
}

LIMITS = {
    "guest": {"daily": 5},    # 하루 5회 (✅ scope별 한도 — rewrite / summarize 각각 5회)
    "free": {"monthly": 30},  # 월 30회 (✅ scope별)
    "pro": {"monthly": 1000}, # 월 1000회 (✅ scope별)
}

AID_COOKIE = "aid"

# reCAPTCHA v2
RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET_KEY")
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")

# 전역 기본 소켓 타임아웃을 짧게
socket.setdefaulttimeout(5)

# 응답시간 평탄화
MIN_RESP_MS = 450  # 450 ~ 650ms 사이로 랜덤 지연
JITTER_MS = 200

# (5분, 이메일로 비밀번호 변경 인증 토큰)
RESET_TOKEN_BYTES = 32
RESET_TOKEN_TTL_SECONDS = 60 * 5  # 5 minutes

# 이메일 인증
VERIFY_SALT = "email-verify-v1"
VERIFY_TTL_SECONDS = 60 * 30  # 5분 유효

# ✅ 허용 스코프(서비스 키) — 여기 추가하면 확장 가능
USAGE_SCOPES = {"rewrite", "summarize"}

# 토스 API 키
TOSS_API_BASE = os.getenv("TOSS_API_BASE", "https://api.tosspayments.com").rstrip("/")
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")
TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY", "")

# 엔드포인트 경로(문서와 대조하여 필요시 수정)
TOSS_PATH_ISSUE_BILLING = "/v1/billing/authorizations/issue"     # authKey+customerKey → billingKey
TOSS_PATH_PAY_WITH_BILLING = "/v1/billing/payments"              # billingKey 결제
# (참고) 카드 등록용 위젯은 프론트에서 clientKey로 초기화, successUrl/failUrl로 콜백

# --- Ads (feature flags & providers) ---
ADS_ENABLED = os.getenv("ADS_ENABLED", "false").lower() in {"1", "true", "yes"}
ADS_PROVIDER = os.getenv("ADS_PROVIDER", "adsense")  # adsense | kakao | naver
# Google AdSense
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "")  # e.g. ca-pub-xxxxxxxxxxxxxxxx
# Kakao AdFit
ADFIT_UNIT_ID = os.getenv("ADFIT_UNIT_ID", "")    # e.g. DAN-xxxxxxxxxxxx
# Naver
NAVER_AD_UNIT = os.getenv("NAVER_AD_UNIT", "")    # 필요시 유닛/클라이언트 ID
# ads.txt / app-ads.txt(옵션): env 문자열 또는 파일 경로
ADS_TXT = os.getenv("ADS_TXT", "")                # 직접 텍스트 넣거나 빈값
APP_ADS_TXT = os.getenv("APP_ADS_TXT", "")

# 상단 설정 근처
EXTENSION_IDS = [x.strip() for x in os.getenv("EXTENSION_IDS", "").split(",") if x.strip()]
EXT_ORIGINS = ["chrome-extension://*"]


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


def _guest_serializer(secret_key: str):
    return URLSafeSerializer(secret_key=secret_key or "dev-secret", salt="guest-key-v1")


def ensure_guest_cookie():
    """
    게스트 식별 쿠키(aid)를 '항상 같은 규칙'으로 보장한다.
    - 유효한 서명 쿠키가 있으면: (키, False)
    - 없거나(미보유) / 서명 무효이면: (새 키, True)
    """
    s = _guest_serializer(current_app.config.get("SECRET_KEY"))
    cur = request.cookies.get(AID_COOKIE)
    if cur:
        try:
            s.loads(cur)  # 서명 검증 (성공하면 cur 그대로 사용)
            return cur, False
        except Exception:
            pass  # 무효 → 새로 발급

    raw = secrets.token_urlsafe(24)
    signed = s.dumps(raw)
    return signed, True


def set_guest_cookie(resp, aid_value: str):
    # http 로컬 개발환경에서도 동작하도록 secure 자동 전환
    is_secure = request.is_secure or current_app.config.get("PREFERRED_URL_SCHEME", "https") == "https"
    resp.set_cookie(
        AID_COOKIE,
        aid_value,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
    )
    return resp


def get_current_user():
    """
    세션에서 user_id를 읽어 DB의 User 객체를 반환.
    (별도의 로그인 로직은 기존 auth_bp가 담당)
    """
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if not uid:
        return None
    return User.query.filter_by(user_id=uid).first()


def has_active_subscription(user: User) -> bool:
    if not user:
        return False
    sub = Subscription.query.filter_by(user_id=user.user_id, status="active").first()
    if not sub:
        return False
    now_utc = _utcnow()
    next_at = _to_utc_aware(sub.next_billing_at)
    if next_at and next_at < now_utc:
        return False
    return True


def resolve_tier():
    if g.get("is_admin"):
        return "pro"
    user = get_current_user()
    if not user:
        return "guest"
    return "pro" if has_active_subscription(user) else "free"


def outputs_for_tier():
    tier = resolve_tier()
    return 3 if tier == "pro" else 1


def _as_text_from_claude_result(result) -> str:
    """
    claude_prompt_generator.call_claude(...) 반환값 정규화
    """
    if result is None:
        return ""
    if isinstance(result, tuple) and len(result) >= 1:
        return str(result[0] or "")
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("text") or result.get("content") or "")
    return str(result or "")


def _ensure_exact_count(outputs, count):
    """
    결과 개수 정확히 맞추기:
      - 공백/빈값 제거
      - (count>1) 중복 제거
      - 모자라면 마지막 문장 복제
      - 많으면 앞에서 count개만
    """
    out = [(o or "").strip() for o in (outputs or []) if (o or "").strip()]
    if count > 1:
        seen, uniq = set(), []
        for o in out:
            k = " ".join(o.lower().split())
            if k in seen:
                continue
            seen.add(k)
            uniq.append(o)
        out = uniq
    if len(out) < count:
        while len(out) < count:
            out.append(out[-1] if out else "(빈 결과)")
    else:
        out = out[:count]
    return out


def feature_allowed(tier: str, feature_key: str) -> bool:
    allowed = FEATURES_BY_TIER.get(tier, set())
    return "*" in allowed or feature_key in allowed


def require_feature(feature_key: str):
    """기능 권한 게이트: 허용되지 않으면 403"""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            tier = resolve_tier()
            if not feature_allowed(tier, feature_key):
                return (
                    jsonify(
                        {"error": "feature_not_allowed", "feature": feature_key, "tier": tier}
                    ),
                    403,
                )
            return view(*args, **kwargs)

        return wrapper

    return decorator


def enforce_quota(scope: str, methods=("POST",)):
    """
    사용량 게이트(성공시에만 +1)
    ✅ scope별로 별도 카운트/한도 적용
      - guest: daily (GuestUsage)
      - free/pro: monthly (Usage[Date])
    - methods: 해당 HTTP 메서드에만 실행 (기본 POST)
    """
    assert scope in USAGE_SCOPES, f"Unknown scope '{scope}'"

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if methods and request.method.upper() not in {m.upper() for m in methods}:
                return view(*args, **kwargs)

            tier = resolve_tier()
            now = _utcnow()

            if tier == "guest":
                guest_key, need_set = ensure_guest_cookie()
                day_start, _ = _day_window(now)

                from psycopg2._psycopg import IntegrityError
                try:
                    with db.session.begin_nested():
                        row = (
                            GuestUsage.query.filter(
                                and_(
                                    GuestUsage.anon_key == guest_key,
                                    GuestUsage.scope == scope,
                                    GuestUsage.window_start == day_start,
                                )
                            )
                            .with_for_update(nowait=False)
                            .first()
                        )

                        # 아직 row 없으면 새로 만들기 (여기서 race가 날 수 있음)
                        if not row:
                            row = GuestUsage(
                                anon_key=guest_key,
                                ip=request.remote_addr,
                                scope=scope,
                                window_start=day_start,
                                count=0,
                            )
                            db.session.add(row)
                            db.session.flush()

                        limit = LIMITS["guest"]["daily"]
                        if row.count >= limit:
                            resp = jsonify(
                                {
                                    "error": "daily_limit_reached",
                                    "limit": limit,
                                    "scope": scope,
                                }
                            )
                            resp.status_code = 429
                            if need_set:
                                resp = set_guest_cookie(make_response(resp), guest_key)
                            return resp

                except IntegrityError:
                    # 여기로 온다는 건, 방금 INSERT 경쟁에서 졌다는 뜻
                    db.session.rollback()
                    # 이미 다른 트랜잭션이 row를 만든 상태이므로 그냥 다시 가져오기만
                    with db.session.begin_nested():
                        row = (
                            GuestUsage.query.filter(
                                and_(
                                    GuestUsage.anon_key == guest_key,
                                    GuestUsage.scope == scope,
                                    GuestUsage.window_start == day_start,
                                )
                            )
                            .with_for_update(nowait=False)
                            .one()
                        )
                        limit = LIMITS["guest"]["daily"]
                        if row.count >= limit:
                            resp = jsonify(
                                {
                                    "error": "daily_limit_reached",
                                    "limit": limit,
                                    "scope": scope,
                                }
                            )
                            resp.status_code = 429
                            if need_set:
                                resp = set_guest_cookie(make_response(resp), guest_key)
                            return resp
                # 여기까지가 "limit 확인" 단계

                resp = view(*args, **kwargs)

                with db.session.begin_nested():
                    row = (
                        GuestUsage.query.filter(
                            and_(
                                GuestUsage.anon_key == guest_key,
                                GuestUsage.scope == scope,
                                GuestUsage.window_start == day_start,
                            )
                        )
                        .with_for_update(nowait=False)
                        .one()
                    )
                    row.count += 1
                db.session.commit()

                if need_set:
                    if not hasattr(resp, "set_cookie"):
                        resp = make_response(resp)
                    resp = set_guest_cookie(resp, guest_key)
                return resp

            # ===== free / pro (월간 집계 — Date window) =====
            month_start, _ = _month_window(now)
            user = get_current_user()
            if not user:
                return jsonify({"error": "auth_required"}), 401

            tier_key = "pro" if tier == "pro" else "free"

            with db.session.begin_nested():
                row = (
                    Usage.query.filter(
                        and_(
                            Usage.user_id == user.user_id,
                            Usage.tier == tier_key,
                            Usage.scope == scope,                # ✅ scope 포함
                            Usage.window_start == month_start,
                        )
                    )
                    .with_for_update(nowait=False)
                    .first()
                )
                if not row:
                    row = Usage(
                        user_id=user.user_id,
                        tier=tier_key,
                        scope=scope,                            # ✅ 신규 row에 scope 저장
                        window_start=month_start,
                        count=0,
                    )
                    db.session.add(row)
                    db.session.flush()

                limit = LIMITS[tier]["monthly"]
                if row.count >= limit:
                    return jsonify({"error": "monthly_limit_reached", "limit": limit, "scope": scope}), 429

            resp = view(*args, **kwargs)

            with db.session.begin_nested():
                row = (
                    Usage.query.filter(
                        and_(
                            Usage.user_id == user.user_id,
                            Usage.tier == tier_key,
                            Usage.scope == scope,                # ✅ scope 포함
                            Usage.window_start == month_start,
                        )
                    )
                    .with_for_update(nowait=False)
                    .one()
                )
                row.count += 1
            db.session.commit()
            return resp

        return wrapper
    return decorator


# 비밀번호 재설정을 위한 함수
def _reset_serializer(app):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=RESET_SALT)


# 비밀번호 재설정 링크 보내주는 함수
def _send_email_reset_link_sync(email, link):
    """
    SMTP 설정이 없으면 콘솔에 링크만 출력합니다.
    실제 SMTP 쓰려면: smtplib/메일서비스 연동으로 교체.
    """
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM", "lexinoakr@gmail.com")
    msg["To"] = email
    msg["Subject"] = "[Lexinoa] 비밀번호 재설정 링크"
    msg.set_content(f"아래 링크로 접속하여 비밀번호를 재설정하세요 (5분 유효)\n{link}")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")

    try:
        with smtplib.SMTP(host, port, timeout=5) as s:
            s.starttls(context=None)
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
        print(f"[PASSWORD RESET] To: {email}\nLink: {link}\n")
        return True
    except Exception as e:
        print("[MAIL][ERROR]", repr(e))
        return False


def send_email_reset_link_async(email, link):
    Thread(target=_send_email_reset_link_sync, args=(email, link), daemon=True).start()


# reCAPTCHA v2
def verify_recaptcha_v2(response_token, remote_ip=None):
    payload = {"secret": RECAPTCHA_SECRET, "response": response_token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        r = requests.post(
            "https://www.google.com/recaptcha/api/siteverify", data=payload, timeout=5
        )
        result = r.json()
        return result.get("success", False)
    except Exception as e:
        print("reCAPTCHA verification failed:", e)
        return False


# 응답시간 평탄화
def _sleep_floor(start_t):
    elapsed_ms = int((time.perf_counter() - start_t) * 1000)
    floor = MIN_RESP_MS + random.randint(0, JITTER_MS)
    if elapsed_ms < floor:
        time.sleep((floor - elapsed_ms) / 1000.0)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_password_reset_token(user, *, ttl_seconds=60 * 5):
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    now = _utcnow()
    row = PasswordResetToken(
        user_pk=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(seconds=ttl_seconds),
        created_at=now,
        created_ip=(request.remote_addr or None),
        created_ua=(request.headers.get("User-Agent") or None)[:500],
    )
    db.session.add(row)
    db.session.commit()
    return raw


def verify_password_reset_token(raw: str):
    token_hash = _hash_token(raw)
    row = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not row:
        return None, None, "invalid"
    if row.used_at is not None:
        return None, None, "used"
    # Fix: Ensure row.expires_at is timezone-aware before comparison
    expires_at_aware = row.expires_at
    if expires_at_aware.tzinfo is None: # If it's naive
        expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc) # Assume it's UTC naive

    if expires_at_aware < _utcnow(): # Compare aware datetimes
        return None, None, "expired"
    user = User.query.get(row.user_pk)
    if not user:
        return None, None, "invalid"
    return row, user, "ok"


def consume_password_reset_token(row):
    row.used_at = _utcnow()
    db.session.add(row)
    db.session.commit()


def _verify_serializer(app):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=VERIFY_SALT)


def _send_email_verify_link_sync(email, link):
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM", "lexinoakr@gmail.com")
    msg["To"] = email
    msg["Subject"] = "[Lexinoa] 이메일 인증 링크"
    msg.set_content(f"아래 링크에서 이메일 인증을 완료해 주세요. (30분 유효)\n{link}")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")

    try:
        with smtplib.SMTP(host, port, timeout=5) as s:
            s.starttls(context=None)
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
        print(f"[EMAIL VERIFY] To: {email}\nLink: {link}\n")
    except Exception as e:
        print("[MAIL][ERROR][VERIFY]", repr(e))


def send_email_verify_link_async(email, link):
    Thread(target=_send_email_verify_link_sync, args=(email, link), daemon=True).start()


def create_email_verify_token(user):
    s = _verify_serializer(current_app)
    payload = {"uid": user.user_id, "email": user.email}
    return s.dumps(payload)


def verify_email_token(raw):
    s = _verify_serializer(current_app)
    try:
        data = s.loads(raw, max_age=VERIFY_TTL_SECONDS)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"

    uid = (data or {}).get("uid")
    mail = (data or {}).get("email")
    if not uid or not mail:
        return None, "invalid"

    user = User.query.filter_by(user_id=uid).first()
    if not user or user.email.lower() != str(mail).lower():
        return None, "invalid"
    return user, "ok"


# 토스 연결부
def toss_request(method: str, path: str, json_body: dict):
    url = f"{TOSS_API_BASE}{path}"
    r = requests.request(method.upper(), url, headers=_toss_headers(), json=json_body, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if not r.ok:
        # 실패 응답도 그대로 넘겨서 DB에 적재/디버깅 가능하게
        raise RuntimeError(f"Toss API error {r.status_code}: {data}")
    return data

def _new_order_id(prefix="sub"):
    # 상점 고유 주문ID (UNIQUE) — 환불/정산/분쟁 추적에 필요
    return f"{prefix}_{uuid.uuid4().hex[:24]}"

def _new_idempo():
    return uuid.uuid4().hex

def _compute_anchor_day(now_kst=None):
    kst = now_kst or datetime.now(KST)
    return kst.day


def _toss_headers():
    # Basic {base64(SECRET_KEY:)} 형식 (뒤의 콜론 주의)
    b64 = base64.b64encode((TOSS_SECRET_KEY + ":").encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/json",
    }



def create_app():
    from security import (
        require_safe_input,
        polish_input_schema,
        feedback_schema,
    )  # 👈 함수 안 import (순환참조 회피)

    app = Flask(__name__)
    app.config.from_object(Config)

    # --- 필수: 강력한 SECRET_KEY ---
    app.secret_key = app.config.get("SECRET_KEY")
    assert (
        app.secret_key and app.secret_key != "dev-secret-change-me"
    ), "SECURITY: 환경변수 SECRET_KEY를 강력한 값으로 설정하세요."

    # --- 세션/쿠키 보안 ---
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",  # 확장/타도메인에서 폼 제출 필요하면 'None'
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    # --- 프록시 신뢰(HTTPS 판단) ---
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # --- DB/Migrate ---
    db.init_app(app)
    migrate.init_app(app, db)

    # --- OpenAI 클라이언트 (원하면 주석 해제)
    # from openai import OpenAI
    # app.openai_client = OpenAI(api_key=os.getenv("GPT_API_KEY"), timeout=15.0)

    # --- CORS (API 엔드포인트만) ---
    CORS(
        app,
        supports_credentials=True,
        resources={
            r"/api/*": {
                "origins": CORS_ORIGINS + EXT_ORIGINS,
                "methods": ["POST", "GET", "DELETE"],
                "allow_headers": ["Content-Type", "Authorization", "X-Lex-Client"],
            }
        },
    )

    # --- CSRF ---
    csrf.init_app(app)

    # --- 레이트리밋 ---
    limiter.init_app(app)

    # --- 블루프린트 ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)
    print("create_app() 진입")

    def nocache(view):
        @wraps(view)
        def _wrapped(*args, **kwargs):
            rv = view(*args, **kwargs)
            if isinstance(rv, tuple):
                data, status, headers = (rv + (None, None))[0:3]
                resp = make_response(data, status, headers)
            else:
                resp = make_response(rv)
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            return resp
        return _wrapped

    # -------------------- 유틸 --------------------
    def _retry(fn, tries=3, base_delay=0.4):
        """지수 백오프 간단 재시도"""
        last_exc = None
        for i in range(tries):
            try:
                return fn()
            except Exception as e:
                last_exc = e
                time.sleep(base_delay * (2 ** i))
        raise last_exc

    def call_openai_and_log(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
        *,
        n_outputs=1,
    ):
        outputs = []
        prompt_tokens = completion_tokens = total_tokens = None
        model_name = "gpt-4.1"

        system_prompt, final_user_prompt = build_prompt(
            input_text,
            selected_categories,
            selected_tones,
            honorific_checked,
            opener_checked,
            emoji_checked,
        )

        start = time.perf_counter()
        try:
            def _do():
                temp = 0.4 if int(n_outputs) == 1 else 0.85
                top_p = 1.0 if int(n_outputs) == 1 else 0.95
                return app.openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                final_user_prompt
                                if int(n_outputs) == 1
                                else final_user_prompt
                                     + "\n\n같은 의미를 유지하되, 문장 표현이 서로 다른 한국어 문장 1개를 만들어주세요.\n"
                                     "단어 선택, 어순, 문체, 문장 길이 등을 다양하게 바꿔주세요.\n"
                                     "너무 유사하거나 번역투 느낌이 나는 결과는 피해주세요."
                            ),
                        },
                    ],
                    temperature=temp,
                    top_p=top_p,
                    presence_penalty=0.6 if int(n_outputs) > 1 else 0.0,
                    frequency_penalty=0.4 if int(n_outputs) > 1 else 0.0,
                    max_tokens=300,
                    n=max(1, int(n_outputs)),
                )

            completion = _retry(_do)
            for ch in (completion.choices or []):
                content = getattr(getattr(ch, "message", None), "content", None)
                text = (content or "").strip()
                if text:
                    outputs.append(text)
            usage = getattr(completion, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
                total_tokens = getattr(usage, "total_tokens", None)
        except Exception:
            outputs = []
        latency_ms = int((time.perf_counter() - start) * 1000)

        # 로그 저장
        try:
            sess = session.get("user") or {}
            uid = sess.get("user_id")
            request_ip = request.remote_addr

            log = RewriteLog(
                user_pk=None,
                user_id=uid,
                input_text=input_text,
                output_text=(outputs[0] if outputs else "(에러/빈 응답)"),
                categories=selected_categories or [],
                tones=selected_tones or [],
                honorific=bool(honorific_checked),
                opener=bool(opener_checked),
                emoji=bool(emoji_checked),
                model_name=model_name,
                request_ip=request_ip,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            if uid:
                u = User.query.filter_by(user_id=uid).first()
                if u:
                    log.user_pk = u.id

            if hasattr(RewriteLog, "model_latency_ms"):
                setattr(log, "model_latency_ms", latency_ms)

            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            db.session.rollback()
            print("[rewrite log save error]", log_err)

        return outputs

    def call_claude_and_log(
        input_text,
        selected_categories,
        selected_tones,
        honorific_checked,
        opener_checked,
        emoji_checked,
        *,
        n_outputs=1,
    ):
        """
        Claude 호출 (결과 개수 고정형)
        """
        outputs = []
        model_name = "claude"

        try:
            system_prompt, final_user_prompt = build_prompt(
                input_text,
                selected_categories,
                selected_tones,
                honorific_checked,
                opener_checked,
                emoji_checked,
            )
            count = max(1, int(n_outputs))

            variant_prompt = (
                f"{final_user_prompt}\n\n"
                f"위 문장을 바탕으로, 같은 의미를 유지하되 표현 방식이 다른 "
                f"한국어 문장 {count}개를 만들어주세요.\n"
                f"각 문장은 한 줄짜리로, 단락 없이 깔끔하게 써주세요.\n"
                f"출력 형식은:\n"
                f"1) 문장1\n2) 문장2\n3) 문장3\n형태로 주세요."
            )

            def _do():
                return claude_prompt_generator.call_claude(system_prompt, variant_prompt)

            result = _retry(_do)
            text = _as_text_from_claude_result(result).strip()

            lines = [l.strip(" -•*0123456789.)\t") for l in text.splitlines() if l.strip()]
            outputs = [l for l in lines if len(l) > 1][:count]

            while len(outputs) < count:
                outputs.append(outputs[-1] if outputs else "(빈 결과)")

        except Exception as e:
            outputs = [f"(Claude 오류) {e}"]

        # 로그 저장 (첫 번째 결과만 기록)
        try:
            sess = session.get("user") or {}
            uid = sess.get("user_id")
            request_ip = request.remote_addr

            log = RewriteLog(
                user_pk=None,
                user_id=uid,
                input_text=input_text,
                output_text=(outputs[0] if outputs else "(에러/빈 응답)"),
                categories=selected_categories or [],
                tones=selected_tones or [],
                honorific=bool(honorific_checked),
                opener=bool(opener_checked),
                emoji=bool(emoji_checked),
                model_name=f"claude:{model_name}",
                request_ip=request_ip,
            )
            if uid:
                u = User.query.filter_by(user_id=uid).first()
                if u:
                    log.user_pk = u.id
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            db.session.rollback()
            print("[rewrite log save error]", log_err)

        return outputs

    @app.before_request
    def mark_ads_allowed_path():
        # 광고를 노출하고 싶은 경로만 True (예: 메인/히스토리/마이페이지 상단 배너)
        ADS_PATHS = {"/", "/history", "/mypage", "/pricing", "/subscribe"}
        g.show_ads_here = (request.path in ADS_PATHS)

        # -------------------- 보안 훅/역할 로드 --------------------
    @app.before_request
    def guard_payload_size():
        if request.content_length and request.content_length > 256 * 1024:
            abort(413)

    @app.before_request
    def load_current_user_role():
        g.is_admin = False
        sess = session.get("user") or {}
        uid = sess.get("user_id")
        if not uid:
            try:
                db.session.rollback()
            finally:
                return
        user = User.query.filter_by(user_id=uid).first()
        if user and getattr(user, "is_admin", False):
            g.is_admin = True
        elif ADMIN_ID and uid == ADMIN_ID:
            g.is_admin = True
        try:
            db.session.rollback()
        except Exception:
            pass

    def admin_required(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not g.get("is_admin", False):
                return abort(403)
            return view_func(*args, **kwargs)
        return wrapper

    # -------------------- 방문 로깅 --------------------
    @app.before_request
    def log_visit():
        path = request.path or "/"
        if path.startswith("/static") or path.startswith("/health") or path.startswith("/api/"):
            return
        try:
            TRACK_PATHS = {"/", "/subscribe", "/history", "/login", "/signup"}
            if path not in TRACK_PATHS:
                return
            sess = session.get("user") or {}
            user_id = sess.get("user_id")
            ip = request.remote_addr
            ua = (request.headers.get("User-Agent") or "")[:500]
            v = Visit(user_id=user_id, ip=ip, user_agent=ua, path=path)
            db.session.add(v)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # -------------------- 보안 헤더 --------------------
    @app.after_request
    def add_security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")

        nonce = getattr(g, "csp_nonce", "")

        csp = (
            "default-src 'self'; "
            "img-src 'self' data: https://www.gstatic.com/recaptcha/ https://*.tosspayments.com; "
            "style-src 'self' 'unsafe-inline'; "
            f"script-src 'self' 'nonce-{nonce}' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/ https://js.tosspayments.com; "
            "frame-src https://www.google.com/ https://www.gstatic.com/ https://tosspayments.com https://*.tosspayments.com; "
            "connect-src 'self' https://api.tosspayments.com https://log.tosspayments.com https://customer.tosspayments.com https://*.tosspayments.com; "
        )

        # ⬇️ 광고 제공자별 도메인 화이트리스트(ADS_ENABLED일 때만)
        if ADS_ENABLED:
            if ADS_PROVIDER == "adsense":
                csp += (
                    # AdSense / Google Ads
                    "script-src-elem 'self' https://pagead2.googlesyndication.com https://www.googletagservices.com; "
                    "img-src 'self' data: https://pagead2.googlesyndication.com https://tpc.googlesyndication.com https://googleads.g.doubleclick.net; "
                    "frame-src https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com; "
                    "connect-src 'self' https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com; "
                )
            elif ADS_PROVIDER == "kakao":
                csp += (
                    # Kakao AdFit
                    "script-src-elem 'self' https://ad.kakao.com https://adfit.ad.daum.net https://t1.daumcdn.net; "
                    "img-src 'self' data: https://t1.daumcdn.net https://ad.kakao.com https://adfit.ad.daum.net; "
                    "frame-src https://ad.kakao.com https://adfit.ad.daum.net https://t1.daumcdn.net; "
                    "connect-src 'self' https://ad.kakao.com https://adfit.ad.daum.net; "
                )
            elif ADS_PROVIDER == "naver":
                csp += (
                    # Naver Ads(대역폭 넉넉히 허용)
                    "script-src-elem 'self' https://*.naver.com https://ssl.pstatic.net; "
                    "img-src 'self' data: https://*.naver.com https://ssl.pstatic.net; "
                    "frame-src https://*.naver.com https://ssl.pstatic.net; "
                    "connect-src 'self' https://*.naver.com https://ssl.pstatic.net; "
                )

        resp.headers.setdefault("Content-Security-Policy", csp)
        return resp

    # -------------------- API Origin 검사 --------------------
    def _origin_allowed():
        origin = (request.headers.get("Origin") or "").rstrip("/")
        ref = (request.headers.get("Referer") or "").rstrip("/")
        this = (request.host_url or "").rstrip("/")

        if origin.startswith("chrome-extension://") or ref.startswith("chrome-extension://"):
            return True

        allowed = set(API_ALLOWED_ORIGINS)
        allowed.add(this)
        # 확장 오리진 추가
        for eo in EXT_ORIGINS:
            allowed.add(eo)

        if origin in allowed:
            return True
        for a in allowed:
            if a and ref.startswith(a + "/"):
                return True
        if not origin and this in allowed:
            return True
        return False

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

    # ===== 관리자 GET 쿼리 검증 헬퍼 =====
    import re, json
    from jsonschema import validate as _jsonschema_validate, ValidationError as _JsErr

    YMD_RE = r"^\d{4}-\d{2}-\d{2}$"
    PATH_ALLOW = ["", "/", "/login", "/signup", "/subscribe", "/history"]

    def _safe_args(schema, *, source=None):
        q = {
            k: (
                request.args.getlist(k)
                if len(request.args.getlist(k)) > 1
                else request.args.get(k)
            )
            for k in request.args.keys()
        }
        for k, v in list(q.items()):
            if isinstance(v, str) and v.strip() == "":
                q[k] = None
        try:
            _jsonschema_validate(instance=q, schema=schema)
        except _JsErr as e:
            abort(400, description=f"유효하지 않은 쿼리: {e.message}")
        return q

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

    def _truthy(v):
        return str(v).lower() in {"on", "true", "1", "yes"}

    @app.before_request
    def _make_csp_nonce():
        # 요청마다 랜덤 nonce 생성
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _inject_nonce():
        # 모든 템플릿에서 {{ csp_nonce }} 로 접근 가능
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    # 추가
    @app.context_processor
    def inject_ads_flags():
        tier = resolve_tier()
        # 프로는 광고 OFF, 나머지는 ADS_ENABLED 따라 ON
        show_ads = ADS_ENABLED and tier in {"guest", "free"}
        return {
            "ADS_ENABLED": ADS_ENABLED,
            "ADS_PROVIDER": ADS_PROVIDER,
            "ADSENSE_CLIENT": ADSENSE_CLIENT,
            "ADFIT_UNIT_ID": ADFIT_UNIT_ID,
            "NAVER_AD_UNIT": NAVER_AD_UNIT,
            "SHOW_ADS": show_ads,
        }

    def _get_ai_outputs(provider, input_text, selected_categories, selected_tones, honorific_checked, opener_checked, emoji_checked, n_outputs):
        """Helper function to call the appropriate AI provider and log the request."""
        outputs = []
        if provider == "openai":
            try:
                outputs = call_openai_and_log(
                    input_text,
                    selected_categories,
                    selected_tones,
                    honorific_checked,
                    opener_checked,
                    emoji_checked,
                    n_outputs=n_outputs,
                )
            except Exception:
                outputs = []
        elif provider == "claude":
            outputs = call_claude_and_log(
                input_text,
                selected_categories,
                selected_tones,
                honorific_checked,
                opener_checked,
                emoji_checked,
                n_outputs=n_outputs,
            )
        else:  # Default to openai
            try:
                outputs = call_openai_and_log(
                    input_text,
                    selected_categories,
                    selected_tones,
                    honorific_checked,
                    opener_checked,
                    emoji_checked,
                    n_outputs=n_outputs,
                )
            except Exception:
                outputs = []
        return outputs

    # -------------------- 라우트 --------------------
    @app.route("/", methods=["GET", "POST"])
    @require_safe_input(polish_input_schema, form=True, for_llm_fields=["input_text"])
    @require_feature("rewrite.single")     #  비로그인: 기능 허용 검증
    @enforce_quota("rewrite")              #  일/월 한도 차감(성공 시) — scope=rewrite
    def polish():
        """
        메인 페이지 — 문장 다듬기 기능
        """
        input_text = ""
        output_text = ""
        outputs = []
        selected_categories = []
        selected_tones = []
        honorific_checked = False
        opener_checked = False
        emoji_checked = False
        provider_current = PROVIDER_DEFAULT

        if g.safe_input:
            data = g.safe_input
            input_text = (data.get("input_text") or "").strip()
            selected_categories = (
                data.get("selected_categories") or data.get("categories") or []
            )
            selected_tones = data.get("selected_tones") or data.get("tones") or []
            honorific_checked = bool(data.get("honorific_checked") or data.get("honorific"))
            opener_checked = bool(data.get("opener_checked") or data.get("opener"))
            emoji_checked = bool(data.get("emoji_checked") or data.get("emoji"))
            provider_current = (data.get("provider") or PROVIDER_DEFAULT).lower()

            if provider_current not in ("openai", "gemini", "claude"):
                provider_current = PROVIDER_DEFAULT

            if input_text:
                n_outputs = outputs_for_tier()
                outputs = _get_ai_outputs(
                    provider_current,
                    input_text,
                    selected_categories,
                    selected_tones,
                    honorific_checked,
                    opener_checked,
                    emoji_checked,
                    n_outputs
                )

        outputs = _ensure_exact_count(outputs, outputs_for_tier())
        output_text = outputs[0] if outputs else ""

        return render_template(
            "mainpage.html",
            input_text=input_text,
            output_text=output_text or "",
            outputs=outputs,
            selected_categories=selected_categories,
            selected_tones=selected_tones,
            honorific_checked=honorific_checked,
            opener_checked=opener_checked,
            emoji_checked=emoji_checked,
            provider_current=provider_current,
            is_pro=(resolve_tier() == "pro"),
        )

    # JSON API — CSRF 제외 + Origin 화이트리스트 검사 + 레이트리밋
    @csrf.exempt
    @limiter.limit("60/minute")
    @app.route("/api/polish", methods=["POST"])
    @require_safe_input(api_polish_schema, form=False, for_llm_fields=["input_text"])
    @require_feature("rewrite.single")  # 기능 권한
    @enforce_quota("rewrite")          #  scope=rewrite
    def api_polish():
        start_t = time.perf_counter()
        if not _origin_allowed():
            _sleep_floor(start_t)
            return jsonify({"error": "forbidden_origin"}), 403

        data = g.safe_input
        input_text = (data.get("input_text") or "").strip()
        selected_categories = data.get("selected_categories", [])
        selected_tones = data.get("selected_tones", [])
        honorific_checked = bool(data.get("honorific_checked"))
        opener_checked = bool(data.get("opener_checked"))
        emoji_checked = bool(data.get("emoji_checked"))
        provider = (data.get("provider") or PROVIDER_DEFAULT).lower()

        if not input_text:
            _sleep_floor(start_t)
            return jsonify({"error": "empty_input"}), 400
        if len(input_text) > 4000:
            _sleep_floor(start_t)
            return jsonify({"error": "too_long"}), 413
        if provider not in ("openai", "gemini", "claude"):
            provider = PROVIDER_DEFAULT

        n_outputs = outputs_for_tier()

        outputs = _get_ai_outputs(
            provider,
            input_text,
            selected_categories,
            selected_tones,
            honorific_checked,
            opener_checked,
            emoji_checked,
            n_outputs
        )

        outputs = _ensure_exact_count(outputs, n_outputs)
        resp = jsonify({"outputs": outputs, "output_text": outputs[0]}), 200
        _sleep_floor(start_t)
        return resp

    @csrf.exempt
    @nocache
    @app.route("/api/usage", methods=["GET"])
    def api_usage_status():
        """
          scope-aware 사용량 조회
        - 로그인: 월간 window + scope
        - 게스트: 일간 window + scope
        """
        def _json_resp(payload, set_aid=None, status=200):
            resp = make_response(jsonify(payload), status)
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
            if set_aid is not None:
                set_guest_cookie(resp, set_aid)
            return resp

        try:
            if "_origin_allowed" in globals() and not _origin_allowed():
                return _json_resp({"error": "forbidden_origin"}, status=403)
        except Exception:
            pass

        #  scope 파라미터 (기본 rewrite)
        scope = (request.args.get("scope") or "rewrite").strip().lower()
        if scope not in USAGE_SCOPES:
            scope = "rewrite"

        # ----- 로그인 사용자 -----
        sess = session.get("user") or {}
        uid = sess.get("user_id")
        if uid:
            try:
                sub = Subscription.query.filter_by(user_id=uid, status="active").first()
                tier = "pro" if sub else "free"
                limit = LIMITS["pro"]["monthly"] if tier == "pro" else LIMITS["free"]["monthly"]

                #  Usage.window_start는 Date — 범위 조회 사용
                now = _utcnow()
                month_start, month_end = _month_window(now)

                used = (
                    db.session.query(func.coalesce(func.sum(Usage.count), 0))
                    .filter(
                        Usage.user_id == uid,
                        Usage.tier == tier,
                        Usage.scope == scope,              #  scope 필터
                        Usage.window_start >= month_start,
                        Usage.window_start < month_end,
                    )
                    .scalar()
                )
                return _json_resp({"used": int(used or 0), "limit": int(limit), "tier": tier, "scope": scope})
            except Exception:
                return _json_resp({"used": 0, "limit": LIMITS["free"]["monthly"], "tier": "free", "scope": scope})

        # ----- 게스트 -----
        try:
            tier = "guest"
            limit = LIMITS["guest"]["daily"]
            aid, need_set = ensure_guest_cookie()

            now = _utcnow()
            day_start, day_end = _day_window(now)

            used = (
                db.session.query(func.coalesce(func.sum(GuestUsage.count), 0))
                .filter(
                    GuestUsage.anon_key == aid,
                    GuestUsage.scope == scope,            # ✅ scope 필터
                    GuestUsage.window_start >= day_start,
                    GuestUsage.window_start < day_end,
                )
                .scalar()
            )

            return _json_resp(
                {"used": int(used or 0), "limit": int(limit), "tier": tier, "scope": scope},
                set_aid=aid if need_set else None
            )
        except Exception:
            return _json_resp({"used": 0, "limit": LIMITS["guest"]["daily"], "tier": "guest", "scope": scope})

    def _json_ok(payload=None, status=200):
        payload = payload or {}
        resp = make_response(jsonify({"ok": True, **payload}), status)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    def _json_err(code, message=None, status=400):
        resp = make_response(jsonify({"ok": False, "error": code, "message": message}), status)
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @csrf.exempt
    @limiter.limit("60/minute")
    @app.route("/api/user_templates", methods=["GET", "POST"])
    def api_user_templates():
        if not _origin_allowed():
            return _json_err("forbidden_origin", status=403)

        user = get_current_user()
        if not user:
            return _json_err("login_required", status=401)
        if resolve_tier() != "pro":
            return _json_err("pro_required", status=403)

        if request.method == "GET":
            rows = (
                UserTemplate.query.filter_by(user_id=user.user_id)
                .order_by(UserTemplate.updated_at.desc())
                .all()
            )
            return _json_ok({"items": [r.to_dict() for r in rows]})

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        category = (data.get("category") or "").strip() or None
        tone = (data.get("tone") or "").strip() or None
        honorific = bool(data.get("honorific"))
        opener = bool(data.get("opener"))
        emoji = bool(data.get("emoji"))

        if not title:
            return _json_err("title_required", "제목은 필수입니다.", status=400)

        tpl = UserTemplate(
            user_id=user.user_id,
            title=title,
            category=category,
            tone=tone,
            honorific=honorific,
            opener=opener,
            emoji=emoji,
        )
        db.session.add(tpl)
        db.session.commit()
        return _json_ok({"item": tpl.to_dict()}, status=200)

    @csrf.exempt
    @limiter.limit("60/minute")
    @app.route("/api/user_templates/<int:tpl_id>", methods=["DELETE"])
    def api_user_templates_delete(tpl_id):
        if not _origin_allowed():
            return _json_err("forbidden_origin", status=403)

        user = get_current_user()
        if not user:
            return _json_err("login_required", status=401)
        if resolve_tier() != "pro":
            return _json_err("pro_required", status=403)

        tpl = UserTemplate.query.filter_by(id=tpl_id, user_id=user.user_id).first()
        if not tpl:
            return _json_err("not_found", "해당 템플릿을 찾을 수 없습니다.", status=404)

        db.session.delete(tpl)
        db.session.commit()
        return _json_ok({"deleted_id": tpl_id}, status=200)

    @app.route("/feedback", methods=["GET", "POST"])
    @require_safe_input(feedback_schema_, form=True)
    def feedback():
        success = None
        error = None

        sess = session.get("user", {}) or {}
        default_email = sess.get("email") or ""
        default_user_id = sess.get("user_id") or ""
        default_page = request.args.get("from") or request.referrer or "/"

        if g.safe_input:
            data = g.safe_input
            email = (data.get("email") or default_email).strip()
            user_id = (data.get("user_id") or default_user_id).strip()
            category = (data.get("category") or "general").strip()
            message = (data.get("message") or "").strip()
            page = (data.get("page") or default_page).strip()

            if not message:
                error = "피드백 내용을 입력해 주세요."
            else:
                try:
                    fb = Feedback(
                        user_id=user_id or None,
                        email=email or None,
                        category=category or "general",
                        message=message,
                        page=page or None,
                    )
                    db.session.add(fb)
                    db.session.commit()
                    success = "소중한 의견 감사합니다! 반영에 노력하겠습니다."
                    return render_template(
                        "feedback.html",
                        success=success,
                        email=default_email,
                        user_id=default_user_id,
                        category="general",
                        message="",
                        page=default_page,
                    )
                except Exception as e:
                    db.session.rollback()
                    error = f"저장 중 오류가 발생했습니다: {e}"

        return render_template(
            "feedback.html",
            error=error,
            success=success,
            email=default_email,
            user_id=default_user_id,
            category="general",
            message="",
            page=default_page,
        )

    # ===== 마이페이지(읽기 전용 개요) =====
    @csrf.exempt
    @app.route("/mypage", methods=["GET"])
    def mypage_overview():
        sess = session.get("user") or {}
        uid = sess.get("user_id")
        if not uid:
            return redirect(url_for("auth.login_page") + "?next=/mypage")

        user = User.query.filter_by(user_id=uid).first()
        if not user:
            return redirect(url_for("auth.login_page"))

        tier = resolve_tier()
        limit = LIMITS[tier]["monthly"]

        month_start, month_end = _month_window(_utcnow())

        # ✅ 전체 합계(과거 호환) — scope 합산
        used = (
            db.session.query(func.coalesce(func.sum(Usage.count), 0))
            .filter(
                Usage.user_id == uid,
                Usage.tier == tier,
                Usage.window_start >= month_start,
                Usage.window_start < month_end,
            )
            .scalar()
            or 0
        )
        remaining = max(0, (limit or 0) - int(used))

        visits = (
            Visit.query.filter(Visit.user_id == uid)
            .order_by(Visit.created_at.desc())
            .limit(5)
            .all()
        )

        active_sub = (
            Subscription.query.filter_by(user_id=uid, status="active")
            .order_by(Subscription.created_at.desc())
            .first()
        )

        payments = (
            Payment.query.filter_by(user_id=uid)
            .order_by(Payment.created_at.desc())
            .limit(5)
            .all()
        )

        my_feedbacks = (
            Feedback.query
            .filter(Feedback.user_id == user.user_id)
            .order_by(Feedback.created_at.desc())
            .limit(50)
            .all()
        )

        return render_template(
            "mypage.html",
            user=user,
            tier=tier,
            used=int(used),
            limit=int(limit),
            remaining=int(remaining),
            visits=visits,
            active_sub=active_sub,
            payments=payments,
            my_feedbacks=my_feedbacks,
        )

    # ------ 관리자 대시보드 페이지/데이터 ------
    @app.route("/admin/analytics", methods=["GET"])
    @admin_required
    def admin_analytics_page():
        return render_template("admin_analytics.html")

    @app.route("/admin/usage", methods=["GET"])
    @admin_required
    def admin_usage_page():
        return render_template("admin_usage.html")

    @app.route("/admin/feedback", methods=["GET"])
    @admin_required
    @nocache
    def admin_feedback_page():
        return render_template("admin_feedback.html")

    @app.route("/admin/feedback/<int:fid>/resolve", methods=["POST"])
    @admin_required
    def admin_feedback_resolve(fid):
        fb = Feedback.query.get_or_404(fid)
        fb.resolved = not fb.resolved
        db.session.commit()
        return jsonify({"ok": True, "resolved": fb.resolved})

    @app.route("/admin/feedback/data", methods=["GET"])
    @admin_required
    @nocache
    def admin_feedback_data():
        from sqlalchemy import or_, and_

        category = (request.args.get("category") or "").strip()
        s_resolved = (request.args.get("resolved") or "").strip().lower()
        q = (request.args.get("q") or "").strip()
        try:
            page = max(1, int(request.args.get("page", 1)))
        except Exception:
            page = 1
        try:
            size = int(request.args.get("page_size", 20))
            size = max(1, min(100, size))
        except Exception:
            size = 20

        conds = []
        if category:
            conds.append(Feedback.category == category)
        if q:
            like = f"%{q}%"
            conds.append(or_(
                Feedback.email.ilike(like),
                Feedback.user_id.ilike(like),
                Feedback.message.ilike(like),
            ))
        # resolved 필터는 admin_reply 존재 여부로 판단 (모델에 별도 필드 없어도 동작)
        if s_resolved in ("true", "false"):
            want = (s_resolved == "true")
            if want:
                conds.append(Feedback.admin_reply.isnot(None))
            else:
                conds.append(Feedback.admin_reply.is_(None))

        base = Feedback.query
        if conds:
            from sqlalchemy import and_
            base = base.filter(and_(*conds))

        total = base.count()
        rows = (
            base.order_by(Feedback.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        def row_json(r: Feedback):
            return {
                "id": r.id,
                "created_at": r.created_at.astimezone().strftime("%Y-%m-%d %H:%M") if r.created_at else None,
                "category": r.category,
                "email": r.email,
                "user_id": r.user_id,
                "page": r.page,
                "message": r.message,
                "resolved": bool(r.admin_reply),
                "admin_reply": r.admin_reply,
                "replied_at": r.replied_at.astimezone().strftime("%Y-%m-%d %H:%M") if r.replied_at else None,
            }

        return jsonify({
            "items": [row_json(r) for r in rows],
            "page": page,
            "page_size": size,
            "total": total,
            "page_count": (total + size - 1) // size
        }), 200

    @app.route("/admin/feedback/<int:fid>", methods=["GET"])
    @admin_required
    @nocache
    def admin_feedback_detail(fid):
        row = Feedback.query.get(fid)
        if not row:
            return render_template("admin_feedback_detail.html", error="존재하지 않는 항목입니다."), 404
        return render_template("admin_feedback_detail.html", item=row)

    @app.route("/admin/feedback/<int:fid>/reply", methods=["POST"])
    @admin_required
    def admin_feedback_reply(fid):
        row = Feedback.query.get(fid)
        if not row:
            abort(404)

        reply = (request.form.get("admin_reply") or "").strip()
        row.admin_reply = reply if reply else None
        row.replied_at = _utcnow() if reply else None

        db.session.add(row)
        db.session.commit()

        return redirect(url_for("admin_feedback_detail", fid=fid) + "?saved=1")

    # (선택) 삭제
    @app.route("/admin/feedback/<int:fb_id>", methods=["DELETE"])
    @admin_required
    def admin_feedback_delete(fb_id):
        fb = Feedback.query.get(fb_id)
        if not fb:
            return jsonify({"ok": False, "error": "not_found"}), 404
        db.session.delete(fb)
        db.session.commit()
        return jsonify({"ok": True}), 200

    @app.route("/admin/analytics/data/visits", methods=["GET"])
    @admin_required
    @nocache
    def admin_analytics_data_visits():
        from models import Visit, User

        q = _safe_args(admin_visits_query_schema)
        s_from = q.get("from")
        s_to = q.get("to")
        path = q.get("path")
        ukey = q.get("user")

        now_utc = _utcnow()
        now_kst = now_utc.astimezone(KST)

        start_kst = (now_kst - timedelta(days=29)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_kst = now_kst

        def parse_ymd_kst(s):
            try:
                y, m, d = s.split("-")
                return datetime(int(y), int(m), int(d), tzinfo=KST)
            except Exception:
                return None

        pf_kst = parse_ymd_kst(s_from) or start_kst
        pt_kst = parse_ymd_kst(s_to) or end_kst
        if pt_kst < pf_kst:
            pf_kst, pt_kst = pt_kst, pf_kst

        upper_kst = (pt_kst + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        pf_utc_naive = pf_kst.astimezone(timezone.utc).replace(tzinfo=None)
        up_utc_naive = upper_kst.astimezone(timezone.utc).replace(tzinfo=None)

        v_filters = [
            Visit.created_at >= pf_utc_naive,
            Visit.created_at < up_utc_naive,
        ]
        if path:
            v_filters.append(Visit.path == path)

        if ukey:
            user_ids = {ukey}
            u = User.query.filter(User.email == ukey).first()
            if u and u.user_id:
                user_ids.add(u.user_id)
            v_filters.append(Visit.user_id.in_(list(user_ids)))

        rows = (
            db.session.query(
                func.date_trunc("day", Visit.created_at).label("d"),
                func.count(Visit.id),
            )
            .filter(and_(*v_filters))
            .group_by("d")
            .order_by("d")
            .all()
        )

        utc_map = {r[0].date(): int(r[1]) for r in rows}

        days_span = (pt_kst.date() - pf_kst.date()).days + 1
        series = []
        for i in range(days_span):
            d_kst = pf_kst + timedelta(days=i)
            d_utc = d_kst.astimezone(timezone.utc).date()
            series.append({"date": d_kst.strftime("%Y-%m-%d"), "count": utc_map.get(d_utc, 0)})

        return jsonify({"series": series}), 200

    @app.route("/admin/analytics/data/usage", methods=["GET"])
    @admin_required
    @nocache
    def admin_analytics_data_usage():
        from models import RewriteLog
        now_kst = datetime.now(KST)
        period = request.args.get("period", "month") # 'today', 'week', 'month'

        # --- 1. KPI 계산 (오늘, 이번 주, 이번 달) ---
        # Today
        today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
        today_end_utc = today_start_utc + timedelta(days=1)
        usage_today = db.session.query(func.count(RewriteLog.id)).filter(
            RewriteLog.created_at >= today_start_utc,
            RewriteLog.created_at < today_end_utc
        ).scalar() or 0

        # This Week (Mon-Sun)
        week_start_kst = today_start_kst - timedelta(days=now_kst.weekday())
        week_end_utc = (week_start_kst + timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
        week_start_utc = week_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
        usage_week = db.session.query(func.count(RewriteLog.id)).filter(
            RewriteLog.created_at >= week_start_utc,
            RewriteLog.created_at < week_end_utc
        ).scalar() or 0

        # This Month
        month_start_kst = now_kst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month_val = month_start_kst.month + 1 if month_start_kst.month < 12 else 1
        next_year_val = month_start_kst.year if month_start_kst.month < 12 else month_start_kst.year + 1
        month_end_kst = month_start_kst.replace(year=next_year_val, month=next_month_val)
        month_start_utc = month_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
        month_end_utc = month_end_kst.astimezone(timezone.utc).replace(tzinfo=None)
        usage_month = db.session.query(func.count(RewriteLog.id)).filter(
            RewriteLog.created_at >= month_start_utc,
            RewriteLog.created_at < month_end_utc
        ).scalar() or 0

        # --- 2. 그래프용 시계열 데이터 ---
        series = []
        if period == "today":
            # 시간별 집계
            rows = db.session.query(
                func.date_trunc('hour', RewriteLog.created_at).label('h'),
                func.count(RewriteLog.id)
            ).filter(
                RewriteLog.created_at >= today_start_utc,
                RewriteLog.created_at < today_end_utc
            ).group_by('h').all()
            
            hour_map = {r.h.hour: r[1] for r in rows}
            for i in range(24):
                series.append({"label": f"{i:02d}시", "count": hour_map.get(i, 0)})

        elif period == "week":
            # 주별 일자 집계
            rows = db.session.query(
                func.date_trunc('day', RewriteLog.created_at).label('d'),
                func.count(RewriteLog.id)
            ).filter(
                RewriteLog.created_at >= week_start_utc,
                RewriteLog.created_at < week_end_utc
            ).group_by('d').order_by('d').all()

            day_map = {r.d.date(): r[1] for r in rows}
            for i in range(7):
                d = week_start_utc.date() + timedelta(days=i)
                series.append({"label": d.strftime("%m-%d"), "count": day_map.get(d, 0)})
        
        else: # "month" or default
            # 월별 일자 집계
            rows = db.session.query(
                func.date_trunc('day', RewriteLog.created_at).label('d'),
                func.count(RewriteLog.id)
            ).filter(
                RewriteLog.created_at >= month_start_utc,
                RewriteLog.created_at < month_end_utc
            ).group_by('d').order_by('d').all()

            day_map = {r.d.date(): r[1] for r in rows}
            num_days = (month_end_kst.date() - month_start_kst.date()).days
            for i in range(num_days):
                d = month_start_utc.date() + timedelta(days=i)
                series.append({"label": d.strftime("%m-%d"), "count": day_map.get(d, 0)})

        return jsonify({
            "kpi": {
                "today": usage_today,
                "week": usage_week,
                "month": usage_month,
            },
            "series": series
        }), 200


    @app.route("/admin/analytics/data", methods=["GET"])
    @admin_required
    @nocache
    def admin_analytics_data():
        from models import RewriteLog, Visit, Feedback
        from sqlalchemy import and_, desc

        qsafe = _safe_args(admin_data_query_schema)
        q_date_from = qsafe.get("date_from")
        q_date_to = qsafe.get("date_to")
        q_days = int(qsafe.get("days") or 7)
        q_path = qsafe.get("path") or None
        q_user_id = qsafe.get("user_id") or None

        def parse_ymd(s):
            try:
                y, m, d = map(int, s.split("-"))
                return datetime(y, m, d, tzinfo=KST)
            except Exception:
                return None

        today_kst = (
            _utcnow()
            .astimezone(KST)
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )

        date_from_kst = parse_ymd(q_date_from) or (today_kst - timedelta(days=q_days - 1))
        date_to_kst = parse_ymd(q_date_to) or today_kst
        date_to_kst_inclusive = date_to_kst + timedelta(days=1)

        date_from_utc = date_from_kst.astimezone(timezone.utc)
        date_to_utc = date_to_kst_inclusive.astimezone(timezone.utc)

        rl_filters = [RewriteLog.created_at >= date_from_utc, RewriteLog.created_at < date_to_utc]
        if q_user_id:
            rl_filters.append(RewriteLog.user_id == q_user_id)

        v_filters = [Visit.created_at >= date_from_utc, Visit.created_at < date_to_utc]
        if q_path:
            v_filters.append(Visit.path == q_path)

        total_calls = (
            db.session.query(func.count(RewriteLog.id)).filter(*rl_filters).scalar() or 0
        )
        unique_users = (
            db.session.query(func.count(func.distinct(RewriteLog.user_id)))
            .filter(*rl_filters)
            .scalar()
            or 0
        )
        total_visits = (
            db.session.query(func.count(Visit.id)).filter(*v_filters).scalar() or 0
        )

        success_calls = (
            db.session.query(func.count(RewriteLog.id))
            .filter(and_(*rl_filters, RewriteLog.output_text.isnot(None), RewriteLog.output_text != ""))
            .scalar()
            or 0
        )
        error_calls = total_calls - success_calls
        success_rate = (success_calls / total_calls * 100.0) if total_calls else 0.0
        error_rate = 100.0 - success_rate if total_calls else 0.0

        feedback_count = (
            db.session.query(func.count(Feedback.id))
            .filter(Feedback.created_at >= date_from_utc, Feedback.created_at < date_to_utc)
            .scalar()
            or 0
        )

        model_rows = (
            db.session.query(RewriteLog.model_name, func.count(RewriteLog.id))
            .filter(*rl_filters)
            .group_by(RewriteLog.model_name)
            .order_by(desc(func.count(RewriteLog.id)))
            .all()
        )
        top_model = model_rows[0][0] if model_rows else None

        today_start_kst = today_kst
        tomorrow_start_kst = today_start_kst + timedelta(days=1)
        week_start_kst = today_start_kst - timedelta(days=6)
        month_start_kst = today_start_kst.replace(day=1)

        def count_visits(kst_start, kst_end_exclusive):
            return (
                db.session.query(func.count(Visit.id))
                .filter(
                    Visit.created_at >= kst_start.astimezone(timezone.utc),
                    Visit.created_at < kst_end_exclusive.astimezone(timezone.utc),
                )
                .scalar()
                or 0
            )

        kpi_today = count_visits(today_start_kst, tomorrow_start_kst)
        kpi_this_week = count_visits(week_start_kst, tomorrow_start_kst)
        kpi_this_month = count_visits(month_start_kst, tomorrow_start_kst)

        rows = (
            db.session.query(
                func.date_trunc("day", RewriteLog.created_at).label("d"),
                func.count(RewriteLog.id),
            )
            .filter(*rl_filters)
            .group_by("d")
            .order_by("d")
            .all()
        )
        by_day_map = {r[0].astimezone(KST).date(): int(r[1]) for r in rows}
        days_span = (date_to_kst - date_from_kst).days + 1
        trends = []
        for i in range(days_span):
            d_kst = (date_from_kst + timedelta(days=i)).date()
            trends.append({"date": d_kst.strftime("%Y-%m-%d"), "count": by_day_map.get(d_kst, 0)})

        top_paths_rows = (
            db.session.query(Visit.path, func.count(Visit.id))
            .filter(*v_filters)
            .group_by(Visit.path)
            .order_by(func.count(Visit.id).desc())
            .limit(10)
            .all()
        )
        top_paths = [{"path": p, "count": int(c)} for (p, c) in (top_paths_rows or [])]

        top_users_rows = (
            db.session.query(RewriteLog.user_id, func.count(RewriteLog.id))
            .filter(*rl_filters)
            .group_by(RewriteLog.user_id)
            .order_by(func.count(RewriteLog.id).desc())
            .limit(10)
            .all()
        )
        top_users = [{"user_id": u or "(익명)", "count": int(c)} for (u, c) in (top_users_rows or [])]

        bins = [(0, 50), (51, 100), (101, 200), (201, 300), (301, 500), (501, 10_000_000)]
        bin_labels = ["0-50", "51-100", "101-200", "201-300", "301-500", "501+"]
        len_rows = db.session.query(RewriteLog.input_text).filter(*rl_filters).all()
        bucket = [0] * len(bins)
        for (txt,) in (len_rows or []):
            ln = len(txt or "")
            for idx, (a, b) in enumerate(bins):
                if a <= ln <= b:
                    bucket[idx] += 1
                    break
        length_dist = [{"range": label, "count": bucket[i]} for i, label in enumerate(bin_labels)]

        cat_count, tone_count = {}, {}
        ct_rows = db.session.query(RewriteLog.categories, RewriteLog.tones).filter(*rl_filters).all()
        for cats, tones in (ct_rows or []):
            if isinstance(cats, list):
                for c in cats:
                    if c:
                        cat_count[c] = cat_count.get(c, 0) + 1
            if isinstance(tones, list):
                for t in tones:
                    if t:
                        tone_count[t] = tone_count.get(t, 0) + 1
        top_categories = sorted(
            [{"name": k, "count": v} for k, v in cat_count.items()], key=lambda x: -x["count"]
        )[:10]
        top_tones = sorted(
            [{"name": k, "count": v} for k, v in tone_count.items()], key=lambda x: -x["count"]
        )[:10]

        all_paths_rows = (
            db.session.query(Visit.path, func.count(Visit.id))
            .filter(Visit.created_at >= date_from_utc, Visit.created_at < date_to_utc)
            .group_by(Visit.path)
            .order_by(func.count(Visit.id).desc())
            .limit(50)
            .all()
        )
        paths_all = [p for (p, _c) in (all_paths_rows or [])]

        users_sample_rows = (
            db.session.query(RewriteLog.user_id, func.count(RewriteLog.id))
            .filter(RewriteLog.created_at >= date_from_utc, RewriteLog.created_at < date_to_utc)
            .group_by(RewriteLog.user_id)
            .order_by(func.count(RewriteLog.id).desc())
            .limit(50)
            .all()
        )
        users_all = [u or "(익명)" for (u, _c) in (users_sample_rows or [])]

        return jsonify(
            {
                "today": kpi_today,
                "this_week": kpi_this_week,
                "this_month": kpi_this_month,
                "range": {
                    "date_from": date_from_kst.strftime("%Y-%m-%d"),
                    "date_to": date_to_kst.strftime("%Y-%m-%d"),
                    "path": q_path,
                    "user_id": q_user_id,
                },
                "kpis": {
                    "total_calls": int(total_calls),
                    "unique_users": int(unique_users),
                    "total_visits": int(total_visits),
                    "success_rate": round(success_rate, 2),
                    "error_rate": round(error_rate, 2),
                    "feedback_count": int(feedback_count),
                    "top_model": top_model,
                },
                "trends": trends,
                "top_paths": top_paths,
                "top_users": top_users,
                "distros": {"length": length_dist, "categories": top_categories, "tones": top_tones},
                "filters": {"paths": paths_all, "users": users_all},
            }
        ), 200

    # 비밀번호 재설정
    @app.route("/forgot", methods=["GET", "POST"])
    @limiter.limit("5/minute;20/hour")
    def forgot_password():
        if request.method == "POST":
            start = time.perf_counter()
            email = (request.form.get("email") or "").strip().lower()
            recaptcha_response = request.form.get("g-recaptcha-response")

            if not verify_recaptcha_v2(recaptcha_response, request.remote_addr):
                elapsed = time.perf_counter() - start
                if elapsed < 1.5:
                    time.sleep(1.5 - elapsed)
                return render_template(
                    "forgot.html",
                    error="자동 등록 방지를 통과하지 못했습니다.",
                    email=email,
                    recaptcha_site_key=RECAPTCHA_SITE_KEY,
                )

            if not email:
                elapsed = time.perf_counter() - start
                if elapsed < 1.5:
                    time.sleep(1.5 - elapsed)
                return render_template(
                    "forgot.html",
                    error="이메일을 입력해 주세요.",
                    email=email,
                    recaptcha_site_key=RECAPTCHA_SITE_KEY,
                )

            user = User.query.filter(func.lower(User.email) == email).first()
            if user:
                raw = create_password_reset_token(
                    user, ttl_seconds=RESET_TOKEN_TTL_SECONDS
                )
                link = url_for("reset_password", token=raw, _external=True)
                # Check if email sending was successful
                if not _send_email_reset_link_sync(user.email, link):
                    # If email sending failed, return an error message
                    elapsed = time.perf_counter() - start
                    if elapsed < 1.5:
                        time.sleep(1.5 - elapsed)
                    return render_template(
                        "forgot.html",
                        error="비밀번호 재설정 이메일 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                        email=email,
                        recaptcha_site_key=RECAPTCHA_SITE_KEY,
                    )

            elapsed = time.perf_counter() - start
            if elapsed < 1.5:
                time.sleep(1.5 - elapsed)

            return render_template(
                "forgot.html",
                message="입력하신 주소로 안내 메일을 보냈습니다. (수신함/스팸함 확인)",
                recaptcha_site_key=RECAPTCHA_SITE_KEY,
            )

        return render_template("forgot.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)

    @app.route("/reset/<token>", methods=["GET", "POST"])
    def reset_password(token):
        if request.method == "GET":
            row, user, status = verify_password_reset_token(token)
            if status != "ok":
                msg = "유효하지 않은 링크입니다." if status in ("invalid", "used") else "링크가 만료되었습니다."
                code = 400
                flag = {"invalid": True} if status in ("invalid", "used") else {"expired": True}
                return render_template("reset.html", error=msg, **flag), code
            return render_template("reset.html", token=token)

        row, user, status = verify_password_reset_token(token)
        if status != "ok":
            msg = "유효하지 않은 링크입니다." if status in ("invalid", "used") else "링크가 만료되었습니다."
            return render_template("reset.html", error=msg), 400

        p1 = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if len(p1) < 8:
            return render_template("reset.html", error="비밀번호는 8자 이상이어야 합니다.", token=token)
        if p1 != p2:
            return render_template("reset.html", error="비밀번호가 일치하지 않습니다.", token=token)
        if user.password_hash and check_password_hash(user.password_hash, p1):
            return render_template("reset.html", error="사용할 수 없는 비밀번호 입니다.", token=token)

        user.password_hash = generate_password_hash(p1)
        db.session.add(user)
        db.session.commit()
        consume_password_reset_token(row)

        return redirect(url_for("auth.login_page") + "?reset=ok")

    # (A) 인증 안내 페이지 + 전송 버튼
    @app.route("/verify/require", methods=["GET"])
    def verify_require():
        user = get_current_user()
        if not user:
            return redirect(url_for("auth.login_page"))
        if user.email_verified:
            nxt = request.args.get("next") or url_for("mypage_overview") if False else "/me"
            return redirect(nxt)
        return render_template("verify_notice.html", email=user.email, next=request.args.get("next") or "")

    # (B) 인증 메일 보내기 (POST)
    @csrf.exempt
    @app.route("/verify/send", methods=["POST"])
    def verify_send():
        user = get_current_user()
        if not user:
            return redirect(url_for("auth.login_page"))
        if user.email_verified:
            return redirect(request.args.get("next") or "/me")

        token = create_email_verify_token(user)
        link = url_for("verify_confirm", token=token, _external=True)
        _send_email_verify_link_sync(user.email, link)
        return render_template("verify_notice.html", email=user.email, sent=True, next=request.args.get("next") or "")

    # (C) 인증 완료 콜백
    @app.route("/verify/<token>", methods=["GET"])
    def verify_confirm(token):
        user, status = verify_email_token(token)
        if status != "ok":
            msg = "유효하지 않은 링크입니다." if status == "invalid" else "인증 링크가 만료되었습니다."
            return render_template("verify_result.html", ok=False, message=msg), 400

        if not user.email_verified:
            user.email_verified = True
            db.session.add(user)
            db.session.commit()

        return render_template("verify_result.html", ok=True, message="이메일 인증이 완료되었습니다.")

    # =========================
    # Summarize(핵심 요약/정리) — 입력/출력만
    # =========================

    @app.route("/summarize")
    def summarize_page():
        return render_template("summarize.html")

    def _build_summarize_prompt_korean(text: str):
        return (
            "아래 한국어 원문을 핵심만 간결하게 요약해 주세요.\n"
            "- 불필요한 수식/감탄사/사족 금지\n"
            "- 핵심 사실, 결론, 근거 위주\n"
            "- 350자 이내\n"
            "- 출력 형식: (1) 불릿 3~5개 또는 (2) 문장 2~3개 중 하나만\n"
            "- 이모지 사용 금지\n\n"
            f"[원문]\n{text.strip()}\n\n"
            "[출력]"
        )

    # ---- 입력 검증 스키마 (폼/JSON) ----
    summarize_form_schema = {
        "type": "object",
        "properties": {
            "input_text": {"type": "string", "minLength": 1, "maxLength": 8000},
        },
        "required": ["input_text"],
        "additionalProperties": True,
    }

    # JS는 { text: "..." }로 보냄. 두 키 다 허용.
    api_summarize_schema = {
        "type": "object",
        "properties": {
            "input_text": {"type": "string", "minLength": 1, "maxLength": 8000},
            "text": {"type": "string", "minLength": 1, "maxLength": 8000},
            "provider": {"type": "string", "enum": ["claude", "openai", "gemini"]},
        },
        "oneOf": [
            {"required": ["input_text"]},
            {"required": ["text"]},
        ],
        "additionalProperties": True,
    }

    def _call_provider_summarize(text: str, provider: str = None) -> str:
        provider = (provider or PROVIDER_DEFAULT).lower()
        prompt = _build_summarize_prompt_korean(text)
        out_text = ""

        if provider == "claude":
            try:
                def _do():
                    return claude_prompt_generator.call_claude(
                        "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다.",
                        prompt,
                    )

                result = _retry(_do)
                out_text = _as_text_from_claude_result(result).strip()
            except Exception:
                out_text = ""
        elif provider == "openai":
            try:
                if not hasattr(current_app, "openai_client") or current_app.openai_client is None:
                    raise RuntimeError("OpenAI client not configured")
                completion = current_app.openai_client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "system", "content": "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    top_p=0.9,
                    max_tokens=400,
                    n=1,
                )
                out_text = (completion.choices[0].message.content or "").strip()
            except Exception:
                out_text = ""
        else:
            # 기본은 Claude
            try:
                def _do():
                    return claude_prompt_generator.call_claude(
                        "당신은 간결하고 사실 중심의 한국어 전문 요약가입니다.",
                        prompt,
                    )

                result = _retry(_do)
                out_text = _as_text_from_claude_result(result).strip()
            except Exception:
                out_text = ""

        return out_text[:1200].strip()


    # ---- JSON API (네 JS 사양에 맞춤) ----
    @csrf.exempt
    @limiter.limit("60/minute")
    @require_feature("summarize")
    @enforce_quota("summarize")
    @app.route("/api/summarize", methods=["POST"])
    def api_summarize():
        # 1) Origin 검사(있다면)
        if not _origin_allowed():
            return jsonify({"error": "forbidden_origin"}), 403

        # 2) 안전 입력 가져오기: g.safe_input 우선, 없으면 직접 JSON 파싱 (최후의 보루)
        data = getattr(g, "safe_input", None)
        data = getattr(g, "safe_input", None)
        if data is None:
            data = request.get_json(silent=True)
            if data is None:
                try:
                    data = json.loads(request.data or b"{}")
                except Exception:
                    return jsonify({"error": "json_required",
                                    "hint": "send JSON with Content-Type: application/json"}), 400

        input_text = (data.get("input_text") or data.get("text") or "").strip()
        provider = (data.get("provider") or PROVIDER_DEFAULT).lower()

        if not input_text:
            return jsonify({"error": "empty_input"}), 400

        # 4) 생성 호출
        output = _call_provider_summarize(input_text, provider)

        # 5) 로그 저장 (예외 무시)
        try:
            sess = session.get("user") or {}
            uid = sess.get("user_id")
            log = RewriteLog(
                user_pk=None,
                user_id=uid,
                input_text=input_text,
                output_text=output or "(빈 응답)",
                categories=["summary"],
                tones=["concise", "clearly"],
                honorific=False, opener=False, emoji=False,
                model_name=f"summarize:{provider}",
                request_ip=request.remote_addr,
            )
            if uid:
                u = User.query.filter_by(user_id=uid).first()
                if u: log.user_pk = u.id
            db.session.add(log);
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "output": output,
            "outputs": [output] if output else [],
            "output_text": output,
        }), 200

    # 토스 페이먼츠를 이용한 결제
    # 정기결제(구독) 구현
    # ---- 1) 체크아웃 시작(프론트 위젯 세팅용 정보 전달) ----
    @app.route("/api/toss/checkout/start", methods=["POST"])
    @csrf.exempt
    def toss_checkout_start():
        user = get_current_user()
        if not user:
            return jsonify({"ok": False, "error": "login_required"}), 401
        if not user.email_verified:
            return jsonify({"ok": False, "error": "email_verify_required"}), 403

        # 요금제는 서버 기준으로 결정(클라 변조 방지)
        plan_name = "pro_monthly"
        plan_amount = 6900  # KRW
        # success/fail 콜백
        success_url = url_for("toss_checkout_success", _external=True)
        fail_url = url_for("toss_checkout_fail", _external=True)

        # 고객 식별자 (토스 customerKey) — 보통 상점 내 유저 식별자 사용
        customer_key = f"u_{user.user_id}"

        return jsonify({
            "ok": True,
            "clientKey": TOSS_CLIENT_KEY,
            "customerKey": customer_key,
            "successUrl": success_url,
            "failUrl": fail_url,
            "plan": {"name": plan_name, "amount": plan_amount, "currency": "KRW"},
        }), 200

    # ---- 2) 성공 콜백: authKey 교환 → billingKey 발급 & 저장 → 첫 결제 진행 ----
    @app.route("/toss/success", methods=["GET"])
    def toss_checkout_success():
        """
        프론트 위젯이 성공 시 여기에 ?authKey=...&customerKey=... 쿼리로 리디렉트
        """
        user = get_current_user()
        if not user:
            return redirect(url_for("auth.login_page"))

        auth_key = request.args.get("authKey")
        customer_key = request.args.get("customerKey")
        if not auth_key or not customer_key:
            return render_template("subscribe.html", error="잘못된 인증 콜백입니다(authKey/customerKey 누락).")

        # 2-1) billingKey 발급
        try:
            issued = toss_request("POST", TOSS_PATH_ISSUE_BILLING, {
                "authKey": auth_key,
                "customerKey": customer_key,
            })
            billing_key = issued.get("billingKey")
            # 카드 메타(브랜드/마스킹 정보 등)
            card = (issued.get("card") or {}) if isinstance(issued, dict) else {}
            brand = card.get("issuerCode") or card.get("company") or None
            last4 = card.get("number", "")[-4:] if card.get("number") else None
            expiry_ym = card.get("expiryMonth") and card.get("expiryYear")
            if expiry_ym:
                expiry_ym = f"{card.get('expiryYear')}-{str(card.get('expiryMonth')).zfill(2)}"
            if not billing_key:
                raise RuntimeError("No billingKey in Toss response")

            # 2-2) DB에 PaymentMethod 저장(있으면 교체/활성화)
            from models import PaymentMethod, Subscription, Payment
            with db.session.begin():
                # 기존 활성 결제수단 비활성화(선택)
                db.session.query(PaymentMethod).filter(
                    PaymentMethod.user_id == user.user_id,
                    PaymentMethod.status == "active"
                ).update({"status": "inactive"})

                pm = PaymentMethod(
                    user_id=user.user_id,
                    provider="toss",
                    billing_key=billing_key,
                    brand=brand,
                    last4=last4,
                    expiry_ym=expiry_ym,
                    status="active",
                )
                db.session.add(pm)
                db.session.flush()  # pm.id 사용을 위해

                # 2-3) 구독 레코드 생성(없으면)
                plan_name = "pro_monthly"
                plan_amount = 6900  # KRW
                now_kst = datetime.now(KST)
                anchor_day = _compute_anchor_day(now_kst)
                # 이번 주기: 오늘 ~ 다음달 같은 날짜 전날
                start_d = now_kst.date()
                # next billing은 다음 anchor(다음달 동일 일자 00:00 KST 가정)
                if start_d.month == 12:
                    next_billing = datetime(start_d.year + 1, 1, min(anchor_day, 28), tzinfo=KST)
                else:
                    next_billing = datetime(start_d.year, start_d.month + 1, min(anchor_day, 28), tzinfo=KST)

                sub = Subscription(
                    user_id=user.user_id,
                    status="active",
                    plan_name=plan_name,
                    plan_amount=plan_amount,
                    anchor_day=anchor_day,
                    current_period_start=start_d,
                    current_period_end=None,  # 필요시 채우기
                    next_billing_at=next_billing.astimezone(timezone.utc),
                    default_payment_method_id=pm.id,
                )
                db.session.add(sub)
                db.session.flush()

                # 2-4) 첫 결제(즉시) 시도
                order_id = _new_order_id("first")
                idempo = _new_idempo()
                pay_req = {
                    "billingKey": billing_key,
                    "orderId": order_id,
                    "amount": int(plan_amount),
                    "orderName": "Lexinoa Pro 월구독(첫 결제)",
                    "customerKey": customer_key,
                    "currency": "KRW",
                    "useEscrow": False,
                    "taxFreeAmount": 0,
                    "metadata": {"user_id": user.user_id, "subscription_id": sub.id},
                }

                # 결제 row 미리 pending으로 생성(멱등/추적)
                pay_row = Payment(
                    user_id=user.user_id,
                    subscription_id=sub.id,
                    provider="toss",
                    order_id=order_id,
                    idempotency_key=idempo,
                    amount=plan_amount,
                    currency="KRW",
                    status="pending",
                    raw_request=pay_req,
                )
                db.session.add(pay_row)
                db.session.flush()
        except Exception as e:
            db.session.rollback()
            return render_template("subscribe.html", error=f"결제수단 등록 실패: {e}")

        # 2-5) 서버-서버 결제 호출
        try:
            paid = toss_request("POST", TOSS_PATH_PAY_WITH_BILLING, pay_req)
            txid = paid.get("paymentKey") or paid.get("transactionId")
            with db.session.begin():
                pr = Payment.query.filter_by(order_id=order_id).first()
                pr.status = "captured"
                pr.psp_transaction_id = txid
                pr.raw_response = paid
                db.session.add(pr)
        except Exception as e:
            # 실패 기록
            with db.session.begin():
                pr = Payment.query.filter_by(order_id=order_id).first()
                pr.status = "failed"
                pr.failure_message = str(e)
                # 실패 응답도 raw_response에 담을 수 있으면 담기
                try:
                    msg = str(e)
                    if "Toss API error" in msg and ":" in msg:
                        # 러프 파싱
                        pr.failure_code = "TOSS_API_ERROR"
                except Exception:
                    pass
                db.session.add(pr)
            return render_template("subscribe.html", error=f"첫 결제 실패: {e}")

        # 성공
        return redirect(url_for("mypage_overview"))

    # 실패 콜백(선택)
    @app.route("/toss/fail", methods=["GET"])
    def toss_checkout_fail():
        code = request.args.get("code")
        msg = request.args.get("message")
        ui = translate_toss_error(code, msg, status=400)
        current_app.logger.warning("TOSS_FAIL code=%s msg=%s", code, msg)
        session["pay_error"] = {"code": ui.code, "message": ui.message, "severity": ui.severity}
        return redirect(url_for("subscribe_page") + "?pay=failed", code=303)

    # ---- 3) 웹훅 수신 (멱등/서명검증 → 상태반영) ----
    @app.route("/webhooks/toss", methods=["POST"])
    @csrf.exempt
    def toss_webhook():
        payload = request.get_json(force=True, silent=True) or {}
        # (권장) Toss 서명 검증 — 공식 문서대로 구현
        # ex) header: Toss-Signature / x-toss-request-id 등 활용
        signature_valid = True  # TODO: 문서대로 검증 구현

        event_id = str(payload.get("eventId") or payload.get("paymentKey") or uuid.uuid4().hex)
        event_type = str(payload.get("status") or payload.get("eventType") or "")

        from models import WebhookEvent, Payment
        # 멱등 저장
        try:
            with db.session.begin():
                exists = WebhookEvent.query.filter_by(event_id=event_id).first()
                if exists:
                    return jsonify({"ok": True, "dup": True}), 200
                wh = WebhookEvent(
                    event_id=event_id,
                    event_type=event_type,
                    signature_valid=bool(signature_valid),
                    payload=payload,
                    processed=False,
                )
                db.session.add(wh)
        except Exception:
            db.session.rollback()
            return jsonify({"ok": False}), 500

        # 상태 반영 (예: 결제 완료/실패)
        try:
            order_id = None
            # 토스 웹훅 payload에 상점 orderId/metadata가 포함되도록 요청 시 넘겼다면 여기서 매칭
            order_id = (payload.get("orderId") or
                        ((payload.get("data") or {}).get("orderId")))

            if order_id:
                with db.session.begin():
                    p = Payment.query.filter_by(order_id=order_id).first()
                    if p:
                        status = (payload.get("status") or "").lower()
                        if status in ("done", "approved", "paid", "captured"):
                            p.status = "captured"
                        elif status in ("canceled", "refunded"):
                            p.status = "refunded"
                        elif status in ("failed", "declined"):
                            p.status = "failed"
                            p.failure_message = str(payload)
                        db.session.add(p)

            with db.session.begin():
                wh = WebhookEvent.query.filter_by(event_id=event_id).first()
                if wh:
                    wh.processed = True
                    wh.processed_at = _utcnow()
                    db.session.add(wh)

        except Exception:
            db.session.rollback()

        return jsonify({"ok": True}), 200

    # ---- 4) 정기 청구 스케줄러 — 내부용 Cron 엔드포인트 ----
    @app.route("/internal/cron/bill-due", methods=["POST"])
    @csrf.exempt
    def cron_bill_due():
        """
        - 서버 크론 또는 외부 스케줄러(Cloud Scheduler 등)가 1일 1회 호출.
        - 오늘 anchor_day인 구독을 찾아 `next_billing_at <= now` 인 것만 청구.
        - 헤더 Authorization: Bearer <CRON_SECRET> 체크.
        """
        auth = request.headers.get("Authorization", "")
        want = f"Bearer {os.getenv('CRON_SECRET', '')}"
        if not want or auth != want:
            return jsonify({"ok": False, "error": "forbidden"}), 403

        from models import Subscription, PaymentMethod, Payment
        now_utc = _utcnow()

        due = (
            Subscription.query
            .filter(
                Subscription.status == "active",
                Subscription.next_billing_at != None,  # noqa: E711
                Subscription.next_billing_at <= now_utc
            )
            .all()
        )

        charged = 0
        for sub in due:
            # 결제수단
            pm = None
            if sub.default_payment_method_id:
                pm = db.session.get(type('PM', (), {'__tablename__': 'payment_methods'}), sub.default_payment_method_id)
            if not pm:
                pm = None
                pm = db.session.query(db.Model.metadata.tables['payment_methods']).filter_by(
                    id=sub.default_payment_method_id
                ).first()

            # 안전하게 다시 조회
            from models import PaymentMethod as PM
            pm = PM.query.get(sub.default_payment_method_id) if sub.default_payment_method_id else None
            if not pm or pm.status != "active":
                continue  # 다음번에 재시도

            order_id = _new_order_id("recurr")
            idempo = _new_idempo()
            req = {
                "billingKey": pm.billing_key,
                "orderId": order_id,
                "amount": int(sub.plan_amount),
                "orderName": f"Lexinoa Pro 월구독",
                "customerKey": f"u_{sub.user_id}",
                "currency": "KRW",
                "useEscrow": False,
                "taxFreeAmount": 0,
                "metadata": {"user_id": sub.user_id, "subscription_id": sub.id},
            }

            # Payment row 생성
            with db.session.begin():
                prow = Payment(
                    user_id=sub.user_id,
                    subscription_id=sub.id,
                    provider="toss",
                    order_id=order_id,
                    idempotency_key=idempo,
                    amount=sub.plan_amount,
                    currency="KRW",
                    status="pending",
                    raw_request=req,
                )
                db.session.add(prow)
                db.session.flush()

            # 토스 결제 시도
            try:
                res = toss_request("POST", TOSS_PATH_PAY_WITH_BILLING, req)
                tx = res.get("paymentKey") or res.get("transactionId")
                with db.session.begin():
                    prow = Payment.query.filter_by(order_id=order_id).first()
                    prow.status = "captured"
                    prow.psp_transaction_id = tx
                    prow.raw_response = res
                    db.session.add(prow)

                    # 다음 청구일 갱신
                    cur = sub.next_billing_at.astimezone(KST)
                    # 다음달 같은 날(예외: 말일 보정은 28일로 최소화)
                    if cur.month == 12:
                        nxt = datetime(cur.year + 1, 1, min(sub.anchor_day or cur.day, 28), tzinfo=KST)
                    else:
                        nxt = datetime(cur.year, cur.month + 1, min(sub.anchor_day or cur.day, 28), tzinfo=KST)
                    sub.next_billing_at = nxt.astimezone(timezone.utc)
                    db.session.add(sub)
                charged += 1
            except Exception as e:
                with db.session.begin():
                    prow = Payment.query.filter_by(order_id=order_id).first()
                    prow.status = "failed"
                    prow.failure_message = str(e)
                    db.session.add(prow)
                # 실패 구독은 다음 실행 때 다시 시도(별도 재시도 정책 필요시 큐 도입)
                continue

        return jsonify({"ok": True, "charged": charged, "due_count": len(due)}), 200


    #크롬 확장 팝업에서 사용
    @csrf.exempt
    @app.route("/api/auth/status", methods=["GET"])
    def api_auth_status():
        u = get_current_user()
        if not u:
            return jsonify({"logged_in": False, "tier": "guest"}), 200
        tier = "pro" if has_active_subscription(u) else "free"
        return jsonify({
            "logged_in": True,
            "tier": tier,
            "user_id": u.user_id,
            "email": u.email,
            "email_verified": bool(u.email_verified),
            "features": list(FEATURES_BY_TIER.get(tier, set())),
            "n_outputs": outputs_for_tier()
        }), 200

    #크롬 확장 팝업에서 사용
    @csrf.exempt
    @app.route("/api/history", methods=["GET"])
    def api_history():
        user = get_current_user()
        if not user:
            return jsonify({"error": "login_required"}), 401
        # Pro만 허용(요구사항 반영)
        if resolve_tier() != "pro":
            return jsonify({"error": "pro_required"}), 403
        try:
            limit = max(1, min(int(request.args.get("limit", 20)), 100))
        except Exception:
            limit = 20
        rows = (
            RewriteLog.query.filter_by(user_id=user.user_id)
            .order_by(RewriteLog.created_at.desc())
            .limit(limit).all()
        )
        items = [{
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "input_text": r.input_text,
            "output_text": r.output_text,
            "categories": r.categories,
            "tones": r.tones,
            "model": r.model_name
        } for r in rows]
        return jsonify({"items": items}), 200

    @app.route("/health")
    def health():
        return "ok", 200

    @app.route("/history")
    def user_history():
        user = session.get("user")
        if not user:
            return redirect(url_for("auth.login_page"))
        user_id = user.get("user_id")
        logs = (
            RewriteLog.query.filter_by(user_id=user_id)
            .order_by(RewriteLog.created_at.desc())
            .all()
        )
        return render_template("history.html", logs=logs, user=user)

    def _read_text_or_file(val: str) -> str:
        if not val:
            return ""
        # 파일 경로가 존재하면 파일에서 읽고, 아니면 그대로 내용으로 간주
        try:
            if os.path.exists(val):
                with open(val, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception:
            pass
        return val

    @app.route("/ads.txt")
    def ads_txt():
        body = _read_text_or_file(ADS_TXT).strip()
        # 예: "google.com, pub-xxxxxxxxxxxxxxxx, DIRECT, f08c47fec0942fa0"
        return (body or ""), 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600"}

    @app.route("/app-ads.txt")
    def app_ads_txt():
        body = _read_text_or_file(APP_ADS_TXT).strip()
        return (body or ""), 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600"}

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/disclaimer")
    def disclaimer():
        return render_template("disclaimer.html")

    # ----- 구독/가격 -----
    @app.route("/subscribe", methods=["GET"])
    def subscribe_page():
        return render_template("subscribe.html")

    @app.route("/pricing", methods=["GET"])
    def pricing_alias():
        return redirect(url_for("subscribe_page"))


    #결제 창
    @app.route("/subscribe/checkout", methods=["GET"])
    def subscribe_checkout():
        # 로그인/이메일 인증 같은 선행검사는 여기서 필요하면 추가
        return render_template("checkout.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
