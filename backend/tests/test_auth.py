from tests.conftest import auth_headers, signup, tokens_from


def test_signup_login_and_me(client):
    res = signup(client)
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]
    assert data["user"]["role"] == "recruiter"
    assert data["user"]["email"] == "recruiter@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "recruiter@example.com", "password": "super-secret-password"},
    )
    assert login.status_code == 200
    tokens = tokens_from(login)
    me = client.get("/api/auth/me", headers=auth_headers(tokens))
    assert me.status_code == 200
    assert me.get_json()["data"]["email"] == "recruiter@example.com"


def test_duplicate_email(client):
    assert signup(client).status_code == 201
    again = signup(client)
    assert again.status_code == 409


def test_wrong_password(client):
    signup(client)
    res = client.post(
        "/api/auth/login",
        json={"email": "recruiter@example.com", "password": "definitely-wrong"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.get_json()["error"]["message"]


def test_short_password_rejected(client):
    res = signup(client, password="short")
    assert res.status_code == 422


def test_refresh_rotation_rejects_old_token(client):
    tokens = tokens_from(signup(client))
    first = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert first.status_code == 200
    rotated = tokens_from(first)
    reuse = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert reuse.status_code == 401
    second = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {rotated['refresh_token']}"},
    )
    assert second.status_code == 200


def test_logout_revokes_access_and_refresh(client):
    tokens = tokens_from(signup(client))
    logout = client.post(
        "/api/auth/logout",
        headers=auth_headers(tokens),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 200
    me = client.get("/api/auth/me", headers=auth_headers(tokens))
    assert me.status_code == 401
    refresh = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh.status_code == 401


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["status"] == "ok"
    assert body["engines"]["tfidf"] is True
