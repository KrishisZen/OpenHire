"""Flask application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_cors import CORS

from app.config import get_config
from app.extensions import db, jwt, migrate
from app.utils.errors import AppError, register_error_handlers


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    config_object = get_config(config_name)
    app.config.from_object(config_object)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    origins = app.config.get("CORS_ORIGINS") or ["http://127.0.0.1:5173"]
    CORS(
        app,
        resources={r"/api/*": {"origins": origins}},
        supports_credentials=False,
    )

    from app import models  # noqa: F401  — register models with SQLAlchemy
    from app.api import register_blueprints
    from app.auth_jwt import register_jwt_callbacks

    register_blueprints(app)
    register_jwt_callbacks(app)
    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        from app.services.information_extraction import ner_is_available
        from app.services.matcher import embeddings_available

        return jsonify(
            {
                "data": {
                    "status": "ok",
                    "engines": {
                        "tfidf": True,
                        "embeddings": embeddings_available(),
                    },
                    "ner_available": ner_is_available(),
                }
            }
        )

    @app.errorhandler(404)
    def not_found(_e):
        return (
            jsonify(
                {
                    "error": {
                        "code": "not_found",
                        "message": "The requested resource was not found.",
                        "details": {},
                    }
                }
            ),
            404,
        )

    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return err.to_response()

    return app
