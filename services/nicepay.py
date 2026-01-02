# services/nicepay.py
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import requests
from flask import current_app

from utils.time_utils import KST


def _nicepay_headers() -> dict:
    cfg = current_app.config
    client_id = (cfg.get("NICEPAY_CLIENT_ID") or "").strip()
    secret_key = (cfg.get("NICEPAY_SECRET_KEY") or "").strip()

    if not client_id or not secret_key:
        raise RuntimeError("NICEPAY_CLIENT_ID / NICEPAY_SECRET_KEY 환경변수가 설정되지 않았습니다.")

    basic = base64.b64encode(f"{client_id}:{secret_key}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/json",
    }


def _nicepay_iso8601_kst() -> str:
    now = datetime.now(KST)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + now.strftime("%z")


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sign_subscribe(order_id: str, bid: str, edi_date: str) -> str:
    cfg = current_app.config
    secret_key = cfg.get("NICEPAY_SECRET_KEY")
    return _sha256_hex(f"{order_id}{bid}{edi_date}{secret_key}")


def verify_signature(tid: str, amount: int, edi_date: str, signature: str) -> bool:
    if not signature:
        return False
    cfg = current_app.config
    secret_key = cfg.get("NICEPAY_SECRET_KEY")
    expected = _sha256_hex(f"{tid}{int(amount)}{edi_date}{secret_key}")
    return secrets.compare_digest(expected, signature)


def nicepay_request(method: str, path: str, json_body: dict):
    cfg = current_app.config
    base = (cfg.get("NICEPAY_API_BASE", "https://api.nicepay.co.kr") or "").rstrip("/")
    url = f"{base}{path}"

    r = requests.request(method.upper(), url, headers=_nicepay_headers(), json=json_body, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if not r.ok:
        raise RuntimeError(f"NICEPAY API error {r.status_code}: {data}")

    return data


def nicepay_subscribe_pay(
    bid: str,
    *,
    order_id: str,
    amount: int,
    goods_name: str,
    buyer_name: str,
    buyer_email: str,
) -> dict:
    cfg = current_app.config
    path_tpl = cfg.get("NICEPAY_PATH_SUBSCRIBE_PAY")  # "/v1/subscribe/{bid}/payments"
    if not path_tpl:
        raise RuntimeError("NICEPAY_PATH_SUBSCRIBE_PAY 설정 누락")

    edi_date = _nicepay_iso8601_kst()
    sign_data = sign_subscribe(order_id, bid, edi_date)

    req = {
        "orderId": order_id,
        "amount": int(amount),
        "goodsName": goods_name,
        "cardQuota": "0",
        "useShopInterest": False,
        "buyerName": buyer_name,
        "buyerEmail": buyer_email or "",
        "ediDate": edi_date,
        "signData": sign_data,
        "returnCharSet": "utf-8",
    }
    return nicepay_request("POST", path_tpl.format(bid=bid), req)


def nicepay_expire_bid(bid: str, *, order_id: str) -> dict:
    cfg = current_app.config
    path_tpl = cfg.get("NICEPAY_PATH_SUBSCRIBE_EXPIRE")  # "/v1/subscribe/{bid}/expire"
    if not path_tpl:
        raise RuntimeError("NICEPAY_PATH_SUBSCRIBE_EXPIRE 설정 누락")

    edi_date = _nicepay_iso8601_kst()
    sign_data = sign_subscribe(order_id, bid, edi_date)

    req = {
        "orderId": order_id,
        "ediDate": edi_date,
        "signData": sign_data,
        "returnCharSet": "utf-8",
    }
    return nicepay_request("POST", path_tpl.format(bid=bid), req)


# -----------------------------
# API v1 (JS SDK) - Server Approve / BillingKey Regist
# -----------------------------
def nicepay_approve_payment(*, tid: str, amount: int) -> dict:
    """
    결제창 인증 후 서버 승인:
    POST /v1/payments/{tid}
    """
    cfg = current_app.config
    path_tpl = cfg.get("NICEPAY_PATH_APPROVE_PAYMENT") or "/v1/payments/{tid}"
    req = {"amount": int(amount)}
    return nicepay_request("POST", path_tpl.format(tid=tid), req)


def nicepay_regist_billing_key(*, customer_id: str, tid: str) -> dict:
    """
    빌키(BID) 발급:
    POST /v1/subscribe/regist
    """
    cfg = current_app.config
    path = cfg.get("NICEPAY_PATH_SUBSCRIBE_REGIST") or "/v1/subscribe/regist"
    req = {"customerId": customer_id, "tid": tid}
    return nicepay_request("POST", path, req)


def new_order_id(prefix: str = "sub") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def utc_naive(dt_aware) -> datetime:
    return dt_aware.astimezone(timezone.utc).replace(tzinfo=None)


# --- Backward-compatible aliases (DO NOT REMOVE) ---
_new_order_id = new_order_id
_nicepay_iso8601_kst = _nicepay_iso8601_kst
_nicepay_sign_pay = sign_subscribe
_nicepay_sign_expire = sign_subscribe
_nicepay_verify_signature = verify_signature
