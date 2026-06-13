#!/usr/bin/env bash
# run-agent.sh - Execute Claude agent on remote fleet servers
# Matches fleet-utils.js remoteAgent() pattern: SSH + claude -p with NFS-shared prompts

set -euo pipefail

# Configuration
NFS_ROOT="${NFS_ROOT:-${HOME}/Development}"
VERTEX_PROJECT="${ANTHROPIC_VERTEX_PROJECT_ID:-itpc-gcp-uie-eng-claude}"
VERTEX_ENABLED="${CLAUDE_CODE_USE_VERTEX:-1}"
GENAI_VERTEX="${GOOGLE_GENAI_USE_VERTEXAI:-True}"
PROMPTS_DIR="${NFS_ROOT}/fleet-results/.prompts"
RESULTS_DIR="${NFS_ROOT}/fleet-results/.results"
CLAUDE_FLAGS="--dangerously-skip-permissions --output-format json --max-turns 50 --no-session-persistence"

# Default values
SERVER=""
PROMPT=""
MODEL=""
TIMEOUT=180
JOB_ID="agent-$(date +%s)-$$"
CLEANUP=true
VERBOSE=false

# Usage
show_usage() {
    cat << 'EOF'
run-agent.sh - Execute Claude agent on remote fleet servers

USAGE:
  run-agent.sh --server <server> --prompt <prompt> [options]
  run-agent.sh --server <server> --prompt-file <file> [options]

REQUIRED:
  --server <name>          Target server (server-01, server-02, server-03)
  --prompt <text>          Prompt text (inline)
  --prompt-file <path>     Prompt from file (alternative to --prompt)

OPTIONS:
  --model <name>           AI model to use (default: auto)
  --timeout <seconds>      Timeout in seconds (default: 180)
  --job-id <id>            Job identifier (default: auto-generated)
  --no-cleanup             Keep temporary files after execution
  --verbose                Show debug output
  --help                   Show this help

EXAMPLES:
  # Simple inline prompt
  run-agent.sh --server server-01 --prompt "List files in current directory"

  # Prompt from file
  run-agent.sh --server server-02 --prompt-file /tmp/task.txt --model opus

  # With custom timeout and job ID
  run-agent.sh --server server-03 --prompt "Analyze code" --timeout 300 --job-id review-001

OUTPUT:
  JSON envelope from Claude agent:
  {
    "result": "...",
    "cost_usd": 0.001,
    "duration_ms": 1234,
    "is_error": false
  }

ENVIRONMENT:
  NFS_ROOT                      NFS shared directory (default: $HOME/Development)
  ANTHROPIC_VERTEX_PROJECT_ID   GCP Vertex AI project
  CLAUDE_CODE_USE_VERTEX        Enable Vertex AI (default: 1)
  GOOGLE_GENAI_USE_VERTEXAI     Enable Vertex for Gemini (default: True)

NOTES:
  - Prompts >= 4KB are written to NFS shared file
  - Requires passwordless SSH to target server
  - Requires Claude CLI on target server
  - Temporary files created in ${NFS_ROOT}/fleet-results/.prompts/

SEE ALSO:
  fleet-utils.js (remoteAgent function)
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --server)
            SERVER="$2"
            shift 2
            ;;
        --prompt)
            PROMPT="$2"
            shift 2
            ;;
        --prompt-file)
            if [[ ! -f "$2" ]]; then
                echo "Error: Prompt file not found: $2" >&2
                exit 1
            fi
            PROMPT="$(cat "$2")"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --job-id)
            JOB_ID="$2"
            shift 2
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            echo "Use --help for usage information" >&2
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SERVER" ]]; then
    echo "Error: --server is required" >&2
    echo "Use --help for usage information" >&2
    exit 1
fi

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt or --prompt-file is required" >&2
    echo "Use --help for usage information" >&2
    exit 1
fi

# Debug output
if [[ "$VERBOSE" == "true" ]]; then
    echo "[DEBUG] Server: $SERVER" >&2
    echo "[DEBUG] Model: ${MODEL:-auto}" >&2
    echo "[DEBUG] Timeout: ${TIMEOUT}s" >&2
    echo "[DEBUG] Job ID: $JOB_ID" >&2
    echo "[DEBUG] Prompt length: ${#PROMPT} bytes" >&2
fi

# Environment variable exports
ENV_EXPORTS="export ANTHROPIC_VERTEX_PROJECT_ID='${VERTEX_PROJECT}' && export CLAUDE_CODE_USE_VERTEX='${VERTEX_ENABLED}' && export GOOGLE_GENAI_USE_VERTEXAI='${GENAI_VERTEX}'"

