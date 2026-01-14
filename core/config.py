import os


def _csv(v: str):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


# TODO:: Config 에서는 환경변수 설정만
class Config:
    # Flask 보안 키
    SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret")

    ENV = os.getenv("FLASK_ENV", "production")

    # DB
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # 제공자(LLM)
    PROVIDER_DEFAULT = os.getenv("PROVIDER_DEFAULT", "claude").lower()

    # Admin
    ADMIN_ID = os.getenv("ADMIN_ID", "")

    # 게스트 식별 쿠키
    AID_COOKIE = "aid"
    GUEST_SALT = os.getenv("GUEST_SALT")

    # 비밀번호/이메일 인증(기존 유지)
    RESET_SALT = "password-reset-v1"
    RESET_TTL = 60 * 5
    RESET_TOKEN_BYTES = 32
    RESET_TOKEN_TTL_SECONDS = 60 * 5

    VERIFY_SALT = "email-verify-v1"
    VERIFY_TTL_SECONDS = 60 * 30

    # reCAPTCHA
    RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET_KEY")
    RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")

    # 응답시간 평탄화
    MIN_RESP_MS = 450
    JITTER_MS = 200

    # -------------------------
    # CORS / Origin allowlist
    # -------------------------
    CORS_ORIGINS = _csv(os.getenv("CORS_ORIGINS", "https://www.lexinoa.com/"))
    API_ALLOWED_ORIGINS = [o.rstrip("/") for o in _csv(os.getenv(
        "API_ALLOWED_ORIGINS",
        "https://www.lexinoa.com/,http://localhost:3000,http://127.0.0.1:3000/,http://127.0.0.1:5000/",
    ))]

    # -------------------------
    # Chrome extension origins
    # -------------------------
    EXTENSION_IDS = _csv(os.getenv("EXTENSION_IDS", ""))
    EXT_ORIGINS = [f"chrome-extension://{eid}" for eid in EXTENSION_IDS]

    # -------------------------
    # Rate limiting (Flask-Limiter 표준 키)
    # -------------------------
    REDIS_URL = os.getenv("REDIS_URL", "")
    RATELIMIT_STORAGE_URI = REDIS_URL if REDIS_URL else "memory://"
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per hour")

    # -------------------------
    # Nicepay
    # -------------------------
    NICEPAY_API_BASE = os.getenv("NICEPAY_API_BASE", "https://sandbox-api.nicepay.co.kr").rstrip("/")
    NICEPAY_CLIENT_ID = os.getenv("NICEPAY_CLIENT_ID", "").strip()
    NICEPAY_SECRET_KEY = os.getenv("NICEPAY_SECRET_KEY", "").strip()

    NICEPAY_PATH_SUBSCRIBE_PAY = "/v1/subscribe/{bid}/payments"
    NICEPAY_PATH_SUBSCRIBE_EXPIRE = "/v1/subscribe/{bid}/expire"
    NICEPAY_PATH_APPROVE_PAYMENT = "/v1/payments/{tid}"
    NICEPAY_PATH_SUBSCRIBE_REGIST = "/v1/subscribe/regist"

    # payments toggle 배포 전 후 이걸로 on / off
    PAYMENTS_ENABLED = _env_bool("PAYMENTS_ENABLED", default=False)


    # -------------------------
    # Ads
    # -------------------------
    ADS_ENABLED = _env_bool("ADS_ENABLED", False)
    # Provider는 ADS_ENABLED일 때만 의미 있음
    ADS_PROVIDER = os.getenv("ADS_PROVIDER", "").strip().lower() if ADS_ENABLED else ""
    # --- AdSense ---
    ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "").strip()
    # --- Kakao AdFit ---
    ADFIT_UNIT_ID = os.getenv("ADFIT_UNIT_ID", "").strip()
    # --- Naver ---
    NAVER_AD_UNIT = os.getenv("NAVER_AD_UNIT", "").strip()
    # --- ads.txt ---
    ADS_TXT = os.getenv("ADS_TXT", "").strip()
    APP_ADS_TXT = os.getenv("APP_ADS_TXT", "").strip()
    # -------------------------
    # Sanity check (fail-safe)
    # -------------------------
    if ADS_ENABLED:
        if ADS_PROVIDER == "adsense" and not ADSENSE_CLIENT:
            # client 없으면 자동 비활성화 (운영 안전)
            ADS_ENABLED = False
        elif ADS_PROVIDER == "kakao" and not ADFIT_UNIT_ID:
            ADS_ENABLED = False
        elif ADS_PROVIDER == "naver" and not NAVER_AD_UNIT:
            ADS_ENABLED = False

    print("[ADS CONFIG]", ADS_ENABLED, ADS_PROVIDER, ADSENSE_CLIENT)

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
        "guest": {"daily": 5},    # 하루 5회 (scope별 한도 — rewrite / summarize 각각 5회)
        "free": {"monthly": 30},  # 월 30회 (scope별)
        "pro": {"monthly": 1000}, # 월 1000회 (scope별)
    }

    # 허용 스코프(서비스 키) — 여기 추가하면 확장 가능 (summarize 없앨지 고민중)
    USAGE_SCOPES = {"rewrite", "summarize"}

    # -------------------------
    # i18n (Flask-Babel)
    # -------------------------
    LANGUAGES = ["ko", "en"]
    BABEL_DEFAULT_LOCALE = "ko"
    BABEL_DEFAULT_TIMEZONE = "Asia/Seoul"
