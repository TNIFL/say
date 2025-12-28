from functools import wraps
import time as time_module
from flask import make_response, jsonify


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


# api 응답시간 평탄화
def _sleep_floor(start_t: float, min_ms: int = 450, jitter_ms: int = 200) -> None:
    elapsed_ms = int((time_module.perf_counter() - start_t) * 1000)
    floor_ms = min_ms  # 필요시 jitter 포함 로직
    remain = floor_ms - elapsed_ms
    if remain > 0:
        time_module.sleep(remain / 1000)


# api 공통 응답
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