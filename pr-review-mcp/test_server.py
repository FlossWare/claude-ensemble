import http.client
import json
import socket
import subprocess
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contract import ReviewRequest, ReviewResult
from server import GitLabWebhookHandler, normalize_gitlab_event, run_review


class ReviewContractTests(unittest.TestCase):
    def test_round_trip(self):
        request = ReviewRequest(
            request_id="test_001",
            platform="gitlab",
            repository="example/project",
            merge_request_id=7,
            title="Test MR",
            author="alice",
            source_branch="feature/test",
            target_branch="main",
        )
        self.assertEqual(ReviewRequest.from_dict(request.to_dict()), request)

    def test_gitlab_event_normalization(self):
        payload = {
            "object_kind": "merge_request",
            "user": {"username": "alice"},
            "project": {"path_with_namespace": "example/project", "id": 42},
            "object_attributes": {
                "iid": 7,
                "title": "Add feature",
                "source_branch": "feature/test",
                "target_branch": "main",
                "action": "open",
            },
        }
        request = normalize_gitlab_event(payload)
        self.assertEqual(request.platform, "gitlab")
        self.assertEqual(request.merge_request_id, 7)
        self.assertEqual(request.repository, "example/project")

    def test_request_validation(self):
        with self.assertRaises(ValueError):
            ReviewRequest.from_dict({
                "request_id": "x", "platform": "gitlab", "repository": "repo",
                "merge_request_id": 0, "title": "t", "author": "a",
                "source_branch": "src", "target_branch": "main",
            })
        with self.assertRaises(ValueError):
            ReviewRequest.from_dict({
                "request_id": "x", "platform": "unknown", "repository": "repo",
                "merge_request_id": 1, "title": "t", "author": "a",
                "source_branch": "src", "target_branch": "main",
            })

    def test_gitlab_event_rejects_invalid_iid_and_identity(self):
        payload = {
            "object_kind": "merge_request",
            "project": {"path_with_namespace": "example/project"},
            "object_attributes": {
                "iid": 0, "title": "Add feature",
                "source_branch": "feature/test", "target_branch": "main",
            },
        }
        with self.assertRaises(ValueError):
            normalize_gitlab_event(payload)
        payload["object_attributes"]["iid"] = "7"
        with self.assertRaises(ValueError):
            normalize_gitlab_event(payload)
        payload["object_attributes"]["iid"] = 7
        payload["project"].pop("path_with_namespace")
        with self.assertRaises(ValueError):
            normalize_gitlab_event(payload)

    def test_review_result_validation(self):
        result = ReviewResult.from_dict({
            "request_id": "test_001", "status": "complete", "decision": "comment",
            "summary": "ok", "findings": [], "model": "test", "cost_usd": 0.1,
            "metadata": {},
        }, expected_request_id="test_001")
        self.assertEqual(result.request_id, "test_001")
        with self.assertRaises(ValueError):
            ReviewResult.from_dict({
                "request_id": "other", "status": "complete", "decision": "comment",
                "summary": "ok", "findings": "bad", "model": "test", "cost_usd": 0.1,
                "metadata": {},
            }, expected_request_id="test_001")

    def test_review_command_uses_shell_style_arguments(self):
        import os
        from unittest.mock import patch
        request = ReviewRequest(
            request_id="test_001", platform="gitlab", repository="example/project",
            merge_request_id=7, title="Test MR", author="alice",
            source_branch="feature/test", target_branch="main",
        )
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({
                "request_id": "test_001", "status": "complete", "decision": "comment",
                "summary": "ok", "findings": [], "model": "test", "cost_usd": 0.0,
                "metadata": {},
            }), stderr="",
        )
        with patch.dict(os.environ, {"REVIEW_COMMAND": "python3 review_adapter.py --mode test"}), \
             patch("server.subprocess.run", return_value=completed) as run:
            run_review(request)
            self.assertEqual(run.call_args.args[0], ["python3", "review_adapter.py", "--mode", "test"])

    def test_mcp_initialize_and_tools(self):
        server = Path(__file__).with_name("server.py")
        process = subprocess.run(
            [sys.executable, str(server)],
            input=json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        response = json.loads(process.stdout)
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["tools"][0]["name"], "review_merge_request")
        schema = response["result"]["tools"][0]["inputSchema"]
        self.assertEqual(schema["properties"]["platform"]["enum"], ["gitlab", "github", "bitbucket"])
        self.assertEqual(schema["properties"]["merge_request_id"]["minimum"], 1)


    def test_http_content_length_validation(self):
        from http.server import ThreadingHTTPServer

        http_server = ThreadingHTTPServer(("127.0.0.1", 0), GitLabWebhookHandler)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        try:
            port = http_server.server_address[1]
            # HTTPConnection supplies Content-Length: 0 when omitted, so use
            # a raw socket for the genuinely absent-header case.
            sock = socket.create_connection(("127.0.0.1", port), timeout=5)
            sock.sendall(b"POST /webhooks/gitlab HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\n\\r\\n")
            raw = sock.recv(4096).decode()
            self.assertIn("400", raw)
            self.assertIn("invalid Content-Length", raw)
            sock.close()

            for headers in ({"Content-Length": "abc"}, {"Content-Length": "-1"}):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("POST", "/webhooks/gitlab", headers=headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertIn("invalid Content-Length", response.read().decode())
                connection.close()

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request(
                "POST",
                "/webhooks/gitlab",
                headers={"Content-Length": "2000001"},
            )
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
            connection.close()
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=5)
