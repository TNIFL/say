# routes/web/subscribe.py
from flask import render_template, Blueprint, request

subscribe_bp = Blueprint("subscribe", __name__)


@subscribe_bp.route("/subscribe", methods=["GET"])
def subscribe_page():
    return render_template("subscribe.html")


@subscribe_bp.route("/subscribe/checkout", methods=["GET"])
def subscribe_checkout():
    return render_template("checkout.html")


@subscribe_bp.route("/subscribe/checkout/complete", methods=["GET"])
def subscribe_checkout_complete():
    # returnUrl이 bid를 쿼리로 넘겨준다고 가정
    bid = (request.args.get("bid") or "").strip()
    return render_template("checkout_complete.html", bid=bid)


@subscribe_bp.route("/subscribe/success", methods=["GET"])
def subscribe_success():
    # 선택: orderId 등을 쿼리로 넘기면 화면에 표시 가능
    order_id = request.args.get("orderId", "")
    return render_template("subscribe_success.html", order_id=order_id)

@subscribe_bp.route("/subscribe/fail", methods=["GET"])
def subscribe_fail():
    reason = request.args.get("reason", "unknown")
    return render_template("subscribe_fail.html", reason=reason)
