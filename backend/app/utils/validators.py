from __future__ import annotations

import re
from typing import Any

from app.utils.errors import AppError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_json(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise AppError("JSON object body is required.", code="validation_error", status=400)
    return payload


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    value = normalize_email(email)
    if not value or not EMAIL_RE.match(value):
        raise AppError("A valid email address is required.", code="validation_error", status=422)
    return value


def validate_password(password: Any) -> str:
    if not isinstance(password, str) or len(password) < 10:
        raise AppError(
            "Password must be at least 10 characters.",
            code="validation_error",
            status=422,
        )
    return password


def validate_full_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise AppError("Full name is required.", code="validation_error", status=422)
    value = name.strip()
    if len(value) > 255:
        raise AppError("Full name is too long.", code="validation_error", status=422)
    return value


def parse_pagination(args) -> tuple[int, int]:
    try:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 20))
    except (TypeError, ValueError):
        raise AppError("page and per_page must be integers.", code="validation_error", status=422)
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > 50:
        per_page = 50
    return page, per_page


def validate_skills(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if not isinstance(value, list):
        raise AppError(
            "required_skills must be a list of strings.",
            code="validation_error",
            status=422,
        )
    skills = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AppError(
                "Each required skill must be a non-empty string.",
                code="validation_error",
                status=422,
            )
        skills.append(item.strip())
    return skills


def validate_min_experience(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        years = float(value)
    except (TypeError, ValueError):
        raise AppError(
            "min_experience_years must be a non-negative number.",
            code="validation_error",
            status=422,
        )
    if years < 0:
        raise AppError(
            "min_experience_years must be a non-negative number.",
            code="validation_error",
            status=422,
        )
    return years


def allowed_file_extension(filename: str, allowed: set[str]) -> str:
    if not filename or "." not in filename:
        raise AppError("A file with a .pdf or .docx extension is required.", code="validation_error", status=422)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed:
        raise AppError(
            "Only PDF and DOCX files are supported.",
            code="unsupported_file_type",
            status=422,
            details={"extension": ext},
        )
    return ext