# Determine prompt passing method
PROMPT_BYTES=${#PROMPT}
USED_PROMPT_FILE=false
CLAUDE_CMD=""

if [[ $PROMPT_BYTES -ge 4096 ]]; then
    # Large prompt: write to NFS file, read on remote
    if [[ "$VERBOSE" == "true" ]]; then
        echo "[DEBUG] Large prompt (${PROMPT_BYTES} bytes), using NFS file" >&2
    fi

    # Create prompts directory
    mkdir -p "$PROMPTS_DIR"

    # Write prompt to file
    PROMPT_FILE="${PROMPTS_DIR}/${JOB_ID}.txt"
    echo -n "$PROMPT" > "$PROMPT_FILE"

    CLAUDE_CMD="claude -p ${CLAUDE_FLAGS} \"\$(cat '${PROMPT_FILE}')\""
    USED_PROMPT_FILE=true
else
    # Small prompt: inline with single-quote escaping
    if [[ "$VERBOSE" == "true" ]]; then
        echo "[DEBUG] Small prompt (${PROMPT_BYTES} bytes), using inline" >&2
    fi

    # Escape single quotes: ' -> '\''
    ESCAPED_PROMPT="${PROMPT//\'/\'\\\'\'}"
    CLAUDE_CMD="claude -p ${CLAUDE_FLAGS} '${ESCAPED_PROMPT}'"
fi

# Add model flag if specified
if [[ -n "$MODEL" ]]; then
    CLAUDE_CMD="claude -p ${CLAUDE_FLAGS} --model ${MODEL} '${ESCAPED_PROMPT:-\$(cat \"${PROMPT_FILE}\")}'"
fi

# Full remote command
REMOTE_CMD="${ENV_EXPORTS} && cd '${NFS_ROOT}' && ${CLAUDE_CMD}"

# SSH command
SSH_CMD="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 ${SERVER} \"${REMOTE_CMD}\""

if [[ "$VERBOSE" == "true" ]]; then
    echo "[DEBUG] SSH command: ${SSH_CMD}" >&2
fi

# Cleanup function
cleanup() {
    local exit_code=$?

    if [[ "$CLEANUP" == "true" ]] && [[ "$USED_PROMPT_FILE" == "true" ]]; then
        if [[ -f "$PROMPT_FILE" ]]; then
            rm -f "$PROMPT_FILE" 2>/dev/null || true
            if [[ "$VERBOSE" == "true" ]]; then
                echo "[DEBUG] Cleaned up prompt file: $PROMPT_FILE" >&2
            fi
        fi
    fi

    exit $exit_code
}

trap cleanup EXIT INT TERM

# Execute remote agent
if [[ "$VERBOSE" == "true" ]]; then
    echo "[DEBUG] Executing agent on ${SERVER}..." >&2
fi

# Run SSH command with timeout
if ! RAW_OUTPUT=$(timeout "${TIMEOUT}s" bash -c "$SSH_CMD" 2>&1); then
    EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 124 ]]; then
        echo "Error: Agent execution timed out after ${TIMEOUT}s" >&2
        exit 124
    else
        echo "Error: Agent execution failed (exit code: ${EXIT_CODE})" >&2
        echo "$RAW_OUTPUT" >&2
        exit $EXIT_CODE
    fi
fi

# Filter out shell initialization messages (Universal AI, etc.)
# Extract only the JSON line (starts with { and ends with })
OUTPUT=$(echo "$RAW_OUTPUT" | grep -E '^\{.*\}$' | tail -1)

# Validate output
if [[ -z "$OUTPUT" ]]; then
    echo "Error: No JSON output from remote agent" >&2
    echo "Raw output:" >&2
    echo "$RAW_OUTPUT" >&2
    exit 1
fi

# Parse and validate JSON envelope
if ! echo "$OUTPUT" | jq . >/dev/null 2>&1; then
    echo "Error: Invalid JSON output from remote agent" >&2
    echo "$OUTPUT" >&2
    exit 1
fi

# Check for error flag
IS_ERROR=$(echo "$OUTPUT" | jq -r '.is_error // false')
if [[ "$IS_ERROR" == "true" ]]; then
    ERROR_MSG=$(echo "$OUTPUT" | jq -r '.result // "Unknown error"')
    echo "Error: Remote agent error: $ERROR_MSG" >&2
    exit 1
fi

# Output result
echo "$OUTPUT"

# Debug output
if [[ "$VERBOSE" == "true" ]]; then
    COST=$(echo "$OUTPUT" | jq -r '.cost_usd // 0')
    DURATION=$(echo "$OUTPUT" | jq -r '.duration_ms // 0')
    echo "[DEBUG] Cost: \$${COST}" >&2
    echo "[DEBUG] Duration: ${DURATION}ms" >&2
fi

exit 0
