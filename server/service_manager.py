#!/usr/bin/env python3
"""Cross-platform service manager - auto-runs ensemble_server on startup."""

import subprocess
import sys
import os
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def start_services():
    """Start all Claude Ensemble services."""
    base_dir = Path(__file__).parent.parent

    # Start ensemble_server (which auto-spawns other services)
    script_path = base_dir / "server" / "ensemble_server.py"

    if not script_path.exists():
        logger.error(f"Ensemble server script not found at {script_path}")
        sys.exit(1)

    logger.info(f"Starting Claude Ensemble services from {base_dir}")

    try:
        # Run ensemble_server in current process
        # Don't catch KeyboardInterrupt - let it propagate to subprocess
        os.chdir(base_dir)
        subprocess.run([sys.executable, str(script_path)])
    except Exception as e:
        logger.error(f"Error starting services: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    start_services()
