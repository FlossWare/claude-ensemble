#!/usr/bin/env python3
"""
RH Learning Client

Session-side client for connecting to Learning Service.
Used by sessions to record task outcomes and retrieve learning summaries.
Graceful degradation if daemon is not running.
"""

import json
import socket
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

SOCKET_PATH = Path('/tmp/rh-learning.sock')


class LearningClient:
    """Client for RH Learning Service"""

    def __init__(self, socket_path: Path = SOCKET_PATH, timeout: float = 3.0):
        """Initialize learning client

        Args:
            socket_path: Path to learning service socket
            timeout: Connection timeout in seconds
        """
        self.socket_path = Path(socket_path)
        self.timeout = timeout

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to service, return parsed response"""
        try:
            if not self.socket_path.exists():
                logger.warning(f"Learning service not running (socket not found: {self.socket_path})")
                return {'ok': False, 'error': 'Service not available'}

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
        except Exception as e:
            logger.warning(f"Request error: {e}")
            return {'ok': False, 'error': str(e)}

    def process_outcome(self, task_id: str, task_type: str, model: str,
                       rating: int, tokens: int, cost: float) -> bool:
        """Record a task outcome

        Args:
            task_id: Unique task identifier
            task_type: Type of task (code-review, documentation, testing, etc.)
            model: Model used (haiku, sonnet, opus, etc.)
            rating: Quality rating (0-5)
            tokens: Tokens used
            cost: Cost in dollars

        Returns:
            True if recorded successfully, False otherwise
        """
        response = self._send_request({
            'op': 'process_outcome',
            'task_id': task_id,
            'task_type': task_type,
            'model': model,
            'rating': rating,
            'tokens': tokens,
            'cost': cost
        })
        return response.get('ok', False)

    def get_report(self) -> Dict[str, Any]:
        """Get learning summary report

        Returns:
            Report dict with model/task statistics
        """
        response = self._send_request({'op': 'get_report'})
        if response.get('ok'):
            return response
        return {'ok': False, 'error': 'Failed to get report'}

    def get_recent_outcomes(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent task outcomes

        Args:
            days: Number of days to look back (default 7)

        Returns:
            List of outcome dicts
        """
        response = self._send_request({
            'op': 'get_recent_outcomes',
            'days': days
        })
        if response.get('ok'):
            return response.get('outcomes', [])
        return []

    def reset_learning(self) -> bool:
        """Clear all learning outcomes and priors

        Returns:
            True if reset successfully, False otherwise
        """
        response = self._send_request({'op': 'reset_learning'})
        return response.get('ok', False)


if __name__ == '__main__':
    # Test client
    logging.basicConfig(level=logging.INFO)
    client = LearningClient()

    # Try to connect and ping
    result = client._send_request({'op': 'ping'})
    if result.get('ok'):
        print("✓ Connected to learning service")
        report = client.get_report()
        print(f"  Report: {json.dumps(report, indent=2)}")
    else:
        print("✗ Learning service not available (will fall back to local mode)")
