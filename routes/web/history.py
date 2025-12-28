from flask import render_template, Blueprint, session, redirect, url_for
from domain.models import RewriteLog

history_bp = Blueprint("history", __name__)


@history_bp.route("/history")
def user_history():
    user = session.get("user")
    if not user:
        return redirect(url_for("auth.login_page"))
    user_id = user.get("user_id")
    logs = (
        RewriteLog.query.filter_by(user_id=user_id)
        .order_by(RewriteLog.created_at.desc())
        .all()
    )
    return render_template("history.html", logs=logs, user=user)