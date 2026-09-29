#!/usr/bin/env python3

import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from messenger_client import MessengerClient
from messenger_service import MessengerServer


class MessengerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "messenger.sock"
        self.server = MessengerServer(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 2
        while not self.path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)

    def tearDown(self):
        self.server.stop()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def test_multiple_subscribers_receive_publish(self):
        clients = [MessengerClient(self.path) for _ in range(2)]
        received = [[], []]

        def listen(index):
            for message in clients[index].subscribe("test", reconnect=False):
                received[index].append(message)
                break

        threads = [threading.Thread(target=listen, args=(i,), daemon=True) for i in range(2)]
        for thread in threads:
            thread.start()

        deadline = time.monotonic() + 2
        while sum(len(items) for items in received) < 2 and time.monotonic() < deadline:
            clients[0].publish("test", {"value": 42})
            time.sleep(0.02)

        for thread in threads:
            thread.join(timeout=2)

        self.assertEqual(received[0][0]["data"]["value"], 42)
        self.assertEqual(received[1][0]["data"]["value"], 42)

    def test_publish_without_subscribers_is_successful(self):
        self.assertEqual(MessengerClient(self.path).publish("empty", {"value": 1}), 0)

    def test_socket_is_private(self):
        mode = self.path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_invalid_operation_is_rejected(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(self.path))
            client.sendall(b'{"op":"bogus","topic":"test"}\n')
            reader = client.makefile("r", encoding="utf-8")
            response = reader.readline()
            reader.close()
        self.assertIn('"ok":false', response)


if __name__ == "__main__":
    unittest.main()
