from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.api.deps import require_user
from app.auth_jwt import identity_to_user_id, revoke_jti
from app.extensions import db
from app.models import User
from app.utils.errors import AppError
from app.utils.serialization import user_public
from app.utils.validators import require_json, validate_email, validate_full_name, validate_password

bp = Blueprint("auth", __name__)


def _issue_tokens(user: User) -> dict:
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity=identity),
        "refresh_token": create_refresh_token(identity=identity),
        "user": user_public(user),
    }


@bp.post("/signup")
def signup():
    body = require_json(request.get_json(silent=True))
    full_name = validate_full_name(body.get("full_name"))
    email = validate_email(body.get("email", ""))
    password = validate_password(body.get("password"))

    existing = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if existing:
        raise AppError("An account with this email already exists.", code="email_taken", status=409)

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        full_name=full_name,
        role="recruiter",
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"data": _issue_tokens(user)}), 201


@bp.post("/login")
def login():
    body = require_json(request.get_json(silent=True))
    email = validate_email(body.get("email", ""))
    password = body.get("password") or ""
    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None or not check_password_hash(user.password_hash, password):
        raise AppError("Invalid email or password.", code="invalid_credentials", status=401)
    return jsonify({"data": _issue_tokens(user)})


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    jwt_data = get_jwt()
    user_id = identity_to_user_id(jwt_data["sub"])
    user = db.session.get(User, user_id)
    if user is None:
        raise AppError("Invalid email or password.", code="invalid_credentials", status=401)
    revoke_jti(jwt_data["jti"], "refresh", user.id)
    db.session.commit()
    return jsonify({"data": _issue_tokens(user)})


@bp.post("/logout")
@jwt_required()
def logout():
    access = get_jwt()
    user_id = identity_to_user_id(access["sub"])
    revoke_jti(access["jti"], access.get("type") or "access", user_id)

    body = request.get_json(silent=True) or {}
    refresh_token = body.get("refresh_token")
    refresh_error = None
    if refresh_token:
        try:
            decoded = decode_token(refresh_token)
            if decoded.get("type") != "refresh":
                refresh_error = "presented token is not a refresh token"
            elif str(decoded.get("sub")) != str(user_id):
                refresh_error = "refresh token does not belong to this user"
            else:
                revoke_jti(decoded["jti"], "refresh", user_id)
        except Exception:
            refresh_error = "refresh token was missing or invalid and was ignored"
    else:
        refresh_error = "refresh token was missing or invalid and was ignored"

    db.session.commit()
    payload = {"logged_out": True}
    if refresh_error:
        payload["refresh_token_status"] = refresh_error
    else:
        payload["refresh_token_status"] = "revoked"
    return jsonify({"data": payload})


@bp.get("/me")
def me():
    user = require_user()
    return jsonify({"data": user_public(user)})
