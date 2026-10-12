from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        code: str = "bad_request",
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details or {}

    def to_response(self):
        return (
            jsonify(
                {
                    "error": {
                        "code": self.code,
                        "message": self.message,
                        "details": self.details,
                    }
                }
            ),
            self.status,
        )


def error_payload(code: str, message: str, details: dict | None = None):
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_e):
        return jsonify(error_payload("file_too_large", "The uploaded file exceeds the size limit.")), 413

    @app.errorhandler(HTTPException)
    def http_error(err: HTTPException):
        if err.code == 404:
            return jsonify(error_payload("not_found", "The requested resource was not found.")), 404
        return (
            jsonify(error_payload("http_error", err.description or "Request failed.")),
            err.code or 500,
        )

    @app.errorhandler(Exception)
    def unexpected(err: Exception):
        app.logger.exception("Unhandled error")
        if app.config.get("TESTING"):
            raise err
        return (
            jsonify(
                error_payload(
                    "internal_error",
                    "An unexpected error occurred. No sensitive details are returned.",
                )
            ),
            500,
        )
