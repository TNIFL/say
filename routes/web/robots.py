from flask import Blueprint, Response, request

robots_bp = Blueprint("robots", __name__)

@robots_bp.route("/robots.txt")
def robots_txt():
    # 도메인 자동
    base = request.url_root.rstrip("/")
    content = f"""User-agent: *
Allow: /

Sitemap: {base}/sitemap.xml
"""
    return Response(content, mimetype="text/plain")
