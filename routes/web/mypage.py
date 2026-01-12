from flask import session, redirect, render_template, url_for, Blueprint, request, flash

from auth.guards import resolve_tier
from core.extensions import csrf
from domain.models import db, User, Usage, Subscription, Visit, Payment, Feedback
from domain.policies import LIMITS
from utils.time_utils import _month_window, _utcnow
from sqlalchemy import func
import re

mypage_bp = Blueprint("mypage", __name__)


# ===== 마이페이지(읽기 전용 개요) =====
@csrf.exempt
@mypage_bp.route("/mypage", methods=["GET"])
def mypage_overview():
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if not uid:
        return redirect(url_for("auth.login_page") + "?next=/mypage")

    user = User.query.filter_by(user_id=uid).first()
    session["user"]["display_name"] = user.display_name or (user.email.split("@", 1)[0] if user.email else None)
    if not user:
        return redirect(url_for("auth.login_page"))

    tier = resolve_tier()
    limit = LIMITS[tier]["monthly"]

    month_start, month_end = _month_window(_utcnow())

    # 전체 합계(과거 호환) — scope 합산

    used = (
            db.session.query(func.coalesce(func.sum(Usage.count), 0))
            .filter(
                Usage.user_id == uid,
                Usage.tier == tier,
                Usage.window_start >= month_start,
                Usage.window_start < month_end,
                )
            .scalar()
            or 0
    )
    remaining = max(0, (limit or 0) - int(used))

    visits = (
        Visit.query.filter(Visit.user_id == uid)
        .order_by(Visit.created_at.desc())
        .limit(5)
        .all()
    )

    active_sub = (
        Subscription.query.filter_by(user_id=uid, status="active")
        .order_by(Subscription.created_at.desc())
        .first()
    )

    payments = (
        Payment.query.filter_by(user_id=uid)
        .order_by(Payment.created_at.desc())
        .limit(5)
        .all()
    )

    my_feedbacks = (
        Feedback.query
        .filter(Feedback.user_id == user.user_id)
        .order_by(Feedback.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "mypage.html",
        user=user,
        tier=tier,
        used=int(used),
        limit=int(limit),
        remaining=int(remaining),
        visits=visits,
        active_sub=active_sub,
        payments=payments,
        my_feedbacks=my_feedbacks,
    )

@csrf.exempt
@mypage_bp.route("/mypage/input_job", methods=["POST"])
def mypage_update_job():
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if not uid:
        return redirect(url_for("auth.login_page") + "?next=/mypage")

    user = User.query.filter_by(user_id=uid).first()
    if not user:
        return redirect(url_for("auth.login_page"))

    user_job = (request.form.get("user-job") or "").strip()
    user_job_detail = (request.form.get("user-job-detail") or "").strip()

    # 선택사항이면 빈 값 허용
    if len(user_job) > 50:
        flash("직업은 50자 이내로 입력해주세요.", "error")
        return redirect(url_for("mypage.mypage_overview"))

    if len(user_job_detail) > 100:
        flash("직업 설명은 100자 이내로 입력해주세요.", "error")
        return redirect(url_for("mypage.mypage_overview"))

    print(user_job, user_job_detail)

    # 사용자가 입력한 직업과 직업 설명을 db 저장 시키기
    user.user_job = user_job or None
    user.user_job_detail = user_job_detail or None
    db.session.commit()

    session["job_saved"] = "1"
    return redirect(url_for("mypage.mypage_overview"))  # 또는 /mypage


# 직업 삭제는 따로 만들기
@csrf.exempt
@mypage_bp.route("/mypage/delete_job", methods=["POST"])
def mypage_delete_job():
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if not uid:
        return redirect(url_for("auth.login_page") + "?next=/mypage")

    user = User.query.filter_by(user_id=uid).first()
    if not user:
        return redirect(url_for("auth.login_page"))

    user.user_job = None
    user.user_job_detail = None
    db.session.commit()
    flash("직업 정보가 삭제되었습니다.", "success")
    return redirect(url_for("mypage.mypage_overview"))


def _sanitize_display_name(raw: str) -> str:
    """
    닉네임 정책(단순/안전):
    - 공백 제거
    - 이메일 앞부분 기본값에 맞춰 영문/숫자/._- 만 허용
    - 2~20자 권장 (원하면 조정)
    """
    raw = (raw or "").strip()
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "", raw)
    return raw[:20]



@mypage_bp.route("/mypage/update_nickname", methods=["POST"])
def mypage_update_nickname():
    sess = session.get("user") or {}
    uid = sess.get("user_id")
    if not uid:
        return redirect("/login")

    user = User.query.filter_by(user_id=uid).first()
    if not user:
        return redirect("/login")

    raw = (request.form.get("display_name") or "").strip()
    nickname = raw[:20]  # 길이 제한
    norm = nickname.lower()  # ✅ 비교는 소문자 기준(중복 방지 강화)

    if len(nickname) < 2:
        return redirect("/mypage?nick_error=too_short")

    # 중복 체크 (대소문자 무시)
    exists = (
        User.query
        .filter(User.display_name.isnot(None))
        .filter(func.lower(User.display_name) == norm)
        .filter(User.id != user.id)
        .first()
    )

    if exists:
        return redirect("/mypage?nick_error=taken")

    # 저장은 사용자가 입력한 형태(원문)를 그대로 저장해도 되고,
    # 정책상 통일하려면 nickname 자체를 lower()로 저장해도 됩니다.
    user.display_name = nickname
    db.session.commit()

    session["user"]["display_name"] = nickname
    return redirect("/mypage?nick_ok=1")