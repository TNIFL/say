# routes/__init__.py
from .rewrite import bp as rewrite_bp

def register_routes(app):
    app.register_blueprint(rewrite_bp)
