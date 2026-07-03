def _auth_headers(client) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_diagnostics_config_reports_non_sensitive_runtime_settings(client) -> None:
    response = client.get("/api/diagnostics/config", headers=_auth_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["service_name"] == "edge-platform"
    assert body["api_prefix"] == "/api"
    assert body["database"].startswith("sqlite:///")
    assert body["file_backend"] == "sftp"
    assert body["remote_gateway_host"] == "127.0.0.1"
    assert body["default_device_ssh_user"] == "ztl"
    assert "password" not in body
    assert "token" not in str(body).lower()


def test_diagnostics_config_requires_authentication(client) -> None:
    response = client.get("/api/diagnostics/config")

    assert response.status_code == 403
