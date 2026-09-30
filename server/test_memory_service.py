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
    def test_search_route_wins_over_body_op(self, request):
        request.return_value = {"ok": True, "results": []}
        status, body = self.service.dispatch(
            "POST",
            ["search"],
            {"op": "write", "name": "notes", "content": "should not write"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["ok"], True)
        request.assert_called_once_with(
            {
                "op": "search",
                "name": "notes",
                "content": "should not write",
            }
        )

    def test_write_requires_string_content(self):
        for content in (None, 123, {"text": "hello"}, ["hello"]):
            with self.subTest(content=content):
                status, body = self.service.dispatch(
                    "PUT", ["write", "notes"], {"content": content}
                )
                self.assertEqual(status, 400)
                self.assertEqual(body, {"error": "content must be a string"})

    @patch.object(MemoryHTTPService, "request")
    def test_encoded_memory_name_is_decoded(self, request):
        request.return_value = {"ok": True, "content": "hello"}
        status, body = self.service.dispatch("GET", ["read", "my%20notes"], None)
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "invalid memory name"})
        request.assert_not_called()

    @patch.object(MemoryHTTPService, "request")
    def test_invalid_memory_name_is_rejected(self, request):
        status, body = self.service.dispatch("GET", ["read", "../notes"], None)
        self.assertEqual(status, 400)
        self.assertEqual(body, {"error": "invalid memory name"})
        request.assert_not_called()

    @patch.object(MemoryHTTPService, "request")
    def test_search_validates_route_specific_input(self, request):
        request.return_value = {"ok": True, "results": []}
        status, _ = self.service.dispatch("POST", ["search"], {"keywords": ["one"], "top_k": 10})
        self.assertEqual(status, 200)
        request.assert_called_once_with({"op": "search", "keywords": ["one"], "top_k": 10})

        request.reset_mock()
        status, body = self.service.dispatch("POST", ["search"], {"keywords": "one"})
        self.assertEqual(status, 400)
        self.assertIn("keywords", body["error"])
        request.assert_not_called()

    @patch.object(MemoryHTTPService, "request")
    def test_semantic_search_validates_query_and_top_k(self, request):
        status, body = self.service.dispatch("POST", ["search_semantic"], {"query": ""})
        self.assertEqual(status, 400)
        self.assertIn("query", body["error"])
        request.assert_not_called()

        status, body = self.service.dispatch("POST", ["search_semantic"], {"query": "hello", "top_k": 0})
        self.assertEqual(status, 400)
        self.assertIn("top_k", body["error"])
        request.assert_not_called()

    @patch.object(MemoryHTTPService, "request")
    def test_oversized_daemon_response_is_rejected(self, request):
        from server import memory_service

        original = memory_service.MAX_MEMORY_RESPONSE_SIZE
        try:
            memory_service.MAX_MEMORY_RESPONSE_SIZE = 8
            class FakeSocket:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def settimeout(self, _timeout):
                    pass
                def connect(self, _path):
                    pass
                def sendall(self, _data):
                    pass
                def recv(self, _size):
                    return b"x" * 9

            with patch("server.memory_service.socket.socket", return_value=FakeSocket()):
                with self.assertRaises(ConnectionError, msg="oversized response must be rejected"):
                    self.service.request({"op": "read", "name": "notes"})
        finally:
            memory_service.MAX_MEMORY_RESPONSE_SIZE = original

    @patch.object(MemoryHTTPService, "request")
    def test_unexpected_daemon_failure_maps_to_bad_gateway(self, request):
        request.return_value = {"ok": False, "error": "storage failure"}
        status, body = self.service.dispatch("GET", ["ping"], None)
        self.assertEqual(status, 502)
        self.assertEqual(body, {"error": "storage failure"})

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
