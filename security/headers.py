import secrets
from flask import g, current_app


def init_security_headers(app):

    @app.before_request
    def _make_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def add_security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=15552000; includeSubDomains; preload"
        )

        nonce = getattr(g, "csp_nonce", "")

        # -----------------------------
        # Base CSP (Toss 제거 / Nicepay 추가)
        # -----------------------------
        csp = (
            "default-src 'self'; "

            # 이미지(필요 시 nicepay 쪽 이미지가 있으면 *.nicepay.co.kr 추가 가능)
            "img-src 'self' data: https://www.gstatic.com/recaptcha/; "

            # 스타일: 기존 유지 (unsafe-inline 허용)
            "style-src 'self' 'unsafe-inline'; "

            # 스크립트: recaptcha + nicepay 결제창
            f"script-src 'self' 'nonce-{nonce}' "
            "https://www.google.com/recaptcha/ "
            "https://www.gstatic.com/recaptcha/ "
            "https://pay.nicepay.co.kr "
            "https://*.nicepay.co.kr; "

            # 프레임: recaptcha + nicepay 결제창(대부분 iframe/redirect 기반)
            "frame-src "
            "https://www.google.com/ "
            "https://www.gstatic.com/ "
            "https://pay.nicepay.co.kr "
            "https://*.nicepay.co.kr; "

            # 네트워크: 서버/브라우저에서 nicepay로 호출이 발생할 수 있어 허용
            "connect-src 'self' "
            "https://pay.nicepay.co.kr "
            "https://*.nicepay.co.kr; "

            # 결제창이 form submit을 쓸 수 있어서 허용(없으면 다음 단계에서 막히는 케이스 있음)
            "form-action 'self' "
            "https://pay.nicepay.co.kr "
            "https://*.nicepay.co.kr; "
        )

        cfg = current_app.config

        # -----------------------------
        # Ads allowlist (기존 유지)
        # -----------------------------
        if cfg.get("ADS_ENABLED"):
            provider = cfg.get("ADS_PROVIDER")

            if provider == "adsense":
                csp += (
                    "script-src-elem 'self' https://pagead2.googlesyndication.com https://www.googletagservices.com; "
                    "img-src 'self' data: https://pagead2.googlesyndication.com https://tpc.googlesyndication.com https://googleads.g.doubleclick.net; "
                    "frame-src https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com; "
                    "connect-src 'self' https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com; "
                )

            elif provider == "kakao":
                csp += (
                    "script-src-elem 'self' https://ad.kakao.com https://adfit.ad.daum.net https://t1.daumcdn.net; "
                    "img-src 'self' data: https://t1.daumcdn.net https://ad.kakao.com https://adfit.ad.daum.net; "
                    "frame-src https://ad.kakao.com https://adfit.ad.daum.net https://t1.daumcdn.net; "
                    "connect-src 'self' https://ad.kakao.com https://adfit.ad.daum.net; "
                )

            elif provider == "naver":
                csp += (
                    "script-src-elem 'self' https://*.naver.com https://ssl.pstatic.net; "
                    "img-src 'self' data: https://*.naver.com https://ssl.pstatic.net; "
                    "frame-src https://*.naver.com https://ssl.pstatic.net; "
                    "connect-src 'self' https://*.naver.com https://ssl.pstatic.net; "
                )

        resp.headers.setdefault("Content-Security-Policy", csp)
        return resp

    @app.context_processor
    def _inject_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}
