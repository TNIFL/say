from datetime import datetime, timezone
from flask import Blueprint, Response, url_for

from routes.web.learn import SLUG_MAP

sitemap_bp = Blueprint("sitemap", __name__)

@sitemap_bp.route("/sitemap.xml")
def sitemap_xml():
    today = datetime.now(timezone.utc).date().isoformat()

    urls = []

    try:
        urls.append({"loc": url_for("index", _external=True), "lastmod": today})
    except Exception:
        pass

    urls.append({"loc": url_for("learn.learn_index", _external=True), "lastmod": today})

    for slug in sorted(SLUG_MAP.keys()):
        urls.append({"loc": url_for("learn.learn_page", slug=slug, _external=True), "lastmod": today})

    # XML 생성
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for u in urls:
        lines.append("<url>")
        lines.append(f"<loc>{u['loc']}</loc>")
        lines.append(f"<lastmod>{u['lastmod']}</lastmod>")
        lines.append("</url>")

    lines.append("</urlset>")

    return Response("\n".join(lines), mimetype="application/xml")
