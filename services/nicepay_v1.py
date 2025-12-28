# say/services/nicepay_v1.py
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from flask import current_app


@dataclass(frozen=True)
class NicepayConfig:
    client_id: str
    secret_key: str
    api_base: str  # https://sandbox-api.nicepay.co.kr or https://api.nicepay.co.kr


def _cfg() -> NicepayConfig:
    cfg = current_app.config
    client_id = (cfg.get("NICEPAY_CLIENT_ID") or "").strip()
    secret_key = (cfg.get("NICEPAY_SECRET_KEY") or "").strip()
    api_base = (cfg.get("NICEPAY_API_BASE") or "").strip()

    print("[nicepay_v1] api_base =", api_base)
    print("[nicepay_v1] client_id_tail =", client_id[-6:] if client_id else "")
    print("[nicepay_v1] secret_len =", len(secret_key))

    if not client_id or not secret_key:
        raise RuntimeError("NICEPAY_CLIENT_ID / NICEPAY_SECRET_KEY 환경변수가 설정되지 않았습니다.")
    if not api_base:
        raise RuntimeError("NICEPAY_API_BASE 환경변수가 설정되지 않았습니다.")

    return NicepayConfig(client_id=client_id, secret_key=secret_key, api_base=api_base.rstrip("/"))


def _basic_auth_header(client_id: str, secret_key: str) -> str:
    raw = f"{client_id}:{secret_key}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _cfg()
    url = f"{c.api_base}{path}"
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": _basic_auth_header(c.client_id, c.secret_key),
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
    # Nicepay는 실패 시에도 JSON 바디가 오는 경우가 많아 가급적 같이 로깅
    try:
        data = resp.json()
    except Exception:
        data = {"_raw": resp.text}

    if resp.status_code >= 400:
        raise RuntimeError(f"Nicepay API error {resp.status_code}: {data}")

    return data


def _get(path: str) -> Dict[str, Any]:
    c = _cfg()
    url = f"{c.api_base}{path}"
    headers = {"Authorization": _basic_auth_header(c.client_id, c.secret_key)}
    resp = requests.get(url, headers=headers, timeout=15)
    try:
        data = resp.json()
    except Exception:
        data = {"_raw": resp.text}

    if resp.status_code >= 400:
        raise RuntimeError(f"Nicepay API error {resp.status_code}: {data}")
    return data


# ---- v1 결제 승인 ----
def approve_payment(*, tid: str, amount: int) -> Dict[str, Any]:
    # POST /v1/payments/{tid}
    return _post(f"/v1/payments/{tid}", {"amount": amount})


# ---- v1 빌키 발급 ----
def regist_billing_key(*, customer_id: str, tid: str) -> Dict[str, Any]:
    """
    POST /v1/subscribe/regist
    - 문서상 tid 등으로 빌키 발급을 요청하며, 응답에 bid가 포함됨. :contentReference[oaicite:4]{index=4}
    - 샌드박스는 임의값 응답(너가 공유한 표와 동일)
    """
    return _post("/v1/subscribe/regist", {
        "customerId": customer_id,
        "tid": tid,
    })


# ---- v1 빌키로 결제(승인) ----
def pay_with_bid(*, bid: str, order_id: str, amount: int, goods_name: str) -> Dict[str, Any]:
    # POST /v1/subscribe/{bid}/payments
    return _post(f"/v1/subscribe/{bid}/payments", {
        "orderId": order_id,
        "amount": amount,
        "goodsName": goods_name,
    })


def expire_bid(*, bid: str) -> Dict[str, Any]:
    # POST /v1/subscribe/{bid}/expire
    return _post(f"/v1/subscribe/{bid}/expire", {})
