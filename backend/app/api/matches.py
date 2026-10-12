from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.deps import owned_job_or_404, owned_match_or_404, paginate, require_user
from app.extensions import db
from app.models import Match, Resume
from app.services.matcher import run_matching
from app.utils.errors import AppError
from app.utils.serialization import match_detail, match_summary
from app.utils.validators import parse_pagination, require_json

bp = Blueprint("matches", __name__)


@bp.post("/jobs/<int:job_id>/match")
def run_match(job_id: int):
    user = require_user()
    job = owned_job_or_404(user.id, job_id)
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    else:
        body = require_json(body)

    engine = (body.get("engine") or "tfidf").strip().lower()
    if engine not in {"tfidf", "embeddings"}:
        raise AppError("engine must be 'tfidf' or 'embeddings'.", code="validation_error", status=422)

    resume_ids = body.get("resume_ids")
    query = db.select(Resume).filter_by(user_id=user.id, status="processed")
    if resume_ids is not None:
        if not isinstance(resume_ids, list) or not all(isinstance(i, int) for i in resume_ids):
            raise AppError("resume_ids must be a list of integers.", code="validation_error", status=422)
        query = query.filter(Resume.id.in_(resume_ids))

    resumes = list(db.session.execute(query).scalars())
    if resume_ids is not None:
        found = {r.id for r in resumes}
        missing = [i for i in resume_ids if i not in found]
        if missing:
            raise AppError("One or more resumes were not found.", code="not_found", status=404)

    usable = [r for r in resumes if (r.raw_text or "").strip()]
    if not usable:
        raise AppError(
            "No processed resumes are available to match. Upload a resume first.",
            code="no_resumes",
            status=422,
        )

    results = run_matching(job, usable, engine=engine)
    persisted = []
    for item in results:
        row = db.session.execute(
            db.select(Match).filter_by(resume_id=item["resume_id"], job_id=job.id)
        ).scalar_one_or_none()
        if row is None:
            row = Match(resume_id=item["resume_id"], job_id=job.id)
            db.session.add(row)
        row.score = item["score"]
        row.scoring_method = item["scoring_method"]
        row.skill_gaps = item["skill_gaps"]
        row.match_explanation = item["match_explanation"]
        from app.models import utcnow

        row.computed_at = utcnow()
        persisted.append(row)

    db.session.commit()
    persisted.sort(key=lambda m: m.score, reverse=True)
    resume_map = {r.id: r for r in usable}
    return jsonify(
        {
            "data": [match_summary(row, resume=resume_map.get(row.resume_id)) for row in persisted],
            "meta": {"engine": engine, "count": len(persisted)},
        }
    )


@bp.get("/jobs/<int:job_id>/matches")
def list_matches(job_id: int):
    user = require_user()
    job = owned_job_or_404(user.id, job_id)
    page, per_page = parse_pagination(request.args)
    query = (
        db.select(Match)
        .filter_by(job_id=job.id)
        .order_by(Match.score.desc(), Match.id.asc())
    )
    items, meta = paginate(query, page, per_page)
    return jsonify(
        {
            "data": [match_summary(item, resume=item.resume) for item in items],
            "meta": meta,
        }
    )


@bp.get("/matches/<int:match_id>")
def get_match(match_id: int):
    user = require_user()
    match = owned_match_or_404(user.id, match_id)
    return jsonify({"data": match_detail(match, resume=match.resume, job=match.job)})
