import secrets
from flask import g, current_app


def init_security_headers(app):

    @app.before_request
    def _make_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def add_security_headers(resp):
        cfg = current_app.config
        nonce = getattr(g, "csp_nonce", "")

        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=15552000; includeSubDomains; preload"
        )

        # iframe 정책
        resp.headers.setdefault(
            "X-Frame-Options",
            "SAMEORIGIN" if cfg.get("ADS_ENABLED") else "DENY"
        )

        # -----------------------------
        # CSP 구성 요소 누적
        # -----------------------------
        script_src = [
            "'self'",
            f"'nonce-{nonce}'",
            "https://www.google.com/recaptcha/",
            "https://www.gstatic.com/recaptcha/",
            "https://pay.nicepay.co.kr",
            "https://*.nicepay.co.kr",
        ]

        img_src = [
            "'self'",
            "data:",
            "https://www.gstatic.com/recaptcha/",
        ]

        frame_src = [
            "https://www.google.com/",
            "https://www.gstatic.com/",
            "https://pay.nicepay.co.kr",
            "https://*.nicepay.co.kr",
        ]

        connect_src = [
            "'self'",
            "https://pay.nicepay.co.kr",
            "https://*.nicepay.co.kr",
        ]

        form_action = [
            "'self'",
            "https://pay.nicepay.co.kr",
            "https://*.nicepay.co.kr",
        ]

        # -----------------------------
        # AdSense 허용
        # -----------------------------
        if cfg.get("ADS_ENABLED") and cfg.get("ADS_PROVIDER") == "adsense":
            script_src += [
                "https://pagead2.googlesyndication.com",
                "https://www.googletagservices.com",
                "https://googleads.g.doubleclick.net",
            ]

            img_src += [
                "https://pagead2.googlesyndication.com",
                "https://tpc.googlesyndication.com",
                "https://googleads.g.doubleclick.net",
            ]

            frame_src += [
                "https://pagead2.googlesyndication.com",
                "https://tpc.googlesyndication.com",
                "https://googleads.g.doubleclick.net",
            ]

            connect_src += [
                "https://pagead2.googlesyndication.com",
                "https://googleads.g.doubleclick.net",
            ]

        # -----------------------------
        # CSP 문자열 조립 (script-src 단 1번!)
        # -----------------------------
        csp = (
            "default-src 'self'; "
            f"script-src {' '.join(script_src)}; "
            f"img-src {' '.join(img_src)}; "
            "style-src 'self' 'unsafe-inline'; "
            f"frame-src {' '.join(frame_src)}; "
            f"connect-src {' '.join(connect_src)}; "
            f"form-action {' '.join(form_action)}; "
        )

        resp.headers["Content-Security-Policy"] = csp
        return resp

    @app.context_processor
    def _inject_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}
