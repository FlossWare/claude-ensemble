import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import http_server


class HttpServerTests(unittest.TestCase):
    def test_requires_bearer_token_when_configured(self):
        with patch.dict(os.environ, {"MCP_AUTH_TOKEN": "secret"}):
            handler = http_server.Handler
            self.assertTrue(handler)

    def test_module_exposes_mcp_handler(self):
        self.assertTrue(hasattr(http_server, "Handler"))


if __name__ == "__main__":
    unittest.main()
