"""Application configuration. Values come from environment variables / .env."""
import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def build_database_uri() -> str:
    """Build the SQLAlchemy URI. DATABASE_URL wins; otherwise XAMPP/MySQL defaults."""
    url = os.getenv("DATABASE_URL")
    if url:
        # Make sqlite relative paths absolute against the project root
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            rel = url[len("sqlite:///"):]
            if not os.path.isabs(rel):
                url = "sqlite:///" + os.path.join(BASE_DIR, rel)
        return url
    user = os.getenv("DB_USER", "root")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))  # XAMPP root has no password by default
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "spam_detection_db")
    auth = f"{user}:{password}" if password else user
    return f"mysql+pymysql://{auth}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-please")
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    MAX_MESSAGE_LENGTH = 5000
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB (CSV uploads)
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 300

    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@spamguard.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"  # in-memory
    SQLALCHEMY_ENGINE_OPTIONS = {}
