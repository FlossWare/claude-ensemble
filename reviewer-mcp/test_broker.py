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

    def test_result_shape(self):
        value = broker.complete(
            "grok", "xai", "grok-4.7", broker.time.monotonic(),
            {"verdict": "approve", "summary": "clean", "findings": []},
        )
        self.assertEqual(value["reviewer"], "grok")
        self.assertEqual(value["verdict"], "approve")

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
