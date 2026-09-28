#!/usr/bin/env python3
"""
Test suite for RH Learning Service and Client
"""

import sys
import json
import time
import socket
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.learning_client import LearningClient


class LearningServiceTester:
    """Test helper for learning service"""

    def __init__(self):
        self.socket_path = Path('/tmp/rh-learning-test.sock')
        self.service_process = None
        self.temp_dir = None

    def start_test_service(self):
        """Start a test instance of the learning service"""
        # Create temp directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)

        # Start service with custom socket and data dir
        service_script = str(Path(__file__).parent / 'learning_service.py')
        project_root = str(Path(__file__).parent.parent)

        # Create a wrapper script that uses our test socket
        wrapper = f"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, '{project_root}')

# Import from learning_service.py directly
import importlib.util
spec = importlib.util.spec_from_file_location("learning_service", "{service_script}")
module = importlib.util.module_from_spec(spec)
sys.modules["learning_service"] = module
spec.loader.exec_module(module)

service = module.LearningService(
    socket_path=Path('{self.socket_path}'),
    learning_dir=Path('{temp_path / "learning"}')
)
service.start()
"""

        print(f"Starting test service on {self.socket_path}")
        self.service_process = subprocess.Popen(
            [sys.executable, '-c', wrapper],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for socket to appear
        for i in range(50):  # 5 seconds max
            if self.socket_path.exists():
                print("✓ Service started")
                time.sleep(0.5)  # Extra stability
                return True
            time.sleep(0.1)

        # If failed, print stderr for debugging
        if self.service_process.poll() is not None:
            _, stderr = self.service_process.communicate()
            if stderr:
                print(f"Service error: {stderr.decode()}")

        print("✗ Service failed to start")
        return False

    def stop_test_service(self):
        """Stop the test service"""
        if self.service_process:
            self.service_process.terminate()
            try:
                self.service_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.service_process.kill()

        if self.socket_path.exists():
            self.socket_path.unlink()

        if self.temp_dir:
            self.temp_dir.cleanup()

        print("✓ Service stopped")

    def test_basic_ping(self):
        """Test basic ping"""
        client = LearningClient(socket_path=self.socket_path)
        response = client._send_request({'op': 'ping'})
        assert response.get('ok'), "Ping failed"
        print("✓ Ping test passed")

    def test_process_outcome(self):
        """Test recording an outcome"""
        client = LearningClient(socket_path=self.socket_path)

        success = client.process_outcome(
            task_id='test_001',
            task_type='code-review',
            model='haiku',
            rating=4,
            tokens=1200,
            cost=0.005
        )
        assert success, "Failed to process outcome"
        print("✓ Process outcome test passed")

    def test_get_report(self):
        """Test getting a report"""
        client = LearningClient(socket_path=self.socket_path)

        # Record some outcomes first
        for i in range(3):
            client.process_outcome(
                task_id=f'test_{i:03d}',
                task_type='documentation',
                model='haiku',
                rating=5,
                tokens=500,
                cost=0.002
            )

        report = client.get_report()
        assert report.get('ok'), "Failed to get report"
        assert report.get('total_outcomes', 0) >= 3, "Report missing outcomes"
        print(f"✓ Get report test passed (outcomes: {report.get('total_outcomes')})")

    def test_get_recent_outcomes(self):
        """Test getting recent outcomes"""
        client = LearningClient(socket_path=self.socket_path)

        # Record outcomes
        for i in range(2):
            client.process_outcome(
                task_id=f'recent_{i:03d}',
                task_type='testing',
                model='sonnet',
                rating=3,
                tokens=2000,
                cost=0.01
            )

        outcomes = client.get_recent_outcomes(days=7)
        assert len(outcomes) >= 2, "Failed to get recent outcomes"
        print(f"✓ Get recent outcomes test passed (outcomes: {len(outcomes)})")

    def test_multiple_models(self):
        """Test tracking multiple models"""
        client = LearningClient(socket_path=self.socket_path)

        models = ['haiku', 'sonnet', 'opus']
        for model in models:
            client.process_outcome(
                task_id=f'model_test_{model}',
                task_type='refactoring',
                model=model,
                rating=4,
                tokens=1500,
                cost=0.01 if model == 'haiku' else 0.05
            )

        report = client.get_report()
        assert report.get('ok'), "Failed to get report"
        by_model = report.get('by_model', {})
        assert len(by_model) >= 3, f"Expected 3+ models in report, got {len(by_model)}"
        print(f"✓ Multiple models test passed (models: {list(by_model.keys())})")

    def test_reset_learning(self):
        """Test resetting learning system"""
        client = LearningClient(socket_path=self.socket_path)

        # Record outcome
        client.process_outcome(
            task_id='reset_test',
            task_type='testing',
            model='haiku',
            rating=4,
            tokens=1000,
            cost=0.005
        )

        # Get initial count
        report_before = client.get_report()
        count_before = report_before.get('total_outcomes', 0)

        # Reset
        success = client.reset_learning()
        assert success, "Failed to reset learning"

        # Check count after reset
        report_after = client.get_report()
        count_after = report_after.get('total_outcomes', 0)

        assert count_after == 0, f"Reset failed: still have {count_after} outcomes"
        print("✓ Reset learning test passed")

    def run_all_tests(self):
        """Run all tests"""
        print("\n=== RH Learning Service Tests ===\n")

        try:
            if not self.start_test_service():
                return False

            self.test_basic_ping()
            self.test_process_outcome()
            self.test_get_report()
            self.test_get_recent_outcomes()
            self.test_multiple_models()
            self.test_reset_learning()

            print("\n✓ All tests passed!\n")
            return True

        except AssertionError as e:
            print(f"\n✗ Test failed: {e}\n")
            return False
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}\n")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.stop_test_service()


if __name__ == '__main__':
    tester = LearningServiceTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
