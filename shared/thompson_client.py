#!/usr/bin/env python3
"""
RH Thompson Router Client

Session-side client for connecting to Thompson Router Service.
Used by rh-tools and hooks to select models and record outcomes.
Gracefully degrades if daemon is down.
"""

import json
import socket
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

SOCKET_PATH = Path('/tmp/rh-thompson.sock')


class ThompsonClient:
    """Client for RH Thompson Router Service"""

    def __init__(self, socket_path: Path = SOCKET_PATH, timeout: float = 2.0):
        self.socket_path = Path(socket_path)
        self.timeout = timeout
        self.connected = False

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to service, return parsed response"""
        try:
            if not self.socket_path.exists():
                logger.warning(f"Thompson service not running (socket not found: {self.socket_path})")
                return {'ok': False, 'error': 'service_unavailable'}

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))

            # Send request as JSON
            request_str = json.dumps(request) + '\n'
            sock.sendall(request_str.encode('utf-8'))

            # Read response
            response = b''
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                response += chunk
                if b'\n' in response:
                    break

            sock.close()

            return json.loads(response.decode('utf-8').strip())
        except socket.timeout:
            logger.warning(f"Thompson service timeout")
            return {'ok': False, 'error': 'timeout'}
        except Exception as e:
            logger.warning(f"Thompson service error: {e}")
            return {'ok': False, 'error': str(e)}

    def select_model(self, task_type: str, required_capability: float = 0.5, max_cost: float = float('inf')) -> str:
        """
        Select best model using Thompson Sampling.

        Args:
            task_type: Type of task (e.g., 'code-review', 'refactoring')
            required_capability: Minimum capability required (0-1)
            max_cost: Maximum cost threshold per call

        Returns:
            Selected model name (falls back to 'haiku' if service unavailable)
        """
        response = self._send_request({
            'action': 'select_model',
            'task_type': task_type,
            'required_capability': required_capability,
            'max_cost': max_cost
        })

        if response.get('ok'):
            return response.get('model', 'haiku')
        else:
            logger.warning(f"Thompson service unavailable, falling back to haiku")
            return 'haiku'

    def record_outcome(self, model: str, task_type: str, success: bool, cost: float, tokens: int = 0) -> bool:
        """
        Record outcome of a model call.

        Args:
            model: Model that was used
            task_type: Type of task
            success: Whether the task succeeded
            cost: Cost of the call (in dollars)
            tokens: Tokens used (optional)

        Returns:
            True if recorded successfully, False if service unavailable
        """
        response = self._send_request({
            'action': 'record_outcome',
            'model': model,
            'task_type': task_type,
            'success': success,
            'cost': cost,
            'tokens': tokens
        })

        if not response.get('ok'):
            logger.warning(f"Failed to record outcome: {response.get('error')}")
            return False

        return True

    def get_state(self) -> Optional[Dict[str, Any]]:
        """
        Get full state snapshot from service.

        Returns:
            State dict with model stats, or None if service unavailable
        """
        response = self._send_request({'action': 'get_state'})

        if response.get('ok'):
            return response.get('state')
        else:
            logger.warning(f"Failed to get state: {response.get('error')}")
            return None

    def reset(self, model: str) -> bool:
        """
        Reset history for a model.

        Args:
            model: Model name to reset

        Returns:
            True if reset successfully, False if service unavailable
        """
        response = self._send_request({
            'action': 'reset',
            'model': model
        })

        if not response.get('ok'):
            logger.warning(f"Failed to reset model: {response.get('error')}")
            return False

        return True

    def ping(self) -> bool:
        """Check if service is running"""
        response = self._send_request({'action': 'ping'})
        return response.get('ok', False)


if __name__ == '__main__':
    # Test client
    logging.basicConfig(level=logging.INFO)
    client = ThompsonClient()

    if client.ping():
        print("✓ Connected to Thompson service")
        model = client.select_model("test-task")
        print(f"  Selected model: {model}")
    else:
        print("✗ Thompson service not available (will use fallback)")
