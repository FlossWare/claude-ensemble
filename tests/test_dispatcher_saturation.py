"""Regression coverage for nested REST calls under dispatcher saturation."""
from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen

from runtime.server import BoundedThreadingHTTPServer


class TinyBoundedServer(BoundedThreadingHTTPServer):
    max_workers = 4
    max_internal_workers = 2
    max_external_workers = 2


class SaturationHandler(BaseHTTPRequestHandler):
    barrier = threading.Barrier(2)

    def log_message(self, format, *args):
        pass

    def _reply(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/internal":
            self._reply(200, b"internal-ok")
            return
        if self.path == "/outer":
            try:
                self.barrier.wait(timeout=2)
                base = f"http://127.0.0.1:{self.server.server_address[1]}"
                request = Request(base + "/internal", headers={"X-CE-Internal-Call": "true"})
                with urlopen(request, timeout=2) as response:
                    body = response.read()
                self._reply(200 if body == b"internal-ok" else 502, b"outer-ok")
            except Exception:
                self._reply(500, b"nested-call-failed")
            return
        self._reply(404, b"not-found")


class DispatcherSaturationTests(unittest.TestCase):
    def test_reserved_internal_workers_survive_all_external_slots_being_busy(self):
        SaturationHandler.barrier = threading.Barrier(2)
        server = TinyBoundedServer(("127.0.0.1", 0), SaturationHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        results = []
        failures = []

        def call_outer():
            try:
                with urlopen(base + "/outer", timeout=4) as response:
                    results.append((response.status, response.read()))
            except Exception as exc:
                failures.append(exc)

        clients = [threading.Thread(target=call_outer) for _ in range(2)]
        try:
            for client in clients:
                client.start()
            for client in clients:
                client.join(timeout=5)
            self.assertFalse(any(client.is_alive() for client in clients), "outer requests deadlocked")
            self.assertEqual(failures, [])
            self.assertEqual(results, [(200, b"outer-ok"), (200, b"outer-ok")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
