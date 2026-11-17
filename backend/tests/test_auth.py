U = {"email": "Test@Example.com", "password": "StrongPass123", "full_name": "Test User"}


def register(client, **over):
    return client.post("/api/auth/register", json={**U, **over})


def login(client, password="StrongPass123"):
    return client.post("/api/auth/login", json={"email": U["email"], "password": password})


def test_register_ok_and_no_password_leak(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "test@example.com"
    assert "password" not in str(body).lower()


def test_duplicate_email_rejected(client):
    register(client)
    assert register(client, email="test@example.com").status_code == 409


def test_weak_password_rejected(client):
    assert register(client, password="short").status_code == 422


def test_login_success_and_me(client):
    register(client)
    token = login(client).json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_login_wrong_password(client):
    register(client)
    assert login(client, "WrongPass999").status_code == 401


def test_login_unknown_user(client):
    assert login(client).status_code == 401


def test_protected_rejects_unauthenticated(client):
    assert client.get("/api/auth/me").status_code == 401


def test_protected_rejects_bad_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401
