from __future__ import annotations

import os
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from app.api.deps import owned_resume_or_404, paginate, require_user
from app.extensions import db
from app.models import Resume
from app.services.information_extraction import extract_information
from app.services.resume_parser import ParseError, parse_resume_file
from app.utils.errors import AppError
from app.utils.serialization import resume_public
from app.utils.validators import allowed_file_extension, parse_pagination

bp = Blueprint("resumes", __name__)


def _delete_stored_file(resume: Resume) -> None:
    if not resume.stored_filename:
        return
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, resume.stored_filename)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            current_app.logger.warning("Could not delete stored resume file %s", resume.stored_filename)


@bp.post("")
def upload_resume():
    user = require_user()
    if "file" not in request.files:
        raise AppError("A file field named 'file' is required.", code="validation_error", status=422)
    upload = request.files["file"]
    original = upload.filename or ""
    ext = allowed_file_extension(original, current_app.config["ALLOWED_EXTENSIONS"])

    candidate_name = request.form.get("candidate_name") or None
    candidate_email = request.form.get("candidate_email") or None
    if candidate_name:
        candidate_name = candidate_name.strip()[:255] or None
    if candidate_email:
        candidate_email = candidate_email.strip()[:255] or None

    stored_name = f"{uuid4().hex}.{ext}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, stored_name)
    try:
        upload.save(dest)
        raw_text = parse_resume_file(dest, ext)
        parsed = extract_information(raw_text)
        if not candidate_name:
            candidate_name = parsed.get("candidate_name_hint")
        resume = Resume(
            user_id=user.id,
            original_filename=secure_filename(original) or f"resume.{ext}",
            stored_filename=stored_name,
            file_type=ext,
            raw_text=raw_text,
            parsed_data=parsed,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            status="processed",
            is_synthetic=False,
        )
        db.session.add(resume)
        db.session.commit()
        return jsonify({"data": resume_public(resume)}), 201
    except ParseError as exc:
        if os.path.isfile(dest):
            os.remove(dest)
        raise AppError(str(exc), code=exc.code, status=422) from exc
    except AppError:
        if os.path.isfile(dest):
            os.remove(dest)
        raise
    except Exception:
        if os.path.isfile(dest):
            os.remove(dest)
        current_app.logger.exception("Resume upload failed")
        raise AppError(
            "The file could not be processed. Encrypted, scanned, or corrupt files are not supported.",
            code="unreadable_file",
            status=422,
        )


@bp.get("")
def list_resumes():
    user = require_user()
    page, per_page = parse_pagination(request.args)
    query = db.select(Resume).filter_by(user_id=user.id).order_by(Resume.uploaded_at.desc())
    items, meta = paginate(query, page, per_page)
    return jsonify({"data": [resume_public(item) for item in items], "meta": meta})


@bp.get("/<int:resume_id>")
def get_resume(resume_id: int):
    user = require_user()
    resume = owned_resume_or_404(user.id, resume_id)
    payload = resume_public(resume)
    payload["raw_text"] = resume.raw_text
    return jsonify({"data": payload})


@bp.get("/<int:resume_id>/download")
def download_resume(resume_id: int):
    user = require_user()
    resume = owned_resume_or_404(user.id, resume_id)
    if resume.is_synthetic or not resume.stored_filename:
        raise AppError(
            "This synthetic demo resume has no downloadable file.",
            code="no_download",
            status=404,
        )
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, resume.stored_filename)
    if not os.path.isfile(path):
        raise AppError("The stored file is no longer available.", code="not_found", status=404)
    return send_from_directory(
        folder,
        resume.stored_filename,
        as_attachment=True,
        download_name=resume.original_filename,
    )


@bp.delete("/<int:resume_id>")
def delete_resume(resume_id: int):
    user = require_user()
    resume = owned_resume_or_404(user.id, resume_id)
    _delete_stored_file(resume)
    db.session.delete(resume)
    db.session.commit()
    return jsonify({"data": {"deleted": True}})
