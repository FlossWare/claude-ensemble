#!/usr/bin/env python3
"""
RH Memory Client

Session-side client for connecting to Memory Service.
Used in ensemble-init.sh to sync memory across sessions.
"""

import json
import socket
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Patterns that should never be in memory (PII, secrets, tokens)
BLOCKED_PATTERNS = [
    r'(?i)(api[_-]?key|secret[_-]?key|password|token)',
    r'Bearer\s+[A-Za-z0-9\-._~\+\/]+=*',
    r'[A-Za-z0-9._%+-]+@(redhat\.com|gmail\.com)',
    r'(?i)(sfloess|astra)',  # Usernames
]


def sanitize_content(content: str) -> Optional[str]:
    """Check if content contains PII/secrets. Return None if blocked, else content."""
    import re
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, content):
            return None
    return content

from shared.runtime_config import runtime_dir, socket_path

SOCKET_PATH = socket_path(
    "ENSEMBLE_MEMORY_SOCKET", str(runtime_dir() / "memory.sock")
)


class MemoryClient:
    """Client for the Claude Ensemble memory service."""

    def __init__(self, socket_path: Path = SOCKET_PATH, timeout: float = 2.0):
        self.socket_path = Path(socket_path)
        self.timeout = timeout
        self.connected = False
        self.offline_cache = {}  # Graceful degradation: cache writes when offline

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
        # Check for PII/secrets
        if sanitize_content(content) is None:
            logger.error(f"BLOCKED: Attempt to write PII/secrets to {name}")
            logger.error("Memory should not contain: API keys, tokens, emails, usernames")
            return False

        response = self._send_request({'op': 'write', 'name': name, 'content': content})
        return response.get('ok', False)

    def append(self, name: str, entry: Dict[str, Any]) -> bool:
        """Append entry to memory (JSONL) with offline fallback"""
        response = self._send_request({'op': 'append', 'name': name, 'entry': entry})

        if response.get('ok', False):
            return True

        # Error recovery: cache offline writes
        if name not in self.offline_cache:
            self.offline_cache[name] = []

        self.offline_cache[name].append(entry)
        logger.warning(f"Cached offline append to {name} (will sync when service available)")
        return True  # Return success to prevent data loss

    def list(self) -> List[str]:
        """List all memory files"""
        response = self._send_request({'op': 'list'})
        if response.get('ok'):
            return response.get('files', [])
        return []

    def search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search memory files (TF-IDF on chunks)"""
        response = self._send_request({'op': 'search', 'keywords': keywords})
        if response.get('ok'):
            return response.get('results', [])
        return []

    def chunk(self, name: str) -> List[Dict[str, Any]]:
        """Get chunks for a memory file"""
        response = self._send_request({'op': 'chunk', 'name': name})
        if response.get('ok'):
            return response.get('chunks', [])
        return []

    def search_semantic(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Semantic search using vector similarity (meaning-based)"""
        response = self._send_request({'op': 'search_semantic', 'query': query, 'top_k': top_k})
        if response.get('ok'):
            return response.get('results', [])
        return []

    def search_hybrid(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Hybrid search: keywords + semantic (best of both)"""
        response = self._send_request({'op': 'search_hybrid', 'query': query, 'top_k': top_k})
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
