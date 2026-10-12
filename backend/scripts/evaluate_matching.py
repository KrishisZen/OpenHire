"""Offline ranking smoke test on synthetic labeled data. Not a hiring-validity study."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k
from app.services.information_extraction import extract_information
from app.services.matcher import embeddings_available, run_matching

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_relevance.json"
REPORT_DIR = Path(__file__).parent / "reports"


def _job_obj(spec: dict):
    return SimpleNamespace(
        description=spec["description"],
        required_skills=spec.get("required_skills") or [],
        min_experience_years=spec.get("min_experience_years"),
    )


def _resume_obj(spec: dict):
    text = spec["text"]
    return SimpleNamespace(
        id=spec["id"],
        raw_text=text,
        candidate_name=spec.get("candidate_name"),
        candidate_email=spec.get("candidate_email"),
        parsed_data=extract_information(text),
    )


def evaluate_engine(engine: str, job, resumes: list, relevant: set, graded: dict, k: int = 3) -> dict:
    ranked = run_matching(job, resumes, engine=engine)
    ranked_ids = [row["resume_id"] for row in ranked]
    return {
        "engine": engine,
        "ranked_ids": ranked_ids,
        "scores": {row["resume_id"]: row["score"] for row in ranked},
        f"precision@{k}": round(precision_at_k(ranked_ids, relevant, k), 4),
        f"recall@{k}": round(recall_at_k(ranked_ids, relevant, k), 4),
        f"ndcg@{k}": round(ndcg_at_k(ranked_ids, graded, k), 4),
        "mrr": round(mrr(ranked_ids, relevant), 4),
    }


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    print(fixture["disclaimer"])
    report = {"disclaimer": fixture["disclaimer"], "jobs": []}

    for job_spec in fixture["jobs"]:
        job = _job_obj(job_spec)
        resumes = [_resume_obj(r) for r in fixture["resumes"]]
        relevant = set(fixture["binary_relevant"][job_spec["id"]])
        graded = {k: float(v) for k, v in fixture["graded_relevance"][job_spec["id"]].items()}
        job_report = {"job_id": job_spec["id"], "engines": []}
        tfidf = evaluate_engine("tfidf", job, resumes, relevant, graded)
        job_report["engines"].append(tfidf)
        print(json.dumps(tfidf, indent=2))

        if embeddings_available():
            try:
                emb = evaluate_engine("embeddings", job, resumes, relevant, graded)
                job_report["engines"].append(emb)
                print(json.dumps(emb, indent=2))
            except Exception as exc:
                skipped = {"engine": "embeddings", "skipped": True, "reason": str(exc)}
                job_report["engines"].append(skipped)
                print(json.dumps(skipped, indent=2))
        else:
            skipped = {
                "engine": "embeddings",
                "skipped": True,
                "reason": "sentence-transformers is not installed",
            }
            job_report["engines"].append(skipped)
            print(json.dumps(skipped, indent=2))
        report["jobs"].append(job_report)

    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / "latest_evaluation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out} (gitignored). Do not copy these numbers into authored docs as proof of hiring quality.")


if __name__ == "__main__":
    main()
