from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.deps import owned_job_or_404, paginate, require_user
from app.extensions import db
from app.models import Job
from app.services.information_extraction import extract_skills
from app.utils.errors import AppError
from app.utils.serialization import job_public
from app.utils.validators import (
    parse_pagination,
    require_json,
    validate_min_experience,
    validate_skills,
)

bp = Blueprint("jobs", __name__)


def _job_fields(body: dict, *, partial: bool) -> dict:
    fields: dict = {}
    if "title" in body or not partial:
        title = (body.get("title") or "").strip() if isinstance(body.get("title"), str) else ""
        if not title:
            raise AppError("title is required.", code="validation_error", status=422)
        if len(title) > 255:
            raise AppError("title is too long.", code="validation_error", status=422)
        fields["title"] = title
    if "description" in body or not partial:
        description = body.get("description")
        if not isinstance(description, str) or not description.strip():
            raise AppError("description is required.", code="validation_error", status=422)
        fields["description"] = description.strip()
    if "required_skills" in body or not partial:
        fields["required_skills"] = validate_skills(body.get("required_skills"))
    if "min_experience_years" in body or not partial:
        fields["min_experience_years"] = validate_min_experience(body.get("min_experience_years"))
    return fields


def _with_detected(job: Job) -> dict:
    detected = [item["name"] for item in extract_skills(job.description)]
    return job_public(job, detected_skills=detected)


@bp.get("")
def list_jobs():
    user = require_user()
    page, per_page = parse_pagination(request.args)
    query = db.select(Job).filter_by(user_id=user.id).order_by(Job.created_at.desc())
    items, meta = paginate(query, page, per_page)
    return jsonify({"data": [_with_detected(job) for job in items], "meta": meta})


@bp.post("")
def create_job():
    user = require_user()
    body = require_json(request.get_json(silent=True))
    fields = _job_fields(body, partial=False)
    job = Job(user_id=user.id, **fields)
    db.session.add(job)
    db.session.commit()
    return jsonify({"data": _with_detected(job)}), 201


@bp.get("/<int:job_id>")
def get_job(job_id: int):
    user = require_user()
    job = owned_job_or_404(user.id, job_id)
    return jsonify({"data": _with_detected(job)})


@bp.patch("/<int:job_id>")
@bp.put("/<int:job_id>")
def update_job(job_id: int):
    user = require_user()
    job = owned_job_or_404(user.id, job_id)
    body = require_json(request.get_json(silent=True))
    fields = _job_fields(body, partial=request.method == "PATCH")
    for key, value in fields.items():
        setattr(job, key, value)
    db.session.commit()
    return jsonify({"data": _with_detected(job)})


@bp.delete("/<int:job_id>")
def delete_job(job_id: int):
    user = require_user()
    job = owned_job_or_404(user.id, job_id)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"data": {"deleted": True}})
