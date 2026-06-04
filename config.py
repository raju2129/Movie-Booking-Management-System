import os
from dotenv import load_dotenv

# Load .env BEFORE reading os.environ so class-level assignments pick up the values
load_dotenv(override=True)


class Config:
    SECRET_KEY                     = os.environ.get("SECRET_KEY", "bookmyshow-secret-key-2024")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO                = False

    # ── Gmail SMTP for OTP emails ──────────────────────────────────
    # These are read from .env (MAIL_USERNAME / MAIL_PASSWORD).
    # Fallback to the hardcoded values so the app works without a .env file.
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "raju2129babi@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "ssasjysulynqcekn")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:Rajukullayappa@localhost:5432/movie_booking_db0"
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:Rajukullayappa@localhost:5432/movie_booking_db0"
    )
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
