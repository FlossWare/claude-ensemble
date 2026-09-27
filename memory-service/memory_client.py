#!/usr/bin/env python3
"""
RH Memory Client

Session-side client for connecting to Memory Service.
Used in rh-tools-init.sh to sync memory across sessions.
"""

import json
import socket
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

SOCKET_PATH = Path('/tmp/rh-memory.sock')


class MemoryClient:
    """Client for RH Memory Service"""

    def __init__(self, socket_path: Path = SOCKET_PATH, timeout: float = 2.0):
        self.socket_path = Path(socket_path)
        self.timeout = timeout
        self.connected = False

    def connect(self) -> bool:
        """Connect to memory service, fail gracefully if down"""
        try:
            if not self.socket_path.exists():
                logger.warning(f"Memory service not running (socket not found: {self.socket_path})")
                return False

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))

            # Test connection with ping
            response = self._send_request({'op': 'ping'})
            if response.get('ok'):
                self.connected = True
                logger.info("Connected to memory service")
                return True
            else:
                logger.warning("Memory service not responding")
                return False
        except Exception as e:
            logger.warning(f"Could not connect to memory service: {e}")
            return False

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to service, return parsed response"""
        try:
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

    def read(self, name: str) -> Optional[str]:
        """Read a memory file"""
        response = self._send_request({'op': 'read', 'name': name})
        if response.get('ok'):
            return response.get('content')
        return None

    def write(self, name: str, content: str) -> bool:
        """Write a memory file (overwrites)"""
        response = self._send_request({'op': 'write', 'name': name, 'content': content})
        return response.get('ok', False)

    def append(self, name: str, entry: Dict[str, Any]) -> bool:
        """Append entry to memory (JSONL)"""
        response = self._send_request({'op': 'append', 'name': name, 'entry': entry})
        return response.get('ok', False)

    def list(self) -> List[str]:
        """List all memory files"""
        response = self._send_request({'op': 'list'})
        if response.get('ok'):
            return response.get('files', [])
        return []

    def search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search memory files"""
        response = self._send_request({'op': 'search', 'keywords': keywords})
        if response.get('ok'):
            return response.get('results', [])
        return []


if __name__ == '__main__':
    # Test client
    logging.basicConfig(level=logging.INFO)
    client = MemoryClient()
    client.connect()

    if client.connected:
        print("✓ Connected to memory service")
        files = client.list()
        print(f"  Files: {len(files)}")
    else:
        print("✗ Memory service not available (will fall back to session-only cache)")
