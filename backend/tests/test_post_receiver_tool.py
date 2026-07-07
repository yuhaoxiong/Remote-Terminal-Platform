from __future__ import annotations

import http.client
import io
import threading

from scripts.dev.post_receiver import create_server, render_body


def test_render_body_pretty_prints_json() -> None:
    body = render_body('{"message":"hello","count":2}'.encode(), "application/json")

    assert '"message": "hello"' in body
    assert '"count": 2' in body


def test_post_receiver_prints_request_content_and_returns_ok() -> None:
    output = io.StringIO()
    server = create_server("127.0.0.1", 0, output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        _, port = server.server_address[:2]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(
            "POST",
            "/hook?source=test",
            body='{"event":"created"}',
            headers={"Content-Type": "application/json", "X-Test": "ok"},
        )
        response = connection.getresponse()

        assert response.status == 200
        assert response.read() == b"OK\n"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    printed = output.getvalue()
    assert "=== HTTP POST" in printed
    assert "Path: /hook?source=test" in printed
    assert "X-Test: ok" in printed
    assert '"event": "created"' in printed
