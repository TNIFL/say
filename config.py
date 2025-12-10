import os

class Config:
    # Flask 보안 키
    SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret")

    # ✅ PostgreSQL만 사용 (직접 설정)
    # 예시: postgresql+psycopg2://username:password@localhost:5432/dbname
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # SQLAlchemy 기본 설정
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ✅ Redis는 당장 안 쓸 때 memory:// 사용
    REDIS_URL = "memory://"

    # ✅ CORS 허용 도메인 (로컬 테스트만)
    CORS_ORIGINS = ["http://localhost:5000", "http://127.0.0.1:5000"]
    API_ALLOWED_ORIGINS = ["http://localhost:5000", "http://127.0.0.1:5000"]
