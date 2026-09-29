#!/usr/bin/env python3
"""Tests for the alert service."""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path


SERVICE = Path(__file__).with_name("alert_service.py")


def send_request(socket_path: Path, request: dict) -> dict:
    """Send a JSON request to the alert service and get response."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(socket_path))
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        response = b""
        while b"\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        return json.loads(response.decode("utf-8").strip())


class AlertServiceTest(unittest.TestCase):
    def test_alert_store_initialization(self):
        """Verify AlertStore initializes config correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            alerts_dir = Path(temp_dir) / "alerts"

            # Import the AlertStore class from alert_service module
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from alert_service.alert_service import AlertStore

            # Create store - should initialize config
            store = AlertStore(alerts_dir)

            config_file = alerts_dir / "config.json"
            self.assertTrue(config_file.exists(), "config.json should be created")

            config = json.loads(config_file.read_text())
            self.assertIn("cost_spike_threshold_multiplier", config)
            self.assertIn("quality_drop_threshold", config)
            self.assertIn("enabled", config)
            self.assertIn("email_recipient", config)

    def test_alert_store_get_config(self):
        """Verify AlertStore reads config correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            alerts_dir = Path(temp_dir) / "alerts"

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from alert_service.alert_service import AlertStore

            store = AlertStore(alerts_dir)
            config = store.get_config()

            self.assertIsInstance(config, dict)
            self.assertGreater(len(config), 0)
            self.assertEqual(config.get("enabled"), True)

    def test_alert_store_save_alert(self):
        """Verify AlertStore saves alerts to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            alerts_dir = Path(temp_dir) / "alerts"

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from alert_service.alert_service import AlertStore

            store = AlertStore(alerts_dir)

            alert = {
                "alert_type": "cost_spike",
                "severity": "high",
                "message": "Cost exceeded threshold",
                "timestamp": datetime.now().isoformat()
            }

            success = store.save_alert(alert)
            self.assertTrue(success, "save_alert should succeed")

            # Check alert file was created
            alert_files = list(alerts_dir.glob("cost_spike_*.json"))
            self.assertEqual(len(alert_files), 1, "should have created one alert file")

            # Verify alert content
            saved_alert = json.loads(alert_files[0].read_text())
            self.assertEqual(saved_alert["alert_type"], "cost_spike")

if __name__ == "__main__":
    unittest.main()
