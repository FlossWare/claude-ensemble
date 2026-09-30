#!/usr/bin/env python3
"""Cross-platform service manager - auto-runs ensemble_server on startup."""

import subprocess
import sys
import os
import time
from pathlib import Path


def start_services():
    """Start all Claude Ensemble services."""
    base_dir = Path(__file__).parent.parent

    # Start ensemble_server (which auto-spawns other services)
    script_path = base_dir / "server" / "ensemble_server.py"

    if not script_path.exists():
        print(f"Error: {script_path} not found")
        sys.exit(1)

    print(f"Starting Claude Ensemble services from {base_dir}")

    try:
        # Run ensemble_server in current process (never exits)
        os.chdir(base_dir)
        subprocess.run([sys.executable, str(script_path)])
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_services()
