from app.database import session_scope
from app.models.alert import Alert


def test_alerts_api_lists_summary_acknowledges_and_resolves(client, auth_headers, initialized_settings) -> None:
    with session_scope(initialized_settings) as session:
        alert = Alert(
            dedupe_key="test:1",
            alert_type="cpu_high",
            severity="critical",
            status="open",
            source_type="metric",
            source_id=1,
            device_id=None,
            title="CPU 过高",
            summary="CPU 当前 99%",
        )
        session.add(alert)
        session.flush()
        alert_id = alert.id

    list_response = client.get("/api/alerts?status=open&severity=critical", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    summary_response = client.get("/api/alerts/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    assert summary_response.json()["active_count"] == 1
    assert summary_response.json()["critical_count"] == 1

    ack = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=auth_headers, json={"note": "已知晓"})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_note"] == "已知晓"

    resolved = client.post(f"/api/alerts/{alert_id}/resolve", headers=auth_headers, json={"note": "已处理"})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    logs = client.get("/api/logs?action=alert.resolve", headers=auth_headers)
    assert logs.status_code == 200
    assert logs.json()["total"] == 1


def test_alerts_api_requires_authentication(client) -> None:
    response = client.get("/api/alerts")
    assert response.status_code == 403
