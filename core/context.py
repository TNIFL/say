from auth.guards import resolve_tier
from flask import current_app


def init_context_processors(app):
    @app.context_processor
    def inject_ads_flags():
        tier = resolve_tier()
        cfg = current_app.config
        # 프로는 광고 OFF, 나머지는 ADS_ENABLED 따라 ON
        show_ads = cfg.get("ADS_ENABLED") and tier in {"guest", "free"}
        return {
            "ADS_ENABLED": cfg.get("ADS_ENABLED"),
            "ADS_PROVIDER": cfg.get("ADS_PROVIDER"),
            "ADSENSE_CLIENT": cfg.get("ADSENSE_CLIENT"),
            "ADFIT_UNIT_ID": cfg.get("ADFIT_UNIT_ID"),
            "NAVER_AD_UNIT": cfg.get("NAVER_AD_UNIT"),
            "SHOW_ADS": show_ads,
        }