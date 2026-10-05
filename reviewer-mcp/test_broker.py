import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import broker


class BrokerTests(unittest.TestCase):
    def test_tools(self):
        self.assertEqual(
            {item["name"] for item in broker.TOOLS},
            {"review_grok", "review_perplexity", "review_jules", "review_all"},
        )

    def test_result_shape_and_normalization(self):
        value = broker.complete(
            "grok", "xai", "grok-4.7", broker.time.monotonic(),
            {
                "verdict": "nonsense",
                "summary": "clean",
                "findings": [
                    {"message": "keep", "path": "a.py", "line": 3},
                    {"path": "missing-message.py"},
                ],
            },
        )
        self.assertEqual(value["reviewer"], "grok")
        self.assertEqual(value["verdict"], "comment")
        self.assertEqual(value["findings"], [{"message": "keep", "path": "a.py", "line": 3}])

    def test_parse_surrounding_prose_without_greedy_object_capture(self):
        self.assertEqual(
            broker.parse('prefix {"verdict":"approve","summary":"one","findings":[]} suffix'),
            {"verdict": "approve", "summary": "one", "findings": []},
        )
        self.assertEqual(
            broker.parse('{"verdict":"comment","summary":"one","findings":[]} {"other":"ignored"}')['verdict'],
            "comment",
        )

    def test_provider_key_and_failure_isolation(self):
        with patch.dict(os.environ, {"XAI_API_KEY": "secret"}), patch(
            "broker.json_call", side_effect=RuntimeError("boom")
        ):
            result = broker.grok({
                "repository": "FlossWare/claude-ensemble",
                "pr_number": 1, "base_sha": "a", "head_sha": "b", "diff": "diff",
            })
        self.assertEqual(result["status"], "failed")
        self.assertIn("boom", result["error"])

    def test_review_all_preserves_order_and_isolates_failure(self):
        def good(name):
            return {"reviewer": name, "status": "complete"}

        def broken(_):
            raise RuntimeError("provider down")

        with patch.object(broker, "grok", side_effect=lambda p: good("grok")), \
             patch.object(broker, "perplexity", side_effect=broken), \
             patch.object(broker, "jules", side_effect=lambda p: good("jules")):
            result = broker.review_all({"repository": "x/y"})

        self.assertEqual([item["reviewer"] for item in result], ["grok", "perplexity", "jules"])
        self.assertEqual(result[1]["status"], "failed")
        self.assertIn("provider down", result[1]["error"])

    def test_mcp_notifications_produce_no_stdio_output(self):
        process = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("broker.py"))],
            input=json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized"
            }) + "\n",
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(process.stdout, "")

    def test_mcp_tools_list(self):
        process = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("broker.py"))],
            input=json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}
            }) + "\n",
            text=True, capture_output=True, check=True,
        )
        response = json.loads(process.stdout)
        self.assertEqual(response["id"], 1)
        self.assertEqual(len(response["result"]["tools"]), 4)


if __name__ == "__main__":
    unittest.main()
