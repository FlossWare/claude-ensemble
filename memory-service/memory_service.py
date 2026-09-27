#!/usr/bin/env python3
"""
RH Memory Service Daemon

Central memory authority for all Claude Code sessions.
Runs as systemd user service, listens on Unix socket.
Handles concurrent access, file locking, memory operations.
"""

import json
import logging
import socket
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / '.claude' / 'rh-memory-service.log')
    ]
)
logger = logging.getLogger(__name__)

MEMORY_DIR = Path.home() / '.claude' / 'projects' / '-home-sfloess' / 'memory'
SOCKET_PATH = Path('/tmp/rh-memory.sock')


class MemoryStore:
    """Thread-safe memory file operations"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def read_file(self, name: str) -> Optional[str]:
        """Read a memory file"""
        path = self.memory_dir / f"{name}.md"

        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {name}: {e}")
            return None

    def write_file(self, name: str, content: str) -> bool:
        """Write a memory file"""
        path = self.memory_dir / f"{name}.md"

        try:
            with self.lock:
                with open(path, 'w') as f:
                    f.write(content)
            logger.info(f"Wrote memory: {name}")
            return True
        except Exception as e:
            logger.error(f"Error writing {name}: {e}")
            return False

    def append_entry(self, name: str, entry: Dict[str, Any]) -> bool:
        """Append entry to a memory file (JSONL style)"""
        path = self.memory_dir / f"{name}.jsonl"

        try:
            with self.lock:
                with open(path, 'a') as f:
                    entry['timestamp'] = datetime.utcnow().isoformat()
                    f.write(json.dumps(entry) + '\n')
            logger.info(f"Appended to {name}")
            return True
        except Exception as e:
            logger.error(f"Error appending to {name}: {e}")
            return False

    def list_files(self) -> List[str]:
        """List all memory files"""
        return [f.stem for f in self.memory_dir.glob('*.md')]

    def search(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Search memory files for keywords"""
        results = []

        for md_file in self.memory_dir.glob('*.md'):
            try:
                with open(md_file, 'r') as f:
                    content = f.read().lower()

                # Check if any keyword matches
                matches = sum(1 for kw in keywords if kw.lower() in content)

                if matches > 0:
                    results.append({
                        'file': md_file.stem,
                        'matched_keywords': matches,
                        'size_bytes': len(content)
                    })
            except Exception as e:
                logger.debug(f"Error searching {md_file}: {e}")

        return sorted(results, key=lambda x: x['matched_keywords'], reverse=True)


class MemoryService:
    """Memory service daemon"""

    def __init__(self, socket_path: Path, memory_dir: Path):
        self.socket_path = Path(socket_path)
        self.store = MemoryStore(memory_dir)
        self.socket = None

    def start(self):
        """Start the service"""
        logger.info("Starting RH Memory Service")

        # Clean up old socket if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create Unix domain socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(5)
        self.socket.settimeout(None)

        logger.info(f"Listening on {self.socket_path}")

        try:
            while True:
                conn, _ = self.socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                thread.start()
        except KeyboardInterrupt:
            logger.info("Shutting down")
            self.stop()
        except Exception as e:
            logger.error(f"Service error: {e}")
            self.stop()

    def stop(self):
        """Stop the service"""
        if self.socket:
            self.socket.close()
        if self.socket_path.exists():
            self.socket_path.unlink()
        logger.info("Memory service stopped")

    def _handle_client(self, conn: socket.socket):
        """Handle client request"""
        try:
            conn.settimeout(5.0)
            # Read request (ends with newline)
            data = b''
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:  # End of request
                    break

            request_str = data.decode('utf-8').strip()
            if not request_str:
                return

            response = self._process_request(request_str)

            # Send response
            conn.sendall((response + '\n').encode('utf-8'))
        except socket.timeout:
            logger.debug("Client timeout")
            try:
                conn.sendall(b'{"ok": false, "error": "timeout"}\n')
            except:
                pass
        except Exception as e:
            logger.error(f"Client error: {e}")
            try:
                conn.sendall(b'{"ok": false, "error": "server error"}\n')
            except:
                pass
        finally:
            try:
                conn.close()
            except:
                pass

    def _process_request(self, request: str) -> str:
        """Process a request, return JSON response"""
        try:
            req_data = json.loads(request)
            operation = req_data.get('op')

            if operation == 'read':
                name = req_data.get('name')
                content = self.store.read_file(name)
                return json.dumps({'ok': content is not None, 'content': content})

            elif operation == 'write':
                name = req_data.get('name')
                content = req_data.get('content')
                success = self.store.write_file(name, content)
                return json.dumps({'ok': success})

            elif operation == 'append':
                name = req_data.get('name')
                entry = req_data.get('entry', {})
                success = self.store.append_entry(name, entry)
                return json.dumps({'ok': success})

            elif operation == 'list':
                files = self.store.list_files()
                return json.dumps({'ok': True, 'files': files})

            elif operation == 'search':
                keywords = req_data.get('keywords', [])
                results = self.store.search(keywords)
                return json.dumps({'ok': True, 'results': results})

            elif operation == 'ping':
                return json.dumps({'ok': True, 'message': 'pong'})

            else:
                return json.dumps({'ok': False, 'error': f'Unknown operation: {operation}'})

        except json.JSONDecodeError:
            return json.dumps({'ok': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Request error: {e}")
            return json.dumps({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    service = MemoryService(SOCKET_PATH, MEMORY_DIR)
    service.start()
