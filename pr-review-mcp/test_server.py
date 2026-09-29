import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from contract import ReviewRequest
from server import normalize_gitlab_event


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
