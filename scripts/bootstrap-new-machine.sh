#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
VERBOSE=false
PI01_HOST="services.flossware.org"
PI01_PORT=2222
API_BASE="http://localhost:5000"
REPO_URL="git@gitlab.cee.redhat.com:sfloess/claude-global-skills.git"
CLAUDE_UID=2000

TUNNEL_PORTS=(
  5000:aio-01:5000
  6379:aio-01:6379
  5433:aio-01:5433
  2424:aio-01:2424
  3000:aio-01:3000
  9090:aio-01:9090
)

FLEET_HOSTS=(
  "aio-01:aio-01"
  "server-01:server-01"
  "server-02:server-02"
  "server-03:server-03"
  "desktop-ap:desktop-ap"
  "server-ap:server-ap"
  "pi-02:pi-02"
  "util-ap:util-ap"
)

OPENCODE_PROVIDERS=(
  "anthropic:ANTHROPIC_API_KEY"
  "openrouter:PERSONAL_OPENROUTER_API_KEY"
  "groq:PERSONAL_GROQ_API_KEY"
  "cerebras:PERSONAL_CEREBRAS_API_KEY"
  "deepseek:PERSONAL_DEEPSEEK_API_KEY"
  "google:GOOGLE_API_KEY"
  "mistral:PERSONAL_MISTRAL_API_KEY"
  "openai:PERSONAL_OPENAI_API_KEY"
)

log() { echo "[$(date '+%H:%M:%S')] $*"; }
run() {
  if $DRY_RUN; then
    log "[DRY-RUN] $*"
  else
    $VERBOSE && log "[RUN] $*"
    "$@"
  fi
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Bootstrap a new machine for the distributed LLM orchestration fleet.
Sets up SSH, tunnels, API keys, AI tools, and syncs knowledge.

Options:
  --dry-run     Show what would be done without executing
  --verbose     Show detailed output
  --skip-tools  Skip installing Claude Code and OpenCode
  --skip-repo   Skip cloning the main repo
  --help        Show this help

Prerequisites:
  - SSH key that can reach pi-01 (${PI01_HOST}:${PI01_PORT})
  - Internet access for tool installation
EOF
  exit 0
}

setup_ssh_config() {
  log "Setting up SSH config..."
  local config_file="$HOME/.ssh/config"
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"

  if grep -q "Host pi-01" "$config_file" 2>/dev/null; then
    log "SSH config already has pi-01 entry, skipping"
    return 0
  fi

  run cat >> "$config_file" <<'SSHEOF'

Host *
   LogLevel ERROR
   StrictHostKeyChecking no
   UserKnownHostsFile=/dev/null

Host pi-01
    HostName services.flossware.org
    Port 2222
    User root

SSHEOF

  for entry in "${FLEET_HOSTS[@]}"; do
    local alias="${entry%%:*}"
    local hostname="${entry#*:}"
    run cat >> "$config_file" <<SSHEOF

Host ${alias}
    HostName ${hostname}
    User root
    ProxyJump pi-01
SSHEOF
  done

  chmod 600 "$config_file"
  log "SSH config written with ${#FLEET_HOSTS[@]} fleet hosts"
}

setup_tunnels() {
  log "Setting up SSH tunnel service..."
  local tunnel_script="$HOME/bin/fleet-tunnels.sh"
  mkdir -p "$HOME/bin"

  local tunnel_args=""
  for spec in "${TUNNEL_PORTS[@]}"; do
    local local_port="${spec%%:*}"
    local remote="${spec#*:}"
    tunnel_args+=" -L 0.0.0.0:${local_port}:${remote}"
  done

  run cat > "$tunnel_script" <<TUNEOF
#!/usr/bin/env bash
# Forward tunnels to aio-01 via pi-01
exec ssh -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \\
  ${tunnel_args} \\
  aio-01
TUNEOF
  run chmod +x "$tunnel_script"

  local service_file="$HOME/.config/systemd/user/fleet-tunnels.service"
  mkdir -p "$HOME/.config/systemd/user"
  run cat > "$service_file" <<SVCEOF
[Unit]
Description=SSH tunnels to aio-01 fleet services
After=network-online.target

[Service]
ExecStart=${tunnel_script}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SVCEOF

  if ! $DRY_RUN; then
    if systemctl --user status >/dev/null 2>&1; then
      systemctl --user daemon-reload
      systemctl --user enable fleet-tunnels.service
      systemctl --user start fleet-tunnels.service
      log "Tunnel service started"
    else
      log "WARNING: systemd user session not available — run ${tunnel_script} manually"
    fi
  fi
}

