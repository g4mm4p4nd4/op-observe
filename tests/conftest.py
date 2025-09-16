import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List

import pytest
from socketserver import ThreadingMixIn


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class LokiTestServer:
    def __init__(self) -> None:
        self._requests: List[Dict[str, object]] = []
        handler = self._build_handler()
        self._server = _ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _build_handler(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # type: ignore[override]
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                parent._requests.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers),
                        "body": body,
                        "json": json.loads(body.decode()) if body else None,
                    }
                )
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args) -> None:  # noqa: A003 - required by base class
                return

        return Handler

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def requests(self) -> List[Dict[str, object]]:
        return list(self._requests)

    def last_json(self) -> Dict[str, object]:
        if not self._requests:
            raise AssertionError("No Loki requests captured")
        json_payload = self._requests[-1]["json"]
        assert isinstance(json_payload, dict)
        return json_payload

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


@pytest.fixture
def loki_server() -> LokiTestServer:
    server = LokiTestServer()
    try:
        yield server
    finally:
        server.stop()
