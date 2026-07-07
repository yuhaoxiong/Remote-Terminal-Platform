from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TextIO


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 6080


def render_body(raw_body: bytes, content_type: str | None) -> str:
    text = raw_body.decode("utf-8", errors="replace")
    if content_type and "json" in content_type.lower() and text.strip():
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return text
    return text


def format_post_request(
    *,
    path: str,
    client: tuple[str, int] | None,
    headers: list[tuple[str, str]],
    body: str,
) -> str:
    client_text = f"{client[0]}:{client[1]}" if client else "unknown"
    header_lines = [f"{name}: {value}" for name, value in headers]
    return "\n".join(
        [
            "",
            f"=== HTTP POST {datetime.now().isoformat(timespec='seconds')} ===",
            f"Path: {path}",
            f"Client: {client_text}",
            "Headers:",
            *(header_lines or ["(none)"]),
            "Body:",
            body if body else "(empty)",
            "=== END ===",
            "",
        ]
    )


def make_handler(output: TextIO) -> type[BaseHTTPRequestHandler]:
    class PostReceiverHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = self.headers.get("Content-Length", "0")
            try:
                length = int(content_length)
            except ValueError:
                self.send_error(400, "Invalid Content-Length")
                return

            raw_body = self.rfile.read(length)
            body = render_body(raw_body, self.headers.get("Content-Type"))
            message = format_post_request(
                path=self.path,
                client=self.client_address,
                headers=list(self.headers.items()),
                body=body,
            )
            print(message, file=output, flush=True)

            response = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def do_GET(self) -> None:
            response = b"POST requests only.\n"
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            return

    return PostReceiverHandler


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    output: TextIO = sys.stdout,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(output))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Receive HTTP POST requests and print them to the terminal.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"listen host, default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"listen port, default: {DEFAULT_PORT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = create_server(args.host, args.port)
    host, port = server.server_address[:2]
    print(f"Listening for HTTP POST requests on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
