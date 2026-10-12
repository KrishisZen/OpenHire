"""Public JSON shapes for API responses. Never include hashes, JTIs, or absolute paths."""

from __future__ import annotations

from datetime import datetime


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def user_public(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": iso(user.created_at),
    }


def job_public(job, *, detected_skills: list | None = None) -> dict:
    payload = {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills or [],
        "min_experience_years": job.min_experience_years,
        "created_at": iso(job.created_at),
        "updated_at": iso(job.updated_at),
    }
    if detected_skills is not None:
        payload["detected_skills"] = detected_skills
    return payload


def resume_public(resume) -> dict:
    return {
        "id": resume.id,
        "original_filename": resume.original_filename,
        "file_type": resume.file_type,
        "candidate_name": resume.candidate_name,
        "candidate_email": resume.candidate_email,
        "status": resume.status,
        "processing_error": resume.processing_error,
        "parsed_data": resume.parsed_data or {},
        "is_synthetic": bool(resume.is_synthetic),
        "has_downloadable_file": bool(resume.stored_filename) and not resume.is_synthetic,
        "uploaded_at": iso(resume.uploaded_at),
    }


def match_summary(match, resume=None) -> dict:
    explanation = match.match_explanation or {}
    gaps = match.skill_gaps or {}
    resume = resume or match.resume
    return {
        "id": match.id,
        "resume_id": match.resume_id,
        "job_id": match.job_id,
        "score": match.score,
        "scoring_method": match.scoring_method,
        "candidate_name": resume.candidate_name if resume else None,
        "original_filename": resume.original_filename if resume else None,
        "is_synthetic": bool(resume.is_synthetic) if resume else False,
        "matched_skills": explanation.get("matched_skills") or gaps.get("matched_skills") or [],
        "missing_skills": explanation.get("missing_skills") or gaps.get("missing_skills") or [],
        "experience_assessment": explanation.get("experience_assessment"),
        "computed_at": iso(match.computed_at),
    }


def match_detail(match, resume=None, job=None) -> dict:
    payload = match_summary(match, resume=resume)
    payload["match_explanation"] = match.match_explanation or {}
    payload["skill_gaps"] = match.skill_gaps or {}
    if job is not None:
        payload["job_title"] = job.title
    return payload


def pagination_meta(page: int, per_page: int, total: int) -> dict:
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {"page": page, "per_page": per_page, "total": total, "pages": pages}
