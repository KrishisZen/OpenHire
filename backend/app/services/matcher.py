"""Explainable matching engines: TF-IDF (default) and optional embeddings."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.information_extraction import canonical_skill_names, extract_skills
from app.utils.errors import AppError

SCORE_MEANING_TFIDF = (
    "Cosine text similarity on a 0–100 scale; not a probability of job success."
)
SCORE_MEANING_EMBEDDINGS = (
    "Embedding cosine similarity mapped with score = clamp(cosine * 100, 0, 100). "
    "This is a simple linear mapping, not a calibrated hiring probability."
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_embedding_model = None
_embedding_error: str | None = None


def embeddings_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return False
    return True


def clamp_score(cosine: float) -> float:
    return round(max(0.0, min(100.0, cosine * 100.0)), 2)


def text_for_matching(raw_text: str, candidate_name: str | None, candidate_email: str | None) -> str:
    """Strip emails and the candidate name so they cannot influence the score."""
    text = raw_text or ""
    text = EMAIL_RE.sub(" ", text)
    if candidate_email:
        text = re.sub(re.escape(candidate_email), " ", text, flags=re.I)
    if candidate_name:
        text = re.sub(re.escape(candidate_name), " ", text, flags=re.I)
    return text


def assess_experience(
    candidate_years: float | None,
    job_min: float | None,
    evidence: str | None,
) -> dict:
    if job_min is None:
        status = "unknown"
    elif candidate_years is None:
        status = "unknown"
    elif candidate_years + 1e-9 >= job_min:
        status = "meets"
    else:
        status = "below"
    return {
        "candidate_stated_years": candidate_years,
        "job_min_years": job_min,
        "status": status,
        "evidence": evidence,
        "note": "Heuristic from explicit numeric phrases only; it does not change the similarity score.",
    }


def job_skill_catalog(job) -> list[dict]:
    required = canonical_skill_names(list(job.required_skills or []))
    detected = [s["name"] for s in extract_skills(job.description or "")]
    detected = canonical_skill_names(detected)
    catalog = []
    seen = set()
    for name in required:
        catalog.append({"skill": name, "importance": "required"})
        seen.add(name.lower())
    for name in detected:
        if name.lower() not in seen:
            catalog.append({"skill": name, "importance": "detected"})
            seen.add(name.lower())
    return catalog


def _resume_skill_map(resume) -> dict[str, str]:
    parsed = resume.parsed_data or {}
    mapping = {}
    for item in parsed.get("skills") or []:
        name = item.get("name")
        if name:
            mapping[name.lower()] = item.get("evidence") or ""
    return mapping


def _job_skill_evidence(job_text: str, skill: str) -> str:
    hits = extract_skills(job_text)
    for item in hits:
        if item["name"].lower() == skill.lower():
            return item.get("evidence") or ""
    return ""


def build_skill_gaps(
    job,
    resume,
    job_term_weights: dict[str, float] | None = None,
) -> tuple[list[dict], list[dict]]:
    catalog = job_skill_catalog(job)
    resume_map = _resume_skill_map(resume)
    resume_keys = set(resume_map)
    matched = []
    missing = []
    for item in catalog:
        skill = item["skill"]
        key = skill.lower()
        if key in resume_keys:
            matched.append(
                {
                    "skill": skill,
                    "importance": item["importance"],
                    "evidence": resume_map.get(key, ""),
                }
            )
        else:
            missing.append(
                {
                    "skill": skill,
                    "importance": item["importance"],
                    "job_evidence": _job_skill_evidence(job.description or "", skill),
                    "weight": (job_term_weights or {}).get(key, 0.0),
                }
            )
    missing.sort(key=lambda row: (0 if row["importance"] == "required" else 1, -row["weight"], row["skill"]))
    for row in missing:
        row.pop("weight", None)
    return matched, missing


def term_contributions(job_vec, resume_vec, feature_names: np.ndarray, top_n: int = 12) -> tuple[float, list[dict]]:
    product = job_vec.multiply(resume_vec)
    cosine = float(product.sum())
    dense = product.toarray().ravel()
    if dense.size == 0:
        return cosine, []
    order = np.argsort(dense)[::-1]
    rows = []
    for idx in order:
        value = float(dense[idx])
        if value <= 0:
            break
        share = (value / cosine * 100.0) if cosine > 1e-12 else 0.0
        rows.append(
            {
                "term": str(feature_names[idx]),
                "contribution": round(value, 6),
                "share_percent": round(share, 2),
            }
        )
        if len(rows) >= top_n:
            break
    return cosine, rows


def job_term_weights_from_vector(job_vec, feature_names: np.ndarray) -> dict[str, float]:
    dense = job_vec.toarray().ravel()
    weights = {}
    for i, name in enumerate(feature_names):
        if dense[i] > 0:
            weights[str(name).lower()] = float(dense[i])
    return weights


def compute_tfidf_matches(job_text: str, resume_payloads: list[dict]) -> list[dict]:
    corpus = [job_text] + [item["text"] for item in resume_payloads]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        stop_words=None,
        token_pattern=r"(?u)\b[\w+#][\w+#.+-]*\b",
        min_df=1,
        norm="l2",
    )
    matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()
    job_vec = matrix[0]
    job_weights = job_term_weights_from_vector(job_vec, feature_names)
    results = []
    for i, payload in enumerate(resume_payloads):
        resume_vec = matrix[i + 1]
        cosine, terms = term_contributions(job_vec, resume_vec, feature_names)
        results.append(
            {
                "resume_id": payload["resume"].id,
                "cosine": cosine,
                "score": clamp_score(cosine),
                "top_contributing_terms": terms,
                "job_term_weights": job_weights,
            }
        )
    return results


def _load_embedding_model():
    global _embedding_model, _embedding_error
    if _embedding_model is not None:
        return _embedding_model
    if _embedding_error:
        raise AppError(_embedding_error, code="embeddings_unavailable", status=503)
    try:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
        )
        return _embedding_model
    except Exception as exc:
        _embedding_error = (
            "The embeddings engine is unavailable. Install backend/requirements-ml.txt "
            "and allow the MiniLM model to download once, or use TF-IDF. "
            f"({type(exc).__name__})"
        )
        raise AppError(_embedding_error, code="embeddings_unavailable", status=503) from exc


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_embedding_matches(job, resumes: list, threshold: float) -> list[dict]:
    model = _load_embedding_model()
    job_text = job.description or ""
    texts = [job_text] + [
        text_for_matching(r.raw_text, r.candidate_name, r.candidate_email) for r in resumes
    ]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    job_emb = embeddings[0]
    catalog = job_skill_catalog(job)
    job_skill_names = [c["skill"] for c in catalog]
    results = []
    for i, resume in enumerate(resumes):
        cosine = _cosine(job_emb, embeddings[i + 1])
        resume_skills = [s["name"] for s in (resume.parsed_data or {}).get("skills") or []]
        pairs = []
        if job_skill_names:
            skill_texts = job_skill_names + (resume_skills or ["(no extracted skills)"])
            skill_emb = model.encode(skill_texts, convert_to_numpy=True, show_progress_bar=False)
            job_skill_emb = skill_emb[: len(job_skill_names)]
            resume_skill_emb = skill_emb[len(job_skill_names) :]
            resume_map = _resume_skill_map(resume)
            matched = []
            missing = []
            for j, job_skill in enumerate(job_skill_names):
                best_name = None
                best_sim = -1.0
                for k, cand in enumerate(resume_skills):
                    sim = _cosine(job_skill_emb[j], resume_skill_emb[k])
                    if sim > best_sim:
                        best_sim = sim
                        best_name = cand
                is_match = best_name is not None and best_sim >= threshold
                importance = catalog[j]["importance"]
                pairs.append(
                    {
                        "job_skill": job_skill,
                        "resume_skill": best_name if is_match else None,
                        "similarity": round(max(best_sim, 0.0), 4) if best_name else None,
                        "matched": is_match,
                        "threshold": threshold,
                        "importance": importance,
                    }
                )
                if is_match:
                    matched.append(
                        {
                            "skill": job_skill,
                            "importance": importance,
                            "evidence": resume_map.get(best_name.lower() if best_name else "", ""),
                            "semantic_match": best_name,
                            "similarity": round(best_sim, 4),
                        }
                    )
                else:
                    missing.append(
                        {
                            "skill": job_skill,
                            "importance": importance,
                            "job_evidence": _job_skill_evidence(job_text, job_skill),
                        }
                    )
            missing.sort(key=lambda row: 0 if row["importance"] == "required" else 1)
        else:
            matched, missing = [], []
        parsed = resume.parsed_data or {}
        experience = assess_experience(
            parsed.get("stated_experience_years"),
            job.min_experience_years,
            parsed.get("experience_evidence"),
        )
        explanation = {
            "engine": "embeddings",
            "score_meaning": SCORE_MEANING_EMBEDDINGS,
            "top_contributing_terms": [],
            "skill_similarity_pairs": pairs,
            "matched_skills": matched,
            "missing_skills": missing,
            "experience_assessment": experience,
        }
        results.append(
            {
                "resume_id": resume.id,
                "score": clamp_score(cosine),
                "scoring_method": "embeddings",
                "skill_gaps": {"matched_skills": matched, "missing_skills": missing},
                "match_explanation": explanation,
            }
        )
    results.sort(key=lambda row: row["score"], reverse=True)
    return results


def run_matching(job, resumes: list, engine: str = "tfidf", embedding_threshold: float | None = None) -> list[dict]:
    if engine == "embeddings":
        if not embeddings_available():
            raise AppError(
                "The embeddings engine is not installed. Use TF-IDF, or install backend/requirements-ml.txt.",
                code="embeddings_unavailable",
                status=503,
            )
        from flask import current_app

        threshold = embedding_threshold
        if threshold is None:
            try:
                threshold = float(current_app.config.get("EMBEDDING_SKILL_THRESHOLD", 0.55))
            except Exception:
                threshold = 0.55
        return compute_embedding_matches(job, resumes, threshold)

    if engine != "tfidf":
        raise AppError("engine must be 'tfidf' or 'embeddings'.", code="validation_error", status=422)

    payloads = [
        {
            "resume": resume,
            "text": text_for_matching(resume.raw_text, resume.candidate_name, resume.candidate_email),
        }
        for resume in resumes
    ]
    tfidf_rows = compute_tfidf_matches(job.description or "", payloads)
    out = []
    for row, payload in zip(tfidf_rows, payloads, strict=True):
        resume = payload["resume"]
        matched, missing = build_skill_gaps(job, resume, row["job_term_weights"])
        parsed = resume.parsed_data or {}
        experience = assess_experience(
            parsed.get("stated_experience_years"),
            job.min_experience_years,
            parsed.get("experience_evidence"),
        )
        explanation = {
            "engine": "tfidf",
            "score_meaning": SCORE_MEANING_TFIDF,
            "top_contributing_terms": row["top_contributing_terms"],
            "matched_skills": matched,
            "missing_skills": missing,
            "experience_assessment": experience,
        }
        out.append(
            {
                "resume_id": resume.id,
                "score": row["score"],
                "scoring_method": "tfidf",
                "skill_gaps": {"matched_skills": matched, "missing_skills": missing},
                "match_explanation": explanation,
            }
        )
    out.sort(key=lambda item: item["score"], reverse=True)
    return out


def tfidf_contribution_invariant(job_text: str, resume_text: str, atol: float = 1e-6) -> tuple[float, float]:
    """Return (cosine_from_sklearn, contribution_sum) for tests."""
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        stop_words=None,
        token_pattern=r"(?u)\b[\w+#][\w+#.+-]*\b",
        min_df=1,
        norm="l2",
    )
    matrix = vectorizer.fit_transform([job_text, resume_text])
    cosine = float(cosine_similarity(matrix[0], matrix[1])[0, 0])
    contrib_sum = float(matrix[0].multiply(matrix[1]).sum())
    assert math.isclose(cosine, contrib_sum, abs_tol=atol)
    return cosine, contrib_sum


# Silence unused Any import if type checkers complain in older setups.
_ = Any
