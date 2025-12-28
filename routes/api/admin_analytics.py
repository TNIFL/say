from flask import jsonify, request, Blueprint

from core.http_utils import nocache
from datetime import datetime, timedelta, timezone
from domain.models import Feedback, db
from domain.schema import admin_visits_query_schema, admin_data_query_schema
from routes.web.admin import admin_required
from security.security import _safe_args
from utils.time_utils import _utcnow, KST
from sqlalchemy import func, and_

api_admin_bp = Blueprint("api_admin", __name__)

# (선택) 삭제
@api_admin_bp.route("/admin/feedback/<int:fb_id>", methods=["DELETE"])
@admin_required
def admin_feedback_delete(fb_id):
    fb = Feedback.query.get(fb_id)
    if not fb:
        return jsonify({"ok": False, "error": "not_found"}), 404
    db.session.delete(fb)
    db.session.commit()
    return jsonify({"ok": True}), 200


@api_admin_bp.route("/admin/analytics/data/visits", methods=["GET"])
@admin_required
@nocache
def admin_analytics_data_visits():
    from domain.models import Visit, User

    q = _safe_args(admin_visits_query_schema)
    s_from = q.get("from")
    s_to = q.get("to")
    path = q.get("path")
    ukey = q.get("user")

    now_utc = _utcnow()
    now_kst = now_utc.astimezone(KST)

    start_kst = (now_kst - timedelta(days=29)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_kst = now_kst

    def parse_ymd_kst(s):
        try:
            y, m, d = s.split("-")
            return datetime(int(y), int(m), int(d), tzinfo=KST)
        except Exception:
            return None

    pf_kst = parse_ymd_kst(s_from) or start_kst
    pt_kst = parse_ymd_kst(s_to) or end_kst
    if pt_kst < pf_kst:
        pf_kst, pt_kst = pt_kst, pf_kst

    upper_kst = (pt_kst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    pf_utc_naive = pf_kst.astimezone(timezone.utc).replace(tzinfo=None)
    up_utc_naive = upper_kst.astimezone(timezone.utc).replace(tzinfo=None)

    v_filters = [
        Visit.created_at >= pf_utc_naive,
        Visit.created_at < up_utc_naive,
    ]
    if path:
        v_filters.append(Visit.path == path)

    if ukey:
        user_ids = {ukey}
        u = User.query.filter(User.email == ukey).first()
        if u and u.user_id:
            user_ids.add(u.user_id)
        v_filters.append(Visit.user_id.in_(list(user_ids)))


    rows = (
        db.session.query(
            func.date_trunc("day", Visit.created_at).label("d"),
            func.count(Visit.id),
        )
        .filter(and_(*v_filters))
        .group_by("d")
        .order_by("d")
        .all()
    )

    utc_map = {r[0].date(): int(r[1]) for r in rows}

    days_span = (pt_kst.date() - pf_kst.date()).days + 1
    series = []
    for i in range(days_span):
        d_kst = pf_kst + timedelta(days=i)
        d_utc = d_kst.astimezone(timezone.utc).date()
        series.append({"date": d_kst.strftime("%Y-%m-%d"), "count": utc_map.get(d_utc, 0)})

    return jsonify({"series": series}), 200


@api_admin_bp.route("/admin/analytics/data/usage", methods=["GET"])
@admin_required
@nocache
def admin_analytics_data_usage():
    from domain.models import RewriteLog
    now_kst = datetime.now(KST)
    period = request.args.get("period", "month")  # 'today', 'week', 'month'

    # --- 1. KPI 계산 (오늘, 이번 주, 이번 달) ---
    # Today
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
    today_end_utc = today_start_utc + timedelta(days=1)
    usage_today = db.session.query(func.count(RewriteLog.id)).filter(
        RewriteLog.created_at >= today_start_utc,
        RewriteLog.created_at < today_end_utc
    ).scalar() or 0

    # This Week (Mon-Sun)
    week_start_kst = today_start_kst - timedelta(days=now_kst.weekday())
    week_end_utc = (week_start_kst + timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    week_start_utc = week_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
    usage_week = db.session.query(func.count(RewriteLog.id)).filter(
        RewriteLog.created_at >= week_start_utc,
        RewriteLog.created_at < week_end_utc
    ).scalar() or 0

    # This Month
    month_start_kst = now_kst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month_val = month_start_kst.month + 1 if month_start_kst.month < 12 else 1
    next_year_val = month_start_kst.year if month_start_kst.month < 12 else month_start_kst.year + 1
    month_end_kst = month_start_kst.replace(year=next_year_val, month=next_month_val)
    month_start_utc = month_start_kst.astimezone(timezone.utc).replace(tzinfo=None)
    month_end_utc = month_end_kst.astimezone(timezone.utc).replace(tzinfo=None)
    usage_month = db.session.query(func.count(RewriteLog.id)).filter(
        RewriteLog.created_at >= month_start_utc,
        RewriteLog.created_at < month_end_utc
    ).scalar() or 0

    # --- 2. 그래프용 시계열 데이터 ---
    series = []
    if period == "today":
        # 시간별 집계
        rows = db.session.query(
            func.date_trunc('hour', RewriteLog.created_at).label('h'),
            func.count(RewriteLog.id)
        ).filter(
            RewriteLog.created_at >= today_start_utc,
            RewriteLog.created_at < today_end_utc
        ).group_by('h').all()

        hour_map = {r.h.hour: r[1] for r in rows}
        for i in range(24):
            series.append({"label": f"{i:02d}시", "count": hour_map.get(i, 0)})

    elif period == "week":
        # 주별 일자 집계
        rows = db.session.query(
            func.date_trunc('day', RewriteLog.created_at).label('d'),
            func.count(RewriteLog.id)
        ).filter(
            RewriteLog.created_at >= week_start_utc,
            RewriteLog.created_at < week_end_utc
        ).group_by('d').order_by('d').all()

        day_map = {r.d.date(): r[1] for r in rows}
        for i in range(7):
            d = week_start_utc.date() + timedelta(days=i)
            series.append({"label": d.strftime("%m-%d"), "count": day_map.get(d, 0)})

    else:  # "month" or default
        # 월별 일자 집계
        rows = db.session.query(
            func.date_trunc('day', RewriteLog.created_at).label('d'),
            func.count(RewriteLog.id)
        ).filter(
            RewriteLog.created_at >= month_start_utc,
            RewriteLog.created_at < month_end_utc
        ).group_by('d').order_by('d').all()

        day_map = {r.d.date(): r[1] for r in rows}
        num_days = (month_end_kst.date() - month_start_kst.date()).days
        for i in range(num_days):
            d = month_start_utc.date() + timedelta(days=i)
            series.append({"label": d.strftime("%m-%d"), "count": day_map.get(d, 0)})

    return jsonify({
        "kpi": {
            "today": usage_today,
            "week": usage_week,
            "month": usage_month,
        },
        "series": series
    }), 200


@api_admin_bp.route("/admin/analytics/data", methods=["GET"])
@admin_required
@nocache
def admin_analytics_data():
    from domain.models import RewriteLog, Visit, Feedback
    from sqlalchemy import and_, desc

    qsafe = _safe_args(admin_data_query_schema)
    q_date_from = qsafe.get("date_from")
    q_date_to = qsafe.get("date_to")
    q_days = int(qsafe.get("days") or 7)
    q_path = qsafe.get("path") or None
    q_user_id = qsafe.get("user_id") or None

    def parse_ymd(s):
        try:
            y, m, d = map(int, s.split("-"))
            return datetime(y, m, d, tzinfo=KST)
        except Exception:
            return None

    today_kst = (
        _utcnow()
        .astimezone(KST)
        .replace(hour=0, minute=0, second=0, microsecond=0)
    )

    date_from_kst = parse_ymd(q_date_from) or (today_kst - timedelta(days=q_days - 1))
    date_to_kst = parse_ymd(q_date_to) or today_kst
    date_to_kst_inclusive = date_to_kst + timedelta(days=1)

    date_from_utc = date_from_kst.astimezone(timezone.utc)
    date_to_utc = date_to_kst_inclusive.astimezone(timezone.utc)

    rl_filters = [RewriteLog.created_at >= date_from_utc, RewriteLog.created_at < date_to_utc]
    if q_user_id:
        rl_filters.append(RewriteLog.user_id == q_user_id)

    v_filters = [Visit.created_at >= date_from_utc, Visit.created_at < date_to_utc]
    if q_path:
        v_filters.append(Visit.path == q_path)

    total_calls = (
            db.session.query(func.count(RewriteLog.id)).filter(*rl_filters).scalar() or 0
    )
    unique_users = (
            db.session.query(func.count(func.distinct(RewriteLog.user_id)))
            .filter(*rl_filters)
            .scalar()
            or 0
    )
    total_visits = (
            db.session.query(func.count(Visit.id)).filter(*v_filters).scalar() or 0
    )

    success_calls = (
            db.session.query(func.count(RewriteLog.id))
            .filter(and_(*rl_filters, RewriteLog.output_text.isnot(None), RewriteLog.output_text != ""))
            .scalar()
            or 0
    )
    error_calls = total_calls - success_calls
    success_rate = (success_calls / total_calls * 100.0) if total_calls else 0.0
    error_rate = 100.0 - success_rate if total_calls else 0.0

    feedback_count = (
            db.session.query(func.count(Feedback.id))
            .filter(Feedback.created_at >= date_from_utc, Feedback.created_at < date_to_utc)
            .scalar()
            or 0
    )

    model_rows = (
        db.session.query(RewriteLog.model_name, func.count(RewriteLog.id))
        .filter(*rl_filters)
        .group_by(RewriteLog.model_name)
        .order_by(desc(func.count(RewriteLog.id)))
        .all()
    )
    top_model = model_rows[0][0] if model_rows else None

    today_start_kst = today_kst
    tomorrow_start_kst = today_start_kst + timedelta(days=1)
    week_start_kst = today_start_kst - timedelta(days=6)
    month_start_kst = today_start_kst.replace(day=1)

    def count_visits(kst_start, kst_end_exclusive):
        return (
                db.session.query(func.count(Visit.id))
                .filter(
                    Visit.created_at >= kst_start.astimezone(timezone.utc),
                    Visit.created_at < kst_end_exclusive.astimezone(timezone.utc),
                )
                .scalar()
                or 0
        )

    kpi_today = count_visits(today_start_kst, tomorrow_start_kst)
    kpi_this_week = count_visits(week_start_kst, tomorrow_start_kst)
    kpi_this_month = count_visits(month_start_kst, tomorrow_start_kst)

    rows = (
        db.session.query(
            func.date_trunc("day", RewriteLog.created_at).label("d"),
            func.count(RewriteLog.id),
        )
        .filter(*rl_filters)
        .group_by("d")
        .order_by("d")
        .all()
    )
    by_day_map = {r[0].astimezone(KST).date(): int(r[1]) for r in rows}
    days_span = (date_to_kst - date_from_kst).days + 1
    trends = []
    for i in range(days_span):
        d_kst = (date_from_kst + timedelta(days=i)).date()
        trends.append({"date": d_kst.strftime("%Y-%m-%d"), "count": by_day_map.get(d_kst, 0)})

    top_paths_rows = (
        db.session.query(Visit.path, func.count(Visit.id))
        .filter(*v_filters)
        .group_by(Visit.path)
        .order_by(func.count(Visit.id).desc())
        .limit(10)
        .all()
    )
    top_paths = [{"path": p, "count": int(c)} for (p, c) in (top_paths_rows or [])]

    top_users_rows = (
        db.session.query(RewriteLog.user_id, func.count(RewriteLog.id))
        .filter(*rl_filters)
        .group_by(RewriteLog.user_id)
        .order_by(func.count(RewriteLog.id).desc())
        .limit(10)
        .all()
    )
    top_users = [{"user_id": u or "(익명)", "count": int(c)} for (u, c) in (top_users_rows or [])]

    bins = [(0, 50), (51, 100), (101, 200), (201, 300), (301, 500), (501, 10_000_000)]
    bin_labels = ["0-50", "51-100", "101-200", "201-300", "301-500", "501+"]
    len_rows = db.session.query(RewriteLog.input_text).filter(*rl_filters).all()
    bucket = [0] * len(bins)
    for (txt,) in (len_rows or []):
        ln = len(txt or "")
        for idx, (a, b) in enumerate(bins):
            if a <= ln <= b:
                bucket[idx] += 1
                break
    length_dist = [{"range": label, "count": bucket[i]} for i, label in enumerate(bin_labels)]

    cat_count, tone_count = {}, {}
    ct_rows = db.session.query(RewriteLog.categories, RewriteLog.tones).filter(*rl_filters).all()
    for cats, tones in (ct_rows or []):
        if isinstance(cats, list):
            for c in cats:
                if c:
                    cat_count[c] = cat_count.get(c, 0) + 1
        if isinstance(tones, list):
            for t in tones:
                if t:
                    tone_count[t] = tone_count.get(t, 0) + 1
    top_categories = sorted(
        [{"name": k, "count": v} for k, v in cat_count.items()], key=lambda x: -x["count"]
    )[:10]
    top_tones = sorted(
        [{"name": k, "count": v} for k, v in tone_count.items()], key=lambda x: -x["count"]
    )[:10]

    all_paths_rows = (
        db.session.query(Visit.path, func.count(Visit.id))
        .filter(Visit.created_at >= date_from_utc, Visit.created_at < date_to_utc)
        .group_by(Visit.path)
        .order_by(func.count(Visit.id).desc())
        .limit(50)
        .all()
    )
    paths_all = [p for (p, _c) in (all_paths_rows or [])]

    users_sample_rows = (
        db.session.query(RewriteLog.user_id, func.count(RewriteLog.id))
        .filter(RewriteLog.created_at >= date_from_utc, RewriteLog.created_at < date_to_utc)
        .group_by(RewriteLog.user_id)
        .order_by(func.count(RewriteLog.id).desc())
        .limit(50)
        .all()
    )
    users_all = [u or "(익명)" for (u, _c) in (users_sample_rows or [])]

    return jsonify(
        {
            "today": kpi_today,
            "this_week": kpi_this_week,
            "this_month": kpi_this_month,
            "range": {
                "date_from": date_from_kst.strftime("%Y-%m-%d"),
                "date_to": date_to_kst.strftime("%Y-%m-%d"),
                "path": q_path,
                "user_id": q_user_id,
            },
            "kpis": {
                "total_calls": int(total_calls),
                "unique_users": int(unique_users),
                "total_visits": int(total_visits),
                "success_rate": round(success_rate, 2),
                "error_rate": round(error_rate, 2),
                "feedback_count": int(feedback_count),
                "top_model": top_model,
            },
            "trends": trends,
            "top_paths": top_paths,
            "top_users": top_users,
            "distros": {"length": length_dist, "categories": top_categories, "tones": top_tones},
            "filters": {"paths": paths_all, "users": users_all},
        }
    ), 200
