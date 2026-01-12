import os
from flask import Blueprint, redirect, request, session, current_app
from werkzeug.security import generate_password_hash
from secrets import token_urlsafe

from core.extensions import oauth, db
from domain.models import User, OAuthIdentity


google_auth_bp = Blueprint("google_auth", __name__, url_prefix="/auth")


def nickname_from_email(email: str) -> str:
    # 이메일 앞부분만 사용 (최대 20자)
    if not email or "@" not in email:
        return "user"
    return email.split("@", 1)[0][:20]


def _register_google_client():
    """
    Authlib OAuth client를 최초 1회 등록.
    """
    if getattr(oauth, "google", None):
        return oauth.google

    oauth.register(
        name="google",
        server_metadata_url=os.getenv(
            "GOOGLE_DISCOVERY_URL",
            "https://accounts.google.com/.well-known/openid-configuration",
        ),
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth.google


def _make_unique_user_id(base: str) -> str:
    """
    users.user_id는 unique + not null 이므로 충돌을 피해서 생성.
    """
    base = (base or "google_user").strip()
    if len(base) > 200:
        base = base[:200]

    candidate = base
    i = 0
    while User.query.filter_by(user_id=candidate).first() is not None:
        i += 1
        candidate = f"{base}_{i}"
        if len(candidate) > 255:
            candidate = candidate[:255]
    return candidate


@google_auth_bp.get("/login/google")
def login_google():
    google = _register_google_client()

    # 로그인 후 돌아갈 페이지(원하면 next= 로 제어)
    next_url = request.args.get("next") or "/"
    session["post_login_redirect"] = next_url
    # nonce 생성/저장
    session["oidc_nonce"] = token_urlsafe(24)

    # 운영 : https://www.lexinoa.com/auth/callback/google
    # 로컬 : http://127.0.0.1:5000/auth/callback/google
    redirect_uri = "https://www.lexinoa.com/auth/callback/google"
    return google.authorize_redirect(
        redirect_uri,
        nonce=session["oidc_nonce"],
    )


@google_auth_bp.get("/callback/google")
def callback_google():
    google = _register_google_client()

    token = google.authorize_access_token()

    nonce = session.pop("oidc_nonce", None)
    if not nonce:
        current_app.logger.warning("Missing oidc_nonce. args=%s", dict(request.args))
        return "Missing OIDC nonce. Please restart login.", 400

    userinfo = google.parse_id_token(token, nonce=nonce)

    provider = "google"
    provider_sub = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower()
    email_verified = bool(userinfo.get("email_verified", False))

    if not provider_sub:
        return "Google login failed: missing sub", 400
    if not email:
        return "Google login failed: missing email", 400

    ident = OAuthIdentity.query.filter_by(provider=provider, provider_sub=provider_sub).first()

    if ident:
        user = User.query.get(ident.user_pk)
        if user and user.email != email:
            user.email = email
        if ident.email != email:
            ident.email = email
        db.session.commit()
    else:
        user = User.query.filter_by(email=email).first()
        if user and not user.display_name:
            user.display_name = nickname_from_email(email)
            db.session.commit()
        if not user:
            base_user_id = f"google_{provider_sub[-12:]}"
            new_user_id = _make_unique_user_id(base_user_id)

            random_pw = token_urlsafe(32)
            pw_hash = generate_password_hash(random_pw, method="pbkdf2:sha256", salt_length=16)

            user = User(
                user_id=new_user_id,
                email=email,
                password_hash=pw_hash,
                is_active=True,
                is_admin=False,
                email_verified=email_verified,
                display_name=nickname_from_email(email),
            )
            db.session.add(user)
            db.session.flush()

        ident = OAuthIdentity(
            provider=provider,
            provider_sub=provider_sub,
            user_pk=user.id,
            email=email,
        )
        db.session.add(ident)
        db.session.commit()

    # clear 전에 next_url 확보
    next_url = session.pop("post_login_redirect", None) or "/"

    # 로그인 세션 세팅
    session.clear()
    session["user"] = {"user_id": user.user_id, "email": user.email}
    session["csrf_guard"] = token_urlsafe(24)
    session.permanent = True

    return redirect(next_url)
