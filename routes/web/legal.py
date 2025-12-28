from flask import render_template, Blueprint


legal_bp = Blueprint("legal", __name__)


@legal_bp.route("/terms")
def terms():
    return render_template("terms.html")

@legal_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")

@legal_bp.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")