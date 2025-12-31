from auth.entitlements import load_current_user

from flask import request, g, session, abort, current_app

from domain.models import db, User, Visit


def load_user():
    load_current_user()

# -------------------- 유틸 --------------------


def mark_ads_allowed_path():
    # 광고를 노출하고 싶은 경로만 True (예: 메인/히스토리/마이페이지 상단 배너)
    ADS_PATHS = {"/", "/history", "/mypage", "/pricing", "/subscribe"}
    g.show_ads_here = (request.path in ADS_PATHS)

    # -------------------- 보안 훅/역할 로드 --------------------


def guard_payload_size():
    if request.content_length and request.content_length > 256 * 1024:
        abort(413)

def load_current_user_role():
    cfg = current_app.config
    g.is_admin = False

    user = getattr(g, "current_user", None)
    admin_id = cfg.get("ADMIN_ID")

    if user and getattr(user, "is_admin", False):
        g.is_admin = True
        return

    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if admin_id and uid and uid == admin_id:
        g.is_admin = True



# -------------------- 방문 로깅 --------------------

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


# -------------------- API Origin 검사 --------------------
# 이 함수의 역할
# 이 요청이 허용된 출처(Origin) 에서 온 것인지 판별하는 자체 검사기
# api 를 아무 사이트/아무 클라이언트가 막 호출하지 못하게 하려고, 요청 헤더를 보고 통과 / 차단 을 결정한다
def origin_allowed():
    origin = (request.headers.get("Origin") or "").rstrip("/")
    ref = (request.headers.get("Referer") or "").rstrip("/")
    this = (request.host_url or "").rstrip("/")
    cfg = current_app.config

    api_allowed_origins = cfg.get("API_ALLOWED_ORIGINS") or []
    ext_origins = cfg.get("EXT_ORIGINS") or []
    ext_ids = cfg.get("EXTENSION_IDS") or []

    # ---- debug (필요하면 잠깐 켜고 나중에 제거) ----
    # print("[ORIGIN] origin=", origin, "ref=", ref, "this=", this)

    # Chrome extension
    if origin.startswith("chrome-extension://"):
        ok = origin in {f"chrome-extension://{i}" for i in ext_ids}
        # print("[ORIGIN] chrome ok=", ok)
        return ok

    allowed = set(o.rstrip("/") for o in api_allowed_origins if o)
    allowed.add(this)
    allowed.update(o.rstrip("/") for o in ext_origins if o)

    # Origin 헤더 없는 same-origin 케이스 처리
    if not origin:
        # Referer가 same-origin이면 허용
        if ref and (ref.startswith(this + "/") or ref == this):
            return True
        # 개발환경 완화
        if current_app.config.get("ENV") == "development":
            return True
        return False

    if origin in allowed:
        return True

    # Referer는 보조 신호
    if ref:
        for a in allowed:
            if a and (ref.startswith(a + "/") or ref == a):
                return True

    return False




def origin_guard():
    path = request.path or ""

    if request.host.startswith("127.0.0.1") or request.host.startswith("localhost"):
        return None

    if not path.startswith("/api/"):
        return None

    # 표시용/기본 API 예외
    if path == "/api/usage":
        return None

    # 로그인된 사용자 요청은 Origin 검사 생략
    if getattr(g, "current_user", None):
        return None

    # 세션 기반 로그인도 허용
    sess = session.get("user") or {}
    if sess.get("user_id"):
        return None

    # 익명 API 요청만 Origin 검사
    if not origin_allowed():
        abort(403)

    return None



def register_hooks(app):
    app.before_request(load_user)
    app.before_request(mark_ads_allowed_path)
    app.before_request(guard_payload_size)
    app.before_request(load_current_user_role)
    app.before_request(log_visit)
    app.before_request(origin_guard)