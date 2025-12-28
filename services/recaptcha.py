import requests
from flask import current_app


# reCAPTCHA v2
def verify_recaptcha_v2(response_token, remote_ip=None):
    cfg = current_app.config
    payload = {"secret": cfg.get("RECAPTCHA_SECRET"), "response": response_token}
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

