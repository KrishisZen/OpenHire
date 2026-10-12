from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from docx import Document
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture()
def app():
    application = create_app("testing")
    upload = Path(application.config["UPLOAD_FOLDER"])
    if upload.exists():
        shutil.rmtree(upload, ignore_errors=True)
    upload.mkdir(parents=True, exist_ok=True)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()
    shutil.rmtree(upload, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def signup(client, email="recruiter@example.com", password="super-secret-password", full_name="Ada Recruiter"):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "full_name": full_name},
    )


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def tokens_from(response) -> dict:
    payload = response.get_json()["data"]
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "user": payload["user"],
    }


@pytest.fixture()
def user_a(client):
    res = signup(client, "alpha@example.com", "password-alpha", "Alpha Recruiter")
    assert res.status_code == 201
    return tokens_from(res)


@pytest.fixture()
def user_b(client):
    res = signup(client, "beta@example.com", "password-beta", "Beta Recruiter")
    assert res.status_code == 201
    return tokens_from(res)


def make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def seed_user(app, email: str, password: str) -> User:
    with app.app_context():
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            full_name="Seed User",
            role="recruiter",
        )
        db.session.add(user)
        db.session.commit()
        return user
