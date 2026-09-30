#!/usr/bin/env python3
"""Tests for the REST memory adapter."""

import unittest
from unittest.mock import patch

from server.memory_service import MemoryHTTPService


class MemoryHTTPServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = MemoryHTTPService("/tmp/test-memory.sock")

    @patch.object(MemoryHTTPService, "request")
    def test_read_maps_to_memory_protocol(self, request):
        request.return_value = {"ok": True, "content": "hello"}
        status, body = self.service.dispatch("GET", ["read", "notes"], None)
        self.assertEqual(status, 200)
        self.assertEqual(body["content"], "hello")
        request.assert_called_once_with({"op": "read", "name": "notes"})

    @patch.object(MemoryHTTPService, "request")
    def test_write_maps_to_memory_protocol(self, request):
        request.return_value = {"ok": True}
        status, body = self.service.dispatch(
            "PUT", ["write", "notes"], {"content": "hello"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        request.assert_called_once_with(
            {"op": "write", "name": "notes", "content": "hello"}
        )

    @patch.object(MemoryHTTPService, "request")
    def test_unavailable_memory_returns_503(self, request):
        request.side_effect = ConnectionError("memory service unavailable")
        status, body = self.service.dispatch("GET", ["ping"], None)
        self.assertEqual(status, 503)
        self.assertIn("unavailable", body["error"])

    def test_unknown_route_is_not_found(self):
        status, body = self.service.dispatch("GET", ["unknown"], None)
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
