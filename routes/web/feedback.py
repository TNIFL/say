from flask import Blueprint, request, render_template, session, g

from domain.models import Feedback, db
from domain.schema import feedback_schema
from security.security import require_safe_input
from flask_babel import gettext as _

feedback_bp = Blueprint("feedback", __name__)

@feedback_bp.route("/feedback", methods=["GET", "POST"])
@require_safe_input(feedback_schema, form=True)
def feedback():
    success = None
    error = None

    sess = session.get("user", {}) or {}
    default_email = sess.get("email") or ""
    default_user_id = sess.get("user_id") or ""
    default_page = request.args.get("from") or request.referrer or "/"

    if g.safe_input:
        data = g.safe_input
        email = (data.get("email") or default_email).strip()
        user_id = (data.get("user_id") or default_user_id).strip()
        category = (data.get("category") or "general").strip()
        message = (data.get("message") or "").strip()
        page = (data.get("page") or default_page).strip()

        if not message:
            error = _("피드백 내용을 입력해 주세요.")
        else:
            try:
                fb = Feedback(
                    user_id=user_id or None,
                    email=email or None,
                    category=category or "general",
                    message=message,
                    page=page or None,
                )
                db.session.add(fb)
                db.session.commit()
                success = _("소중한 의견 감사합니다! 반영에 노력하겠습니다.")
                print("[feedback][success]")
                return render_template(
                    "feedback.html",
                    success=success,
                    email=default_email,
                    user_id=default_user_id,
                    category="general",
                    message="",
                    page=default_page,
                )
            except Exception as e:
                db.session.rollback()
                error = _("저장 중 오류가 발생했습니다.")
                print("[feedback][error] : " + str(e))

    return render_template(
        "feedback.html",
        error=error,
        success=success,
        email=default_email,
        user_id=default_user_id,
        category="general",
        message="",
        page=default_page,
    )