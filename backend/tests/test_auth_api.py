def test_login_me_refresh_and_password_change_flow(client) -> None:
    failed_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert failed_login.status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert login.status_code == 200
    token_payload = login.json()
    assert token_payload["token_type"] == "bearer"
    assert token_payload["access_token"]
    assert token_payload["refresh_token"]

    auth_header = {"Authorization": f"Bearer {token_payload['access_token']}"}
    me = client.get("/api/auth/me", headers=auth_header)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": token_payload["refresh_token"]},
    )
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]

    wrong_change = client.put(
        "/api/auth/password",
        headers=auth_header,
        json={"old_password": "bad-old", "new_password": "new-admin-pass"},
    )
    assert wrong_change.status_code == 400

    changed = client.put(
        "/api/auth/password",
        headers=auth_header,
        json={"old_password": "admin-pass", "new_password": "new-admin-pass"},
    )
    assert changed.status_code == 204

    stale_access = client.get("/api/auth/me", headers=auth_header)
    assert stale_access.status_code == 401

    stale_refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": token_payload["refresh_token"]},
    )
    assert stale_refresh.status_code == 401

    old_password_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "new-admin-pass"},
    )
    assert new_password_login.status_code == 200


def test_protected_auth_endpoint_rejects_missing_token(client) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 403
