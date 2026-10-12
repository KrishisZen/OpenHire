"""JWT blocklist and identity helpers."""

from __future__ import annotations

from flask import Flask, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.extensions import db, jwt
from app.models import TokenBlocklist, User


def identity_to_user_id(identity) -> int:
    try:
        return int(identity)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid token identity") from exc


def current_user() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = identity_to_user_id(identity)
    except ValueError:
        return None
    return db.session.get(User, user_id)


def revoke_jti(jti: str, token_type: str, user_id: int | None) -> None:
    existing = db.session.execute(
        db.select(TokenBlocklist).filter_by(jti=jti)
    ).scalar_one_or_none()
    if existing:
        return
    db.session.add(
        TokenBlocklist(jti=jti, token_type=token_type, user_id=user_id)
    )


def register_jwt_callbacks(app: Flask) -> None:
    @jwt.token_in_blocklist_loader
    def _revoked(_header, payload: dict) -> bool:
        jti = payload.get("jti")
        if not jti:
            return True
        row = db.session.execute(
            db.select(TokenBlocklist).filter_by(jti=jti)
        ).scalar_one_or_none()
        return row is not None

    @jwt.revoked_token_loader
    def _revoked_response(_header, _payload):
        return (
            jsonify(
                {
                    "error": {
                        "code": "token_revoked",
                        "message": "This token has been revoked.",
                        "details": {},
                    }
                }
            ),
            401,
        )

    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return (
            jsonify(
                {
                    "error": {
                        "code": "token_expired",
                        "message": "The token has expired.",
                        "details": {},
                    }
                }
            ),
            401,
        )

    @jwt.invalid_token_loader
    def _invalid(reason: str):
        return (
            jsonify(
                {
                    "error": {
                        "code": "invalid_token",
                        "message": "The token is invalid.",
                        "details": {},
                    }
                }
            ),
            401,
        )

    @jwt.unauthorized_loader
    def _missing(_reason: str):
        return (
            jsonify(
                {
                    "error": {
                        "code": "missing_token",
                        "message": "Authentication is required.",
                        "details": {},
                    }
                }
            ),
            401,
        )

    @jwt.needs_fresh_token_loader
    def _fresh(_header, _payload):
        return (
            jsonify(
                {
                    "error": {
                        "code": "fresh_token_required",
                        "message": "A fresh access token is required.",
                        "details": {},
                    }
                }
            ),
            401,
        )

    # Silence unused import in type checkers; get_jwt used by callers.
    _ = get_jwt
    _ = app
