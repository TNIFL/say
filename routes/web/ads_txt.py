from flask import Blueprint, current_app

from utils.files import _read_text_or_file

ads_bp = Blueprint("ads", __name__)


@ads_bp.route("/ads.txt")
def ads_txt():
    cfg = current_app.config

    body = _read_text_or_file(cfg.get("ADS_TXT")).strip()
    # 예: "google.com, pub-xxxxxxxxxxxxxxxx, DIRECT, f08xxxxxxxxxxxxx"
    return (body or ""), 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600"}


@ads_bp.route("/app-ads.txt")
def app_ads_txt():
    cfg = current_app.config

    body = _read_text_or_file(cfg.get("APP_ADS_TXT")).strip()
    return (body or ""), 200, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600"}

