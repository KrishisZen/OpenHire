"""Environment-based Flask configuration."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _sqlite_uri(relative_or_absolute: str, instance_path: Path) -> str:
    path = Path(relative_or_absolute)
    if not path.is_absolute():
        # sqlite:///instance/app.db -> backend/instance/app.db
        if str(path).replace("\\", "/").startswith("instance/"):
            path = BACKEND_DIR / path
        else:
            path = instance_path / path
    return "sqlite:///" + path.resolve().as_posix()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-jwt-change-me")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=_int_env("ACCESS_TOKEN_MINUTES", 15)
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=_int_env("REFRESH_TOKEN_DAYS", 7))
    JWT_ERROR_MESSAGE_KEY = "msg"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    MAX_CONTENT_LENGTH = _int_env("MAX_UPLOAD_MB", 10) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "docx"}
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]
    EMBEDDING_SKILL_THRESHOLD = float(
        os.environ.get("EMBEDDING_SKILL_THRESHOLD", "0.55")
    )
    JSON_SORT_KEYS = False

    def __init__(self) -> None:
        instance_path = BACKEND_DIR / "instance"
        instance_path.mkdir(parents=True, exist_ok=True)
        database_url = os.environ.get("DATABASE_URL", "sqlite:///instance/app.db")
        if database_url.startswith("sqlite:///"):
            rest = database_url.replace("sqlite:///", "", 1)
            self.SQLALCHEMY_DATABASE_URI = _sqlite_uri(rest, instance_path)
        else:
            self.SQLALCHEMY_DATABASE_URI = database_url

        upload = os.environ.get("UPLOAD_FOLDER")
        if upload:
            self.UPLOAD_FOLDER = str(Path(upload).resolve())
        else:
            self.UPLOAD_FOLDER = str((instance_path / "uploads").resolve())


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    WTF_CSRF_ENABLED = False

    def __init__(self) -> None:
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        self.UPLOAD_FOLDER = str((BACKEND_DIR / "instance" / "test-uploads").resolve())


class ProductionConfig(BaseConfig):
    DEBUG = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> BaseConfig:
    env_name = name or os.environ.get("FLASK_ENV", "development")
    if env_name == "development" or env_name == "dev":
        key = "development"
    elif env_name in ("testing", "test"):
        key = "testing"
    elif env_name == "production":
        key = "production"
    else:
        key = "development"
    return _CONFIGS[key]()
