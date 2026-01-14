# routes/__init__.py
from routes.web.mypage import mypage_bp
from routes.web.legal import legal_bp
from routes.web.admin import admin_bp
from routes.web.ads_txt import ads_bp
from routes.web.rewrite import mainpage_bp
from routes.web.summerize import summarize_bp
from routes.web.password_reset import password_reset_bp
from routes.web.history import history_bp
from routes.web.feedback import feedback_bp
from routes.web.subscribe import subscribe_bp
from routes.web.auth import auth_bp
from routes.web.billing import billing_bp
from routes.web.learn import learn_bp
from routes.web.sitemap import sitemap_bp
from routes.web.robots import robots_bp
from routes.web.google_auth import google_auth_bp
from routes.web.i18n import i18n_bp

from routes.api.history import api_history_bp
from routes.api.usage import api_usage_bp
from routes.api.health import api_health_bp
from routes.api.polish import api_polish_bp
from routes.api.summarize import api_summarize_bp
from routes.api.templates import api_user_templates_bp
from routes.api.auth_status import api_auth_status_bp
from routes.api.billing_nicepay import api_nicepay_subscribe_complete_bp
from routes.api.internal_cron import api_internal_cron_bp
from routes.api.admin_analytics import api_admin_bp
from routes.api.subscription import api_subscription_bp
from routes.api.nicepay_payment_method import api_nicepay_pm_bp
from routes.api.nicepay_v1 import api_nicepay_v1_bp
from routes.api.account import api_account_bp
from routes.api.extension_oauth import api_extension_oauth_bp


def register_routes(app):
    app.register_blueprint(mypage_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ads_bp)
    app.register_blueprint(mainpage_bp)
    app.register_blueprint(summarize_bp)
    app.register_blueprint(password_reset_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(subscribe_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(learn_bp)
    app.register_blueprint(sitemap_bp)
    app.register_blueprint(robots_bp)
    app.register_blueprint(google_auth_bp)
    app.register_blueprint(i18n_bp)

    app.register_blueprint(api_history_bp)
    app.register_blueprint(api_usage_bp)
    app.register_blueprint(api_health_bp)
    app.register_blueprint(api_polish_bp)
    app.register_blueprint(api_summarize_bp)
    app.register_blueprint(api_user_templates_bp)
    app.register_blueprint(api_auth_status_bp)
    app.register_blueprint(api_nicepay_subscribe_complete_bp)
    app.register_blueprint(api_internal_cron_bp)
    app.register_blueprint(api_admin_bp)
    app.register_blueprint(api_subscription_bp)
    app.register_blueprint(api_nicepay_pm_bp)
    app.register_blueprint(api_nicepay_v1_bp)
    app.register_blueprint(api_account_bp)
    app.register_blueprint(api_extension_oauth_bp)