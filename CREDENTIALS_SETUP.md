# Credentials Setup Guide

Credentials (API tokens, API keys) are auto-loaded in all Claude sessions—new, resumed, and tool execution.

## Store Credentials

**File:** `~/.FlossWare/secrets.env`

```bash
export GITLAB_TOKEN='your-gitlab-token'
export GOOGLE_API_KEY='your-google-key'
export JIRA_API_TOKEN='your-jira-token'
export SONAR_TOKEN='your-sonarqube-token'
export CURSOR_API_KEY='your-cursor-key'
```

**Permissions:** `chmod 600 ~/.FlossWare/secrets.env` (do not commit to git)

## How Auto-Loading Works

### 1. Shell Startup (New Sessions)
- `~/.bashrc` and `~/.zshrc` source `~/.FlossWare/secrets.env` with `set -a` (auto-export)
- All variables become available immediately

### 2. Non-Interactive Bash (Claude Tools)
- `BASH_ENV` is set to `~/.bashenv`
- Bash automatically sources `~/.bashenv` for non-interactive shells (like Claude's tool execution)
- `~/.bashenv` sources `~/.FlossWare/secrets.env` with `set -a`

### 3. Resumed Sessions
- **Option A (Automatic):** Session hook (`~/.claude/hooks/user-prompt-submit.sh`) reloads credentials on every prompt
- **Option B (Manual):** User can call `source ~/.FlossWare/secrets.env` anytime

## Setup Steps

### 1. Create credentials file
```bash
mkdir -p ~/.FlossWare
cat > ~/.FlossWare/secrets.env << 'EOF'
export GITLAB_TOKEN='your-token'
export GOOGLE_API_KEY='your-key'
# ... add all your credentials
EOF
chmod 600 ~/.FlossWare/secrets.env
```

### 2. Enable shell auto-loading (already done in .bashrc/.zshrc)
```bash
# These are already in ~/.bashrc and ~/.zshrc:
export BASH_ENV="$HOME/.bashenv"

if [ -f ~/.FlossWare/secrets.env ]; then
  set -a
  . ~/.FlossWare/secrets.env
  set +a
fi
```

### 3. Create ~/.bashenv (already done)
```bash
cat > ~/.bashenv << 'EOF'
#!/bin/bash
if [ -f ~/.FlossWare/secrets.env ]; then
  set -a
  . ~/.FlossWare/secrets.env
  set +a
fi
EOF
chmod 600 ~/.bashenv
```

## Verification

Test that credentials are available:

```bash
# In your shell
echo $GITLAB_TOKEN

# Via Claude tools
# Claude will run: bash -c 'echo $GITLAB_TOKEN'
# Should show actual token value, not ${GITLAB_TOKEN}
```

## How It Works

### `set -a` / `set +a`
- `set -a`: Auto-export all variable assignments
- Loads secrets.env so all `export VAR=value` become available in the environment
- `set +a`: Turn off auto-export

### BASH_ENV
- Environment variable that bash reads for non-interactive shells
- Claude runs tools via `bash -c`, which is non-interactive
- Without BASH_ENV, the non-interactive bash wouldn't read `.bashrc`
- With BASH_ENV, bash sources `~/.bashenv` which has the credentials

### Why This Design
1. **Single source of truth:** `~/.FlossWare/secrets.env` contains all credentials
2. **Automatic propagation:** Credentials load in all contexts (shell, tools, resumed sessions)
3. **No duplication:** Shared `.bashenv` used by all shell types
4. **Security:** Credentials file kept out of git, proper permissions (600)

## Troubleshooting

### Credentials not available in shell
```bash
# Check if file exists and is readable
cat ~/.FlossWare/secrets.env | head -3

# Check if BASH_ENV is set
echo $BASH_ENV

# Manually source to test
source ~/.FlossWare/secrets.env && echo $GITLAB_TOKEN
```

### Credentials not available in Claude tools
1. Restart Claude session (forces re-read of hooks)
2. Verify `~/.bashenv` exists: `cat ~/.bashenv`
3. Verify `BASH_ENV` in `.bashrc`: `grep BASH_ENV ~/.bashrc`
4. Test directly: `bash -c 'echo $GITLAB_TOKEN'` should show token value

### Token still shows as `${GITLAB_TOKEN}`
- This means the variable wasn't exported
- Check that `set -a` is in place before sourcing
- Verify secrets.env has `export VARIABLE=value` (not just `VARIABLE=value`)

## Multi-Machine Setup

If running Claude sessions on **different machines**:
1. Create `~/.FlossWare/secrets.env` on each machine
2. Each machine reads from its local secrets file
3. To sync tokens across machines, use git (ignored via `.gitignore`)

## Performance Notes

**Cache TTL Configuration:** For cost optimization, see **`caching/README.md`** for how to enable 6-hour cache TTL (~$500/month savings). Default is conservative 5 minutes for freshness.

## See Also

- `CLAUDE.ENSEMBLE.md` — Main guide
- `scripts/ensemble-init.sh` — Initialization script (loads credentials)
- `~/.claude/hooks/user-prompt-submit.sh` — Session hook (re-loads on resumed sessions)
- `caching/README.md` — Cache TTL configuration and cost optimization