setup_reverse_tunnel() {
  log "Setting up reverse tunnel to aio-01..."
  local hostname
  hostname=$(hostname | tr -cd '[:alnum:]._-')
  local reverse_port

  reverse_port=$(ssh -o ConnectTimeout=5 aio-01 \
    "cat ~/.ssh/config | grep -A1 '${hostname}' | grep Port | awk '{print \$2}'" 2>/dev/null || echo "")

  if [[ -z "$reverse_port" ]]; then
    reverse_port=2224
    log "No existing reverse tunnel port found, using ${reverse_port}"
    run ssh -o ConnectTimeout=5 aio-01 "cat >> ~/.ssh/config <<EOF

Host ${hostname}
  HostName localhost
  Port ${reverse_port}
  User claude
EOF"
  fi

  local reverse_script="$HOME/bin/reverse-tunnel.sh"
  run cat > "$reverse_script" <<REVEOF
#!/usr/bin/env bash
exec ssh -N -R ${reverse_port}:localhost:22 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 aio-01
REVEOF
  run chmod +x "$reverse_script"

  local service_file="$HOME/.config/systemd/user/reverse-tunnel.service"
  run cat > "$service_file" <<SVCEOF
[Unit]
Description=Reverse SSH tunnel to aio-01
After=fleet-tunnels.service

[Service]
ExecStart=${reverse_script}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SVCEOF

  if ! $DRY_RUN; then
    if systemctl --user status >/dev/null 2>&1; then
      systemctl --user daemon-reload
      systemctl --user enable reverse-tunnel.service
      systemctl --user start reverse-tunnel.service
    else
      log "WARNING: systemd user session not available — run ${reverse_script} manually"
    fi
  fi
  log "Reverse tunnel configured on port ${reverse_port}"
}

pull_api_keys() {
  log "Pulling API keys from orchestrator..."

  if ! curl -s -m 5 "${API_BASE}/health" > /dev/null 2>&1; then
    log "ERROR: API not reachable at ${API_BASE}. Start tunnels first."
    return 1
  fi

  local keys_json
  keys_json=$(curl -s -m 10 "${API_BASE}/secrets/")
  if [[ -z "$keys_json" ]]; then
    log "ERROR: Empty response from secrets endpoint"
    return 1
  fi

  local key_names
  key_names=$(echo "$keys_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for s in d.get('secrets', []):
    if isinstance(s, dict):
        print(s.get('key', ''))
    else:
        print(s)
" 2>/dev/null)

  local keys_file="$HOME/.fleet-api-keys"
  run cat > "$keys_file" <<'KEYEOF'
# Fleet API Keys (auto-generated by bootstrap)
# Do not edit manually — re-run bootstrap to refresh
KEYEOF
  chmod 600 "$keys_file"

  local count=0
  while IFS= read -r key_name; do
    [[ -z "$key_name" ]] && continue
    case "$key_name" in
      GRAFANA_*|ORIENTDB_*|REDIS_*|SUMO_ENDPOINT|SUMO_GITOPS_*)
        continue ;;
    esac

    local value
    value=$(curl -s -m 5 "${API_BASE}/secrets/${key_name}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('value',''))" 2>/dev/null)
    if [[ -n "$value" ]]; then
      printf 'export %s=%q\n' "$key_name" "$value" >> "$keys_file"
      log "  Added ${key_name}"
      ((count++))
    else
      log "  WARNING: Failed to retrieve ${key_name}"
    fi
  done <<< "$key_names"

  local bashrc="$HOME/.bashrc"
  local source_line="[[ -f ~/.fleet-api-keys ]] && source ~/.fleet-api-keys"
  if ! grep -qF "$source_line" "$bashrc" 2>/dev/null; then
    echo "" >> "$bashrc"
    echo "$source_line" >> "$bashrc"
  fi

  log "${count} API keys written to ~/.fleet-api-keys (mode 600)"
}

