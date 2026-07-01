#!/bin/bash
# SSH Worker Wrapper - Handles stdin piping to remote workers
# Usage: ssh-worker-wrapper.sh <worker> <script> <json_input>

WORKER="$1"
SCRIPT="$2"
JSON_INPUT="$3"

# Pipe JSON to remote worker via SSH
echo "$JSON_INPUT" | ssh -o LogLevel=ERROR "claude@${WORKER}" python3 "${SCRIPT}"
