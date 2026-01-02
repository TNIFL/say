from __future__ import annotations

from flask import Blueprint, request, redirect, jsonify, url_for
from core.extensions import csrf
from auth.entitlements import get_current_user
from services.extension_oauth import issue_auth_code, exchange_code_for_token


api_extension_oauth_bp = Blueprint("api_extension_oauth", __name__)


@api_extension_oauth_bp.route("/extension/oauth/authorize", methods=["GET"])
def extension_oauth_authorize():
    """
    확장이 launchWebAuthFlow로 여는 엔드포인트.
    - 로그인되어 있으면: code 발급 후 redirect_uri로 리다이렉트
    - 로그인 안 되어 있으면: 로그인 페이지로 보내고, 로그인 후 다시 이 URL로 돌아오게 next 설정
    """
    redirect_uri = request.args.get("redirect_uri", "").strip()
    code_challenge = request.args.get("code_challenge", "").strip()
    state = request.args.get("state", "").strip() or None

    if not redirect_uri or not code_challenge:
        return "missing redirect_uri or code_challenge", 400

    user = get_current_user()
    if not user:
        # 로그인 후 다시 authorize로 복귀
        return redirect(url_for("auth.login_page", next=request.full_path))

    code = issue_auth_code(
        user_id=user.user_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        state=state,
        ttl_minutes=5,
    )

    # redirect_uri 로 code 전달
    sep = "&" if "?" in redirect_uri else "?"
    out = f"{redirect_uri}{sep}code={code}"
    if state:
        out += f"&state={state}"
    return redirect(out, code=302)


@api_extension_oauth_bp.route("/extension/oauth/token", methods=["POST"])
@csrf.exempt
def extension_oauth_token():
    """
    확장이 code를 access_token으로 교환하는 엔드포인트.
    - 세션 쿠키 없이 동작해야 하므로 CSRF exempt
    """
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    code_verifier = (data.get("code_verifier") or "").strip()
    redirect_uri = (data.get("redirect_uri") or "").strip()

    if not code or not code_verifier or not redirect_uri:
        return jsonify({"ok": False, "error": "missing_params"}), 400

    result = exchange_code_for_token(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        note="chrome-oauth",
        token_expires_days=None,  # 만료 원하면 90 등으로 변경
    )

    if not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result), 200
