import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-development")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    JITSI_DOMAIN = os.getenv("JITSI_DOMAIN", "meet.jit.si")
    PAYMENT_MODE = os.getenv("PAYMENT_MODE", "sandbox")
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    SESSION_PRICE_PAISE = int(os.getenv("SESSION_PRICE_PAISE", "50000"))
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "SkillConnect <onboarding@resend.dev>")
    EMAIL_DEBUG_LOG_LINKS = os.getenv("EMAIL_DEBUG_LOG_LINKS", "").lower() in {"1", "true", "yes"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
