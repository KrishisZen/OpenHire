"""Idempotent fictional demo data. Does not write resume files.

Read DEMO_EMAIL / DEMO_PASSWORD / DEMO_NAME from the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv(BACKEND_DIR / ".env")

from app import create_app
from app.extensions import db
from app.models import Job, Resume, User
from app.services.information_extraction import extract_information

DEMO_JOBS = [
    {
        "title": "Junior Python Data Analyst (synthetic job)",
        "description": (
            "Fictional role for local demos. We need Python, pandas, SQL, Excel, and basic statistics. "
            "Data analysis of tabular datasets. Flask is useful. Docker is required for packaging local demos. "
            "This posting is synthetic and must not be used as a real job advertisement."
        ),
        "required_skills": ["Python", "SQL", "pandas", "Docker"],
        "min_experience_years": 1,
    },
    {
        "title": "Frontend Intern — React (synthetic job)",
        "description": (
            "Fictional internship. Looking for JavaScript, TypeScript, React, HTML/CSS, Git, and REST APIs. "
            "Flask knowledge is optional. Synthetic posting only."
        ),
        "required_skills": ["React", "JavaScript", "HTML/CSS", "Git"],
        "min_experience_years": 0,
    },
]

DEMO_RESUMES = [
    {
        "original_filename": "priya_nair_synthetic.txt",
        "candidate_name": "Priya Nair (synthetic)",
        "candidate_email": "priya.nair.synthetic@example.com",
        "text": (
            "Priya Nair (synthetic). Email: priya.nair.synthetic@example.com\n"
            "BCA, fictional university. 2 years of experience in data analysis.\n"
            "Built data processing scripts in Python and pandas, wrote SQL against PostgreSQL, "
            "created Excel dashboards, and containerized a Flask demo with Docker. Statistics coursework."
        ),
    },
    {
        "original_filename": "omar_hassan_synthetic.txt",
        "candidate_name": "Omar Hassan (synthetic)",
        "candidate_email": "omar.hassan.synthetic@example.com",
        "text": (
            "Omar Hassan (synthetic). B.Sc. (fictional).\n"
            "Frontend-focused: React, JavaScript, HTML/CSS, Git, REST APIs. Built marketing landing pages. "
            "Mentions Excel for reporting. No Python projects."
        ),
    },
    {
        "original_filename": "mei_chen_synthetic.txt",
        "candidate_name": "Mei Chen (synthetic)",
        "candidate_email": "mei.chen.synthetic@example.com",
        "text": (
            "Mei Chen (synthetic). MCA (fictional). 1 year of experience in machine learning.\n"
            "Python, scikit-learn, NumPy, pandas, SQL, Git, Linux. Course projects in NLP. "
            "Has not used Docker in production."
        ),
    },
]


def seed() -> None:
    email = os.environ.get("DEMO_EMAIL", "demo.recruiter@example.com").strip().lower()
    password = os.environ.get("DEMO_PASSWORD", "demo-password-change-me")
    name = os.environ.get("DEMO_NAME", "Demo Recruiter")
    if len(password) < 10:
        raise SystemExit("DEMO_PASSWORD must be at least 10 characters.")

    app = create_app()
    with app.app_context():
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                full_name=name,
                role="recruiter",
            )
            db.session.add(user)
            db.session.flush()
            print(f"Created demo user {email}")
        else:
            print(f"Demo user already exists: {email}")

        for spec in DEMO_JOBS:
            existing = db.session.execute(
                db.select(Job).filter_by(user_id=user.id, title=spec["title"])
            ).scalar_one_or_none()
            if existing:
                continue
            db.session.add(Job(user_id=user.id, **spec))
            print(f"Created job: {spec['title']}")

        for spec in DEMO_RESUMES:
            existing = db.session.execute(
                db.select(Resume).filter_by(
                    user_id=user.id, original_filename=spec["original_filename"]
                )
            ).scalar_one_or_none()
            if existing:
                continue
            parsed = extract_information(spec["text"])
            db.session.add(
                Resume(
                    user_id=user.id,
                    original_filename=spec["original_filename"],
                    stored_filename=None,
                    file_type="synthetic",
                    raw_text=spec["text"],
                    parsed_data=parsed,
                    candidate_name=spec["candidate_name"],
                    candidate_email=spec["candidate_email"],
                    status="processed",
                    is_synthetic=True,
                )
            )
            print(f"Created synthetic resume: {spec['candidate_name']}")

        db.session.commit()
        print("Seed complete. All names and emails are fictional.")


if __name__ == "__main__":
    seed()