install_tools() {
  log "Installing AI coding tools..."

  if ! command -v opencode &>/dev/null; then
    log "Installing OpenCode..."
    run bash -c 'curl -fsSL https://opencode.ai/install | bash'
  else
    log "OpenCode already installed"
  fi

  if ! command -v claude &>/dev/null; then
    log "Installing Claude Code..."
    run npm install -g @anthropic-ai/claude-code
  else
    log "Claude Code already installed"
  fi
}

generate_opencode_config() {
  log "Generating OpenCode configuration..."
  local config_dir="$HOME/.config/opencode"
  mkdir -p "$config_dir"

  local providers=""
  for entry in "${OPENCODE_PROVIDERS[@]}"; do
    local provider="${entry%%:*}"
    local key_var="${entry#*:}"
    [[ -n "$providers" ]] && providers+=","
    providers+="
    \"${provider}\": {
      \"options\": {
        \"apiKey\": \"{env:${key_var}}\"
      }
    }"
  done

  run cat > "${config_dir}/opencode.json" <<OCEOF
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4-5",
  "small_model": "groq/llama-4-scout-17b-16e-instruct",
  "provider": {${providers}
  }
}
OCEOF

  log "OpenCode config written to ${config_dir}/opencode.json"
}

generate_agents_md() {
  log "Generating AGENTS.md for OpenCode..."
  local config_dir="$HOME/.config/opencode"
  mkdir -p "$config_dir"

  if [[ -f "$HOME/.claude/CLAUDE.md" ]]; then
    run cp "$HOME/.claude/CLAUDE.md" "${config_dir}/AGENTS.md"
    log "Copied ~/.claude/CLAUDE.md → AGENTS.md"
  else
    run cat > "${config_dir}/AGENTS.md" <<'AGEOF'
# Distributed LLM Orchestration Framework

## Architecture
- API-only fleet: 8 workers + 1 controller (aio-01)
- 200+ free API models via OpenRouter, Anthropic, Google, Groq, Cerebras, DeepSeek
- Orchestrator REST API: http://localhost:5000 (via SSH tunnel to aio-01)

## Rules
- ALL database access via REST API :5000 — NEVER direct PostgreSQL :5433
- ALL queues use Redis, not PostgreSQL tables
- ALWAYS use fleet for reviews — never implement solo
- ALWAYS max parallelism — use ALL workers for independent tasks
- NEVER delete files without asking
- Red Hat internal code: Claude/Anthropic ONLY, never third-party LLMs
- Embeddings run ONLY on laptops, never on fleet workers

## Key Endpoints
- GET  /health — Service health
- GET  /secrets/KEY — API key retrieval
- GET  /search/intelligent?q=X — Multi-source search
- POST /learning/memory — Store memory
- GET  /fleet/status — Fleet worker status
- POST /graph/query — OrientDB graph queries
AGEOF
    log "Generated default AGENTS.md"
  fi
}

clone_repo() {
  log "Cloning main repository..."
  local repo_dir="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"

  if [[ -d "$repo_dir/.git" ]]; then
    log "Repo already exists at ${repo_dir}, pulling latest"
    run git -C "$repo_dir" pull
  else
    mkdir -p "$(dirname "$repo_dir")"
    run git clone "$REPO_URL" "$repo_dir"
  fi
}

