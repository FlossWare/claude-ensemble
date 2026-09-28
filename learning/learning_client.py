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
import uuid
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
                       rating: int, tokens: int, cost: float, request_id: str = None) -> bool:
        """Record a task outcome

        Args:
            task_id: Unique task identifier
            task_type: Type of task (code-review, documentation, testing, etc.)
            model: Model used (haiku, sonnet, opus, etc.)
            rating: Quality rating (0-5)
            tokens: Tokens used
            cost: Cost in dollars
            request_id: Request correlation ID for tracing

        Returns:
            True if recorded successfully, False otherwise
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        response = self._send_request({
            'op': 'process_outcome',
            'task_id': task_id,
            'task_type': task_type,
            'model': model,
            'rating': rating,
            'tokens': tokens,
            'cost': cost,
            'request_id': request_id
        })

        if response.get('ok'):
            logger.info(f"[{request_id}] Recorded outcome: {task_id} ({model}, rating={rating})")
        else:
            logger.warning(f"[{request_id}] Failed to record outcome: {response.get('error')}")

        return response.get('ok', False)

    def get_report(self, request_id: str = None) -> Dict[str, Any]:
        """Get learning summary report

        Args:
            request_id: Request correlation ID for tracing

        Returns:
            Report dict with model/task statistics
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        response = self._send_request({'op': 'get_report', 'request_id': request_id})
        if response.get('ok'):
            logger.info(f"[{request_id}] Retrieved learning report")
            return response
        logger.warning(f"[{request_id}] Failed to get report: {response.get('error')}")
        return {'ok': False, 'error': 'Failed to get report', 'request_id': request_id}

    def get_recent_outcomes(self, days: int = 7, request_id: str = None) -> List[Dict[str, Any]]:
        """Get recent task outcomes

        Args:
            days: Number of days to look back (default 7)
            request_id: Request correlation ID for tracing

        Returns:
            List of outcome dicts
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        response = self._send_request({
            'op': 'get_recent_outcomes',
            'days': days,
            'request_id': request_id
        })
        if response.get('ok'):
            logger.info(f"[{request_id}] Retrieved {len(response.get('outcomes', []))} recent outcomes")
            return response.get('outcomes', [])
        logger.warning(f"[{request_id}] Failed to get recent outcomes: {response.get('error')}")
        return []

    def reset_learning(self, request_id: str = None) -> bool:
        """Clear all learning outcomes and priors

        Args:
            request_id: Request correlation ID for tracing

        Returns:
            True if reset successfully, False otherwise
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        response = self._send_request({'op': 'reset_learning', 'request_id': request_id})
        if response.get('ok'):
            logger.info(f"[{request_id}] Learning system reset")
        else:
            logger.warning(f"[{request_id}] Failed to reset learning: {response.get('error')}")
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
