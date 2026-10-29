"""
Configuration module for MFA Physical Token Simulator.
Loads settings from environment variables with safe defaults.
"""

import os
from pathlib import Path

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent

# Attempt to load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


class Config:
    """Base application configuration."""

    # Flask Settings
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    SECRET_KEY = os.getenv("SECRET_KEY", "mfa-token-simulator-demo-secret-key-change-in-prod")

    # OTP Core Settings
    OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "120"))
    DEMO_SHOW_OTP = os.getenv("DEMO_SHOW_OTP", "1").lower() in ("1", "true", "yes")
    RATE_LIMIT_GENERATE_SECONDS = int(os.getenv("RATE_LIMIT_GENERATE_SECONDS", "5"))
    MAX_VERIFY_ATTEMPTS = int(os.getenv("MAX_VERIFY_ATTEMPTS", "5"))

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", str(BASE_DIR / "logs" / "mfa_simulator.log"))

    # AWS CloudWatch Settings (Optional - disabled by default)
    CLOUDWATCH_ENABLED = os.getenv("CLOUDWATCH_ENABLED", "0").lower() in ("1", "true", "yes")
    CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", "/aws/flask/MFA-Token-Simulator")
    CLOUDWATCH_LOG_STREAM = os.getenv("CLOUDWATCH_LOG_STREAM", "simulator-flask-stream")
    AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2")


class TestingConfig(Config):
    """Configuration for automated test suite."""
    TESTING = True
    DEBUG = False
    OTP_TTL_SECONDS = 5  # Shorter for fast expiry tests
    RATE_LIMIT_GENERATE_SECONDS = 0  # Disable rate limit by default in tests unless testing it
    CLOUDWATCH_ENABLED = False

