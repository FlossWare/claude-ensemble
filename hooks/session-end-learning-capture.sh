#!/bin/bash
# Session End Learning Capture Hook
#
# Triggered when session ends - captures insights learned during conversation
# and automatically saves them to the memory service.
#
# The memory service handles indexing, deduplication, and persistence.

ENSEMBLE_ROOT="${ENSEMBLE_ROOT:-$HOME/Development/FlossWare/claude-ensemble}"
SESSION_LEARNING_LOG="${SESSION_LEARNING_LOG:-.claude-session-learning.log}"

# If session captured any learnings, save them to memory service
if [ -f "$SESSION_LEARNING_LOG" ]; then
    # Read learnings from session log
    python3 << 'PYTHON'
import json
import os
import sys
from pathlib import Path

ensemble_root = os.getenv('ENSEMBLE_ROOT', '')
if not ensemble_root:
    sys.exit(0)

sys.path.insert(0, str(Path(ensemble_root) / 'memory-service'))

try:
    from memory_client import MemoryClient

    log_file = os.getenv('SESSION_LEARNING_LOG', '.claude-session-learning.log')
    if not os.path.exists(log_file):
        sys.exit(0)

    client = MemoryClient()
    if not client.connect():
        sys.exit(0)

    # Read session learnings
    with open(log_file, 'r') as f:
        for line in f:
            try:
                learning = json.loads(line.strip())
                # Append to session_learnings memory file
                client.append('session_learnings', learning)
            except:
                pass

    # Clean up session log
    os.remove(log_file)

except:
    pass
PYTHON
fi
