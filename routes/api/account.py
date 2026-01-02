# routes/api/account.py
from __future__ import annotations

from flask import Blueprint, jsonify, request
from core.extensions import csrf
from auth.entitlements import get_current_user

from services.account_delete import (
    request_account_delete,
    restore_account,
)

api_account_bp = Blueprint("api_account", __name__)


# -------------------------
# 탈퇴 요청 (30일 유예)
# -------------------------
@api_account_bp.route("/api/account/delete", methods=["POST"])
@csrf.exempt
def api_account_delete():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401

    body = request.get_json(silent=True) or {}
    confirm = (body.get("confirm") or "").strip()
    reason = (body.get("reason") or "").strip() or None

    if confirm != "DELETE":
        return jsonify({"ok": False, "error": "confirm_required"}), 400

    result = request_account_delete(user.id, reason=reason)
    return jsonify(result), 200 if result.get("ok") else 400


# -------------------------
# 탈퇴 복구 (30일 내)
# -------------------------
@api_account_bp.route("/api/account/restore", methods=["POST"])
@csrf.exempt
def api_account_restore():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "login_required"}), 401

    result = restore_account(user.id)
    return jsonify(result), 200 if result.get("ok") else 400