sync_knowledge() {
  log "Syncing knowledge from orchestrator..."

  if ! curl -s -m 5 "${API_BASE}/health" > /dev/null 2>&1; then
    log "WARNING: API not reachable, skipping knowledge sync"
    return 0
  fi

  local memory_dir
  memory_dir="$HOME/.claude/projects/-home-$(whoami)-Development-redhat-scm-gitlab-cee-sfloess-claude-global-skills/memory"
  mkdir -p "$memory_dir"

  local memories
  memories=$(curl -s -m 10 "${API_BASE}/learning/memory" 2>/dev/null)

  if [[ -n "$memories" ]] && echo "$memories" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    echo "$memories" | python3 -c "
import sys, json, os

data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('memories', data.get('items', []))
out_dir = sys.argv[1]
count = 0

for item in items:
    if not isinstance(item, dict):
        continue
    name = item.get('name', f'memory_{count}')
    content = item.get('content', '')
    mem_type = item.get('memory_type', item.get('type', 'reference'))
    desc = item.get('description', '')

    filename = f'{mem_type}_{name}.md'.replace('/', '_').replace(' ', '_')
    filepath = os.path.join(out_dir, filename)

    with open(filepath, 'w') as f:
        f.write(f'---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: {mem_type}\n---\n\n{content}\n')
    count += 1

print(f'Synced {count} memories')
" "$memory_dir"
  else
    log "No memories to sync or API returned invalid response"
  fi
}

setup_embedding_service() {
  log "Setting up embedding service..."

  if python3 -c "import sentence_transformers" 2>/dev/null; then
    log "sentence-transformers already installed"
  else
    run pip3 install --user sentence-transformers
  fi

  local embed_script="$HOME/bin/embed-service.sh"
  run cat > "$embed_script" <<'EMBEDEOF'
#!/usr/bin/env bash
exec python3 -m sentence_transformers.server --model all-mpnet-base-v2 --port 8101
EMBEDEOF
  run chmod +x "$embed_script"
  log "Embedding service script created at ${embed_script}"
}

create_claude_user() {
  log "Checking claude user..."
  if id claude &>/dev/null; then
    log "claude user already exists"
  else
    log "Creating claude user with UID ${CLAUDE_UID}..."
    run sudo useradd -u "$CLAUDE_UID" -m -s /bin/bash claude
    run sudo mkdir -p /home/claude/.ssh
    run sudo ssh-keygen -t ed25519 -f /home/claude/.ssh/id_ed25519 -N "" -q
    run sudo chown -R claude:claude /home/claude/.ssh
    log "claude user created — distribute public key to fleet"
  fi
}

SKIP_TOOLS=false
SKIP_REPO=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=true ;;
    --verbose)    VERBOSE=true ;;
    --skip-tools) SKIP_TOOLS=true ;;
    --skip-repo)  SKIP_REPO=true ;;
    --help)       usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
  shift
done

main() {
  log "=== Fleet Machine Bootstrap ==="
  log "Hostname: $(hostname)"
  log "Dry run: ${DRY_RUN}"

  setup_ssh_config
  setup_tunnels
  sleep 3

  pull_api_keys
  source "$HOME/.bashrc" 2>/dev/null || true

  if ! $SKIP_TOOLS; then
    install_tools
  fi

  generate_opencode_config
  generate_agents_md

  if ! $SKIP_REPO; then
    clone_repo
  fi

  sync_knowledge
  create_claude_user
  setup_embedding_service
  setup_reverse_tunnel

  log "=== Bootstrap Complete ==="
  log "Next steps:"
  log "  1. source ~/.bashrc"
  log "  2. Verify: curl http://localhost:5000/health"
  log "  3. Test: opencode (or claude)"
  log "  4. Distribute claude user SSH key to fleet workers"
}

main
