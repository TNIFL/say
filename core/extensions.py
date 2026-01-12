# extensions.py
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from domain.models import db

from authlib.integrations.flask_client import OAuth


migrate = Migrate()
csrf = CSRFProtect()

# limiter는 객체만 만들고, 실제 설정(storage/default_limits)은 app.config에서 가져오도록
limiter = Limiter(key_func=get_remote_address)

cors = CORS()
oauth = OAuth()

#TODO:: extensions.py 에는 db, migrate, csrf, limiter, cors 등 init

def init_extensions(app):
    # DB / migrate / csrf
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # migrate 초기화
    migrate.init_app(app, db)
    # csrf 초기화
    csrf.init_app(app)
    # 레이트리밋 초기화
    limiter.init_app(app)


    # 3) CORS: /api/*만 허용
    allowed_origins = (app.config.get("CORS_ORIGINS") or []) + (app.config.get("EXT_ORIGINS") or [])
    cors.init_app(
        app,
        supports_credentials=True,
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "methods": ["POST", "GET", "DELETE"],
                "allow_headers": ["Content-Type", "Authorization", "X-Lex-Client"],
            }
        },
    )




