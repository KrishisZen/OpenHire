"""Shared request helpers for authenticated routes."""

from __future__ import annotations

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.auth_jwt import current_user, identity_to_user_id
from app.extensions import db
from app.models import Job, Match, Resume, User
from app.utils.errors import AppError
from app.utils.serialization import pagination_meta


def require_user() -> User:
    verify_jwt_in_request()
    user = current_user()
    if user is None:
        raise AppError("Authentication is required.", code="missing_token", status=401)
    return user


def current_user_id() -> int:
    return identity_to_user_id(get_jwt_identity())


def owned_job_or_404(user_id: int, job_id: int) -> Job:
    job = db.session.execute(
        db.select(Job).filter_by(id=job_id, user_id=user_id)
    ).scalar_one_or_none()
    if job is None:
        raise AppError("Job not found.", code="not_found", status=404)
    return job


def owned_resume_or_404(user_id: int, resume_id: int) -> Resume:
    resume = db.session.execute(
        db.select(Resume).filter_by(id=resume_id, user_id=user_id)
    ).scalar_one_or_none()
    if resume is None:
        raise AppError("Resume not found.", code="not_found", status=404)
    return resume


def owned_match_or_404(user_id: int, match_id: int) -> Match:
    match = db.session.execute(
        db.select(Match)
        .join(Job, Match.job_id == Job.id)
        .join(Resume, Match.resume_id == Resume.id)
        .filter(Match.id == match_id, Job.user_id == user_id, Resume.user_id == user_id)
    ).scalar_one_or_none()
    if match is None:
        raise AppError("Match not found.", code="not_found", status=404)
    return match


def paginate(query, page: int, per_page: int):
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    meta = pagination_meta(pagination.page, pagination.per_page, pagination.total)
    return pagination.items, meta
