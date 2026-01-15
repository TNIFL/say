from datetime import datetime, timezone
from flask import Blueprint, Response, url_for, request

from routes.web.learn import SLUG_MAP

sitemap_bp = Blueprint("sitemap", __name__)

def _today():
    return datetime.now(timezone.utc).date().isoformat()

def _base_url():
    # 예: http://127.0.0.1:5000/
    return request.url_root.rstrip("/")

def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )

@sitemap_bp.route("/sitemap.xml")
def sitemap_xml():
    today = _today()
    base = _base_url()

    # 블로그 POSTS를 안전하게 로딩 (순환 import 방지)
    try:
        from routes.web.blog import POSTS
        ko_slugs = {p["slug"] for p in POSTS.get("ko", [])}
        en_slugs = {p["slug"] for p in POSTS.get("en", [])}
        blog_slugs = sorted(ko_slugs | en_slugs)
    except Exception:
        blog_slugs = []

    urls = []

    def add_url(loc: str, lastmod: str = today, alternates=None):
        """
        alternates: list of dicts: [{"hreflang":"en","href":"..."}, ...]
        """
        urls.append({
            "loc": loc,
            "lastmod": lastmod,
            "alternates": alternates or []
        })

    # 1) 홈 (있으면 추가)
    try:
        add_url(url_for("index", _external=True), today)
    except Exception:
        # index 엔드포인트가 없다면 스킵
        pass

    # 2) Learn
    try:
        add_url(url_for("learn.learn_index", _external=True), today)
        for slug in sorted(SLUG_MAP.keys()):
            add_url(url_for("learn.learn_page", slug=slug, _external=True), today)
    except Exception:
        pass

    # 3) Blog index (ko/en) + hreflang
    blog_ko = f"{base}/blog"
    blog_en = f"{base}/en/blog"
    add_url(
        blog_ko,
        today,
        alternates=[
            {"hreflang": "ko", "href": blog_ko},
            {"hreflang": "en", "href": blog_en},
            {"hreflang": "x-default", "href": blog_en},
        ],
    )
    add_url(
        blog_en,
        today,
        alternates=[
            {"hreflang": "en", "href": blog_en},
            {"hreflang": "ko", "href": blog_ko},
            {"hreflang": "x-default", "href": blog_en},
        ],
    )

    # 4) Blog posts (ko/en) + hreflang
    for slug in blog_slugs:
        ko_url = f"{base}/blog/{slug}"
        en_url = f"{base}/en/blog/{slug}"

        add_url(
            ko_url,
            today,
            alternates=[
                {"hreflang": "ko", "href": ko_url},
                {"hreflang": "en", "href": en_url},
                {"hreflang": "x-default", "href": en_url},
            ],
        )
        add_url(
            en_url,
            today,
            alternates=[
                {"hreflang": "en", "href": en_url},
                {"hreflang": "ko", "href": ko_url},
                {"hreflang": "x-default", "href": en_url},
            ],
        )

    # XML 생성 (xhtml namespace 포함: hreflang alternates)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    )

    for u in urls:
        lines.append("<url>")
        lines.append(f"<loc>{_xml_escape(u['loc'])}</loc>")
        lines.append(f"<lastmod>{_xml_escape(u['lastmod'])}</lastmod>")

        # hreflang alternates
        for alt in u["alternates"]:
            hreflang = _xml_escape(alt["hreflang"])
            href = _xml_escape(alt["href"])
            lines.append(f'<xhtml:link rel="alternate" hreflang="{hreflang}" href="{href}" />')

        lines.append("</url>")

    lines.append("</urlset>")

    return Response("\n".join(lines), mimetype="application/xml")
