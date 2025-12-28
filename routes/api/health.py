from flask import Blueprint

api_health_bp = Blueprint("api_health", __name__)

@api_health_bp.route("/health")
def health():
    return "ok", 200
