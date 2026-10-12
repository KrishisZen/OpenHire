from tests.conftest import auth_headers


def test_job_crud_and_validation(client, user_a):
    headers = auth_headers(user_a)
    created = client.post(
        "/api/jobs",
        headers=headers,
        json={
            "title": "Python Analyst",
            "description": "Need Python, SQL, Docker and pandas for data analysis.",
            "required_skills": ["Python", "Docker"],
            "min_experience_years": 2,
        },
    )
    assert created.status_code == 201
    job = created.get_json()["data"]
    assert "Python" in job["detected_skills"]
    job_id = job["id"]

    listed = client.get("/api/jobs", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["meta"]["total"] == 1

    fetched = client.get(f"/api/jobs/{job_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.get_json()["data"]["title"] == "Python Analyst"

    patched = client.patch(
        f"/api/jobs/{job_id}",
        headers=headers,
        json={"title": "Updated Analyst"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["title"] == "Updated Analyst"

    bad = client.post("/api/jobs", headers=headers, json={"title": "", "description": ""})
    assert bad.status_code == 422

    deleted = client.delete(f"/api/jobs/{job_id}", headers=headers)
    assert deleted.status_code == 200
    missing = client.get(f"/api/jobs/{job_id}", headers=headers)
    assert missing.status_code == 404
