#!/usr/bin/env python3
"""
Worker Daemon - Lightweight HTTP server for fleet workers
Replaces SSH for command execution and file deployment
Runs on each worker node on port 8003
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess
import os
import base64
import hashlib
from pathlib import Path

# Configuration
PORT = 8003
WORKER_HOME = Path.home()
ALLOWED_COMMANDS = ['worker-client.sh', 'worker-register.sh', 'python3', 'node']
AUTH_TOKEN = os.getenv('WORKER_AUTH_TOKEN', 'change-me-in-production')

class WorkerHandler(BaseHTTPRequestHandler):
    """Handle worker daemon requests"""

    def _authenticate(self):
        """Check Authorization header"""
        auth = self.headers.get('Authorization', '')
        return auth == f'Bearer {AUTH_TOKEN}'

    def _send_json(self, code, data):
        """Send JSON response"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests (health check)"""
        if self.path == '/health':
            self._send_json(200, {
                'status': 'healthy',
                'hostname': os.uname().nodename,
                'worker_home': str(WORKER_HOME),
                'port': PORT
            })
        else:
            self._send_json(404, {'error': 'Not found'})

    def do_POST(self):
        """Handle POST requests (execute, deploy)"""
        if not self._authenticate():
            self._send_json(401, {'error': 'Unauthorized'})
            return

        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())

            if self.path == '/execute':
                self._handle_execute(data)
            elif self.path == '/deploy':
                self._handle_deploy(data)
            else:
                self._send_json(404, {'error': 'Not found'})

        except Exception as e:
            self._send_json(500, {'error': str(e)})

    def _handle_execute(self, data):
        """Execute command on worker"""
        command = data.get('command', '')
        args = data.get('args', [])
        timeout = data.get('timeout', 30)

        # Security: only allow whitelisted commands
        cmd_base = command.split()[0] if command else ''
        if cmd_base not in ALLOWED_COMMANDS:
            self._send_json(403, {
                'error': f'Command not allowed: {cmd_base}',
                'allowed': ALLOWED_COMMANDS
            })
            return

        try:
            # Execute command
            result = subprocess.run(
                [command] + args,
                shell=True if '|' in command else False,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=WORKER_HOME
            )

            self._send_json(200, {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'success': result.returncode == 0
            })

        except subprocess.TimeoutExpired:
            self._send_json(408, {'error': f'Command timed out after {timeout}s'})
        except Exception as e:
            self._send_json(500, {'error': str(e)})

    def _handle_deploy(self, data):
        """Deploy file to worker"""
        filepath = data.get('path', '')
        content = data.get('content', '')
        encoding = data.get('encoding', 'utf8')  # or 'base64'
        mode = data.get('mode', 0o644)

        # Security: restrict to worker home directory
        target = WORKER_HOME / filepath
        if not str(target).startswith(str(WORKER_HOME)):
            self._send_json(403, {'error': 'Path outside worker home'})
            return

        try:
            # Decode content if base64
            if encoding == 'base64':
                content = base64.b64decode(content).decode('utf8')

            # Ensure parent directory exists
            target.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            target.write_text(content)
            target.chmod(mode)

            # Calculate checksum
            checksum = hashlib.sha256(content.encode()).hexdigest()

            self._send_json(200, {
                'path': str(target),
                'size': len(content),
                'checksum': checksum,
                'success': True
            })

        except Exception as e:
            self._send_json(500, {'error': str(e)})

    def log_message(self, format, *args):
        """Custom logging (less verbose)"""
        print(f"[{self.address_string()}] {format % args}")

def main():
    """Start worker daemon"""
    print(f"Worker Daemon starting on port {PORT}...")
    print(f"Worker home: {WORKER_HOME}")
    print(f"Auth token: {'***' + AUTH_TOKEN[-4:] if len(AUTH_TOKEN) > 4 else '***'}")
    print(f"Allowed commands: {', '.join(ALLOWED_COMMANDS)}")
    print()

    server = HTTPServer(('0.0.0.0', PORT), WorkerHandler)

    try:
        print(f"✓ Worker daemon listening on http://0.0.0.0:{PORT}")
        print("  Endpoints: /health (GET), /execute (POST), /deploy (POST)")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down worker daemon...")
        server.shutdown()

if __name__ == '__main__':
    main()
