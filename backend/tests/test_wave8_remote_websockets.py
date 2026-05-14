from starlette.websockets import WebSocketDisconnect


def _auth(client) -> tuple[dict[str, str], str]:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def _create_device(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/devices",
        headers=headers,
        json={
            "name": "Wave8 remote device",
            "device_sn": "wave8-remote-001",
            "project_id": "factory-wave8",
            "ssh_user": "root",
        },
    )
    assert response.status_code == 201
    return response.json()


class FakeShell:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.output = [b"shell-ready\n"]
        self.closed = False

    def recv(self, size: int = 4096, timeout: float = 0.2) -> bytes:
        if self.output:
            return self.output.pop(0)
        return b""

    def send(self, data: str) -> None:
        self.sent.append(data)
        self.output.append(f"echo:{data}".encode("utf-8"))

    def resize(self, columns: int, rows: int) -> None:
        self.sent.append(f"resize:{columns}x{rows}")

    def close(self) -> None:
        self.closed = True


class FakeSshService:
    def __init__(self) -> None:
        self.shell = FakeShell()

    def open_shell(self, device):
        return self.shell


class FakeVncRelayService:
    async def relay(self, websocket, device) -> None:
        await websocket.send_bytes(b"RFB 003.008\n")
        payload = await websocket.receive_bytes()
        await websocket.send_bytes(b"echo:" + payload)


def test_ssh_websocket_requires_token(client) -> None:
    headers, _token = _auth(client)
    device = _create_device(client, headers)

    try:
        with client.websocket_connect(f"/api/ws/devices/{device['id']}/ssh"):
            raise AssertionError("websocket should reject missing token")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008


def test_ssh_websocket_relays_shell_io(client) -> None:
    headers, token = _auth(client)
    device = _create_device(client, headers)
    fake_service = FakeSshService()
    client.app.state.ssh_service = fake_service

    with client.websocket_connect(f"/api/ws/devices/{device['id']}/ssh?token={token}") as websocket:
        assert websocket.receive_json() == {"type": "status", "status": "connected"}
        assert websocket.receive_json() == {"type": "output", "data": "shell-ready\n"}
        websocket.send_json({"type": "input", "data": "echo ok\n"})
        assert websocket.receive_json() == {"type": "output", "data": "echo:echo ok\n"}
        websocket.send_json({"type": "resize", "columns": 120, "rows": 32})
        websocket.send_json({"type": "close"})

    assert "echo ok\n" in fake_service.shell.sent
    assert "resize:120x32" in fake_service.shell.sent
    assert fake_service.shell.closed is True


def test_vnc_websocket_rejects_missing_token_and_relays_bytes(client) -> None:
    headers, token = _auth(client)
    device = _create_device(client, headers)

    try:
        with client.websocket_connect(f"/api/ws/devices/{device['id']}/vnc"):
            raise AssertionError("websocket should reject missing token")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008

    client.app.state.vnc_relay_service = FakeVncRelayService()
    with client.websocket_connect(f"/api/ws/devices/{device['id']}/vnc?token={token}") as websocket:
        assert websocket.receive_bytes() == b"RFB 003.008\n"
        websocket.send_bytes(b"client-hello")
        assert websocket.receive_bytes() == b"echo:client-hello"
