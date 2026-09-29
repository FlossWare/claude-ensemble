# Claude Ensemble

**Complete, production-ready multi-AI orchestration toolkit.**

Claude Ensemble is a portable toolkit for orchestrating multiple AI models and Claude Code workflows. It combines model routing, multi-phase arbitration, autonomous outcome learning, cost tracking, compression, caching, and reusable workflow skills.

It is designed to work both in Red Hat-centric environments and as a standalone personal or open-source toolkit. Runtime paths, credentials, service sockets, and repository locations are configurable rather than hard-coded.

---

## What's Inside

### Core Infrastructure
- **Memory Service** — Concurrent-safe shared state across Claude Ensemble sessions
- **Thompson Service** — Bayesian model selection based on observed task performance
- **Learning Service** — Records task outcomes and feeds learning back into routing
- **Alert Service** — Detects configured anomalies such as cost/quality changes and delivers alerts
- **Messenger Service** — Topic-based pub/sub for commands and communication between concurrent sessions
- **Arbitration Orchestrator** — Multi-phase worker/arbiter pattern for critical decisions

### Optimization & Analysis
- **GA Tuning** — Genetic algorithm optimization every 4 hours (synthetic, zero cost)
- **Model Discovery** — Probes Anthropic/Google/Cursor APIs every 4 hours for latest models
- **Cost Tracking** — JSONL audit log of all API usage
- **5 Dashboards** — Cost, Thompson routing, autonomous learning, GA tuning, performance

### Workflow Skills (Learning-Integrated)
- **Code PR Review** (`code-pr-review`) — AI consensus code review, Thompson-routed model selection
- **Documentation** (`code-doc`) — Auto-generate docs, learns which models write better
- **Release Notes** (`code-release-notes`) — Generate from commits with multi-AI consensus
- **Autonomous Variants** (`code-pr-review-auto`, `code-doc-auto`) — Run without user confirmation

All skills feed outcomes into Thompson — models learn task-specific performance over time.

### Capabilities  
- **Compression** — 64.6% token reduction via recursive text compression
- **Caching** — Prompt caching framework with hit/miss tracking (Phase 1 ready)
- **Hooks** — Memory search on prompt submit, learning extraction
- **Memory** — Project memory files (feedback, projects, references)

---

## Quick Start

### Installation

```bash
curl -fsSL https://raw.githubusercontent.com/FlossWare/claude-ensemble/main/install.sh | bash
```

This will:
1. Clone the repository
2. Create symlinks in `~/.claude/`
3. Set up credentials storage at `~/.FlossWare/secrets.env`
4. Prompt you to configure which tools to enable

**See [CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md)** for how to configure API tokens and credentials (auto-loaded in all sessions).

### Session Initialization
On startup, `scripts/ensemble-init.sh` automatically:
1. Connects to memory service (systemd daemon)
2. Initializes autonomous learning
3. Discovers latest models (Claude 5, Gemini, Cursor)
4. Prints toolkit status

```bash
✓ Connected to memory service
✓ Autonomous learner ready
✓ Claude Ensemble Toolkit initialized
  Tools: compression, caching, cost_tracking, ga_tuning, thompson_router, arbitration
  Memory: ~/.claude/projects/memory
  Arbitration: multi-phase orchestrator for critical decisions
  Autonomous learning: Thompson continuously improving from real tasks
```

### Run Dashboards
After doing real work, view your performance:

```bash
cost-dashboard.py              # Spending by model/provider/workflow/day
thompson-dashboard.py          # Routing accuracy, model rankings, quality
autonomous-learning-dashboard.py  # Learning progress, outcomes
ga-tuning-dashboard.py         # Fitness trends, parameter evolution
```

### Workflow Skills
For routine tasks with learning integration:

```bash
# Interactive PR review (asks before approve/reject)
/code-pr-review

# Autonomous PR review (auto-approves/rejects)
/code-pr-review-auto

# Interactive documentation generation
/code-doc

# Autonomous doc generation
/code-doc-auto

# Generate release notes from commits
/code-release-notes
```

See **[SKILL_INTEGRATION_GUIDE.md](SKILL_INTEGRATION_GUIDE.md)** for full details on how skills learn and route models via Thompson.

### Multi-Phase Arbitration
For critical decisions (security, breaking changes, complex bugs):

```bash
arbitrate code-review /path/to/repo --phases 3 --context-dir src/api
arbitrate bug-analysis error.log code.py --phases 2
arbitrate security-audit src/ --phases 3
```

Workers solve independently. Arbiter synthesizes. No model repeats across phases.

---

## Architecture

### Memory Service
- **Path:** `memory-service/`
- **Linux:** Optional systemd user service
- **Windows:** `ClaudeEnsembleMemory` under Windows SCM
- **Endpoint:** Per-user Unix socket on Linux; service-managed local IPC on Windows
- **Function:** Thread-safe access to shared memory across concurrent sessions

### Thompson Service
- **Path:** `thompson-service/`
- **Linux:** Optional systemd user service
- **Windows:** `ClaudeEnsembleThompson` under Windows SCM
- **Endpoint:** Per-user Unix socket on Linux; service-managed local IPC on Windows
- **Function:** Bayesian model selection based on historical task outcomes

### Learning Service
- **Path:** `learning-service/`
- **Linux:** Optional systemd user service
- **Windows:** `ClaudeEnsembleLearning` under Windows SCM
- **Dependency:** Thompson
- **Endpoint:** Per-user Unix socket on Linux; service-managed local IPC on Windows
- **Function:** Records task outcomes, evaluates results, and updates learning state used by Thompson

### Alert Service
- **Path:** `alert_service/`
- **Linux:** Optional systemd user service
- **Windows:** `ClaudeEnsembleAlert` under Windows SCM
- **Dependency:** Learning
- **Endpoint:** Per-user Unix socket on Linux; service-managed local IPC on Windows
- **Function:** Monitors configured repository/service signals and delivers anomaly or operational alerts

### Messenger Service
- **Path:** `session-messaging/`
- **Linux:** Optional systemd user service
- **Windows:** `ClaudeEnsembleMessenger` under Windows SCM
- **Endpoint:** AF_UNIX socket on Linux; authenticated named pipe `\\.\pipe\ClaudeEnsembleMessenger` on Windows
- **Function:** Topic-based pub/sub for communication between concurrent Claude Ensemble sessions
- **Windows authentication:** Installation-generated key under `%PROGRAMDATA%\ClaudeEnsemble\run\messenger.key`

### Thompson Router
- **Path:** `shared/thompson_router.py`
- **Models:** Haiku (cheap), Sonnet (balanced), Opus (capable), Cursor, Gemini
- **Algorithm:** Bayesian inference with Beta distributions
- **Cost Savings:** 67% vs Opus-for-all (tested)

### Autonomous Learning
- **Path:** `learning/autonomous_learning.py`, `tools/autonomous-learner.py`
- **Workers:** 4 independent models capture outcomes, score, update priors, tune capability matrix
- **Trigger:** After every real task (online learning)
- **Storage:** `learning/autonomous_outcomes/`, `learning/autonomous_priors/`

### Arbitration Orchestrator
- **Path:** `arbitration/`
- **Guarantees:** 
  - No model is both arbiter and worker in same run
  - Workers in different phases are different models
  - Arbiters all different from each other
  - Each phase receives prior arbiter output
- **Context Access:** Git diffs, full files, dependencies, module context

### GA Tuning
- **Path:** `ga_tuning/`
- **Frequency:** Every 4 hours (0, 4, 8, 12, 16, 20 UTC)
- **Evaluators:** 5 independent (compression, Thompson, caching, capability matrix, learning rate)
- **Cost:** Zero (synthetic tasks, no API calls)
- **Parameters:** Tuned automatically, logged to `ga_tuning/parameter_evolution.md`

### Model Discovery
- **Path:** `tools/discover-models.py`
- **Frequency:** Every 4 hours (synced with GA tuning)
- **Providers:** Anthropic (free API call), Google (free API call), Cursor (defaults to latest)
- **Updates:** Thompson router inline, settings.json with discovery timestamp

---

## Dashboards

All dashboards read from local JSON files (no database):

| Dashboard | Command | Shows |
|-----------|---------|-------|
| Cost | `cost-dashboard.py` | Spending by model, provider, workflow, day |
| Thompson | `thompson-dashboard.py` | Routing accuracy, model rankings, quality achieved |
| Autonomous Learning | `autonomous-learning-dashboard.py` | Learning outcomes, prior updates, latest feedback |
| GA Tuning | `ga-tuning-dashboard.py` | Fitness progression, parameter evolution per evaluator |
| Performance | `performance_dashboard.py` | Real-time metrics (overlaps with cost dashboard) |

---

## Directory Structure

```
scripts/
  ensemble-init.sh            # Session initialization
  config.sh                   # Interactive tool configuration
  ga-tuning-schedule.sh       # Cron: GA every 4 hours

memory-service/
  memory_service.py           # Systemd daemon
  memory_client.py            # Session client
  rh-memory.service           # Systemd unit file
  install.sh                  # Install script

arbitration/
  orchestrator.py             # Multi-phase runner, context manager
  api_client.py               # Multi-model API client

learning/
  autonomous_learning.py      # Full system (4 workers)
  autonomous_outcomes/        # Task outcome records
  autonomous_priors/          # Bayesian prior updates

shared/
  thompson_router.py          # Model selection

tools/
  arbitrate.py                # CLI tool
  autonomous-learner.py       # Wrapper for autonomous learning
  code-pr-review.js           # Code review skill
  code-doc.js                 # Documentation skill
  code-release-notes.js       # Release notes skill
  cost-dashboard.py           # Cost viewer
  discover-models.py          # Model discovery
  thompson-dashboard.py       # Thompson performance viewer
  autonomous-learning-dashboard.py  # Learning progress viewer
  ga-tuning-dashboard.py      # GA progress viewer

ga_tuning/
  ga_tuner.py                 # GA optimizer
  extract_and_apply_parameters.py  # Extract & update settings
  evaluators/                 # 5 independent evaluators
  parameter_evolution.md      # Timestamped parameter changes
  results/                    # GA output (JSON)

compression/
  compression_api.py          # 64.6% reduction
  summarizer.py               # Text compression

caching/
  memory_cache_integration.py # Cache manager
  cache_metrics.py            # Hit/miss tracking

cost_tracking/
  logger.py                   # JSONL cost log
  aggregator.py               # Cost aggregation

hooks/
  memory-search-on-prompt.js  # TF-IDF + RRF semantic search

memory/
  MEMORY.md                   # Index (loaded at session start)
  feedback_*.md               # User preferences
  project_*.md                # Project context
```

---

## Portable / Standalone Mode

Claude Ensemble does not require the Red Hat workstation layout. Runtime paths can be
configured with environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `ENSEMBLE_ROOT` | Repository root used by shell initialization | Repository containing `scripts/ensemble-init.sh` |
| `ENSEMBLE_CREDENTIALS_FILE` | Optional credentials file | `~/.FlossWare/secrets.env` |
| `ENSEMBLE_MEMORY_DIR` | Persistent memory directory | `~/.claude/projects/memory` |
| `ENSEMBLE_LOG_DIR` | Service log directory | `~/.claude` |
| `ENSEMBLE_RUNTIME_DIR` | Runtime directory for configurable service sockets | XDG runtime/cache location |
| `ENSEMBLE_REPO_ROOT` | Repository inspected by alerting | Current working directory |
| `ENSEMBLE_LEARNING_DIR` | Learning state directory | Existing Claude Ensemble learning path |
| `ENSEMBLE_ALERT_DIR` | Alert state directory | `~/.claude/alerts` |
| `ENSEMBLE_*_SOCKET` | Per-service Unix socket override | Existing service socket |

For a standalone installation, services are optional. The memory client already degrades
gracefully when its daemon is unavailable, and the learning/Thompson/alert services can
be run only when their corresponding features are needed. No Red Hat GitLab host,
credential file, or repository path is required by the core runtime.

Example:

```bash
export ENSEMBLE_ROOT="$HOME/src/claude-ensemble"
export ENSEMBLE_MEMORY_DIR="$HOME/.local/share/claude-ensemble/memory"
export ENSEMBLE_LOG_DIR="$HOME/.local/state/claude-ensemble"
export ENSEMBLE_REPO_ROOT="$HOME/src/my-project"
```

On systems without systemd, use the CLI tools and standalone components directly rather
than installing the optional user services.

---

## Configuration

**Settings:** `settings.json.default` (copy to `~/.claude/settings.json` to customize)

**Credentials:** `~/.FlossWare/secrets.env` or environment variables
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
- CURSOR_API_KEY
- Custom keys for any MCP servers you configure

**MCP Servers:** `~/.mcp.json` (configure as needed)

### Secrets and GitHub Actions

Claude Ensemble uses different credential mechanisms for local development and GitHub Actions. **Never commit API keys, tokens, passwords, or other secrets to the repository.**

#### Local credentials

For local installations, credentials can be stored in:

```text
~/.FlossWare/secrets.env
```

The installer creates this location, and Claude Ensemble loads the configured credentials for local sessions. You can also provide supported credentials as environment variables.

##### Windows PowerShell

For the current PowerShell session:

```powershell
$env:ANTHROPIC_API_KEY = "..."
$env:GOOGLE_API_KEY = "..."
$env:CURSOR_API_KEY = "..."
```

For a persistent **user** environment variable:

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "...", "User")
[Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "...", "User")
[Environment]::SetEnvironmentVariable("CURSOR_API_KEY", "...", "User")
```

Open a new PowerShell session after changing persistent environment variables so the new values are inherited.

##### Windows Command Prompt

For the current Command Prompt session:

```cmd
set ANTHROPIC_API_KEY=...
set GOOGLE_API_KEY=...
set CURSOR_API_KEY=...
```

##### Windows Git Bash / MSYS2

Git Bash and MSYS2 can use the normal shell form:

```bash
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."
export CURSOR_API_KEY="..."
```

Keep `~/.FlossWare/secrets.env` outside source control. Do not add real credentials to `settings.json`, workflow files, documentation, or test fixtures.

##### Windows services and service accounts

Windows SCM services do **not** necessarily run as the same account as the interactive user. A credential configured only in your interactive user's environment may therefore be invisible to a Claude Ensemble service.

If a Windows service needs an API credential, configure that credential for the service account or through the service's supported environment/configuration mechanism. Do not put the credential in `windows/install.ps1`, commit it to the repository, or place it in the Messenger authentication-key file.

For a service running under a dedicated account, prefer a dedicated credential with only the permissions that service needs. If you change environment variables used by an installed service, restart the service so it receives the updated environment.

The Windows Messenger service is different: its local authentication key is generated and managed by the Windows installer under `%PROGRAMDATA%\\ClaudeEnsemble\\run\\messenger.key`. Users should not create or copy that key manually.

#### GitHub Actions repository secrets

CI/CD credentials belong in GitHub repository secrets rather than in workflow files.

For this repository:

1. Open the **[Claude Ensemble repository](https://github.com/FlossWare/claude-ensemble)** on GitHub.
2. Select **Settings**.
3. Select **Secrets and variables → Actions**.
4. Select **New repository secret**.
5. Enter the exact secret name expected by the workflow.
6. Paste the secret value into the **Secret** field.
7. Select **Add secret**.

A workflow references a repository secret with:

```yaml
env:
  API_KEY: ${{ secrets.API_KEY }}
```

or directly in a step:

```yaml
- name: Run authenticated task
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: python tools/example.py
```

Do not print a secret to workflow logs. To verify that a required secret is configured, test only whether it is non-empty:

```yaml
- name: Verify required secret is configured
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: |
    if [ -z "$API_KEY" ]; then
      echo "Required secret API_KEY is not configured"
      exit 1
    fi
    echo "Required secret is configured"
```

#### Choosing the right GitHub secret scope

- **Repository secrets** are appropriate when a secret is used by workflows across the repository.
- **Environment secrets** are appropriate when a secret should only be available to jobs targeting a specific GitHub Actions environment.
- **Organization secrets** are appropriate when the same credential is intentionally shared across multiple repositories.

Use the narrowest scope that satisfies the workflow.

#### Pull requests from forks

GitHub does not normally expose repository secrets to workflows triggered by pull requests from forks. Workflows must not require contributors to expose secrets merely to run ordinary validation.

For security-sensitive or authenticated integration tests, prefer trusted workflows and explicit GitHub Actions environments rather than weakening secret protections.

#### Secrets used by this repository

The authoritative list of credentials required by each workflow is the workflow itself. Search `.github/workflows/` for expressions of the form:

```text
${{ secrets.SECRET_NAME }}
```

and configure only the secrets actually required by the corresponding workflow.

For application/API credentials used outside CI, see **[CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md)**.


---

## Cost Optimization Stack

Three complementary techniques:

1. **Thompson Router** (67% savings) — Route to cheapest capable model
2. **Compression** (64.6% reduction) — Token reduction via text compression
3. **Caching** (69.8% savings) — Reuse frequent prompts

**Combined:** Can exceed 90% savings on token-heavy workflows.

---

## Future Work

See GitHub issues:
- Arbiter explanations + teaching signals (tabled, needs neural-ai research)
- Consolidate cost tracking dashboards

---

## Documentation

**Core Guides:**
- **`CLAUDE.ENSEMBLE.md`** — Best practices and coding standards
- **`MEMORY_SYSTEM.md`** — Memory persistence, search, analysis (NEW)
- **`REVIEW_SHORTHAND.md`** — Quick commands for code reviews (NEW)
- **`SKILL_INTEGRATION_GUIDE.md`** — How workflow skills work
- **`MODEL_REGISTRY.md`** — Available models and capabilities

**Component Docs:**
- **`SERVICES_GUIDE.md`** — Cross-platform service operations (Linux systemd and Windows SCM; memory, thompson, learning, alert, messenger)
- **`TOOLS_INTEGRATION_GUIDE.md`** — Thompson router, GA tuning, learning system
- **`cost_tracking/`** — Cost logging and aggregation
- **`ga_tuning/`** — Genetic algorithm parameter optimization
- **`learning/`** — Autonomous learning system details
- **Individual `README.md`** in each service directory

---

**Last updated:** 2026-09-29  
**Status:** Production-ready, all tools active  
**License:** See `LICENSE`  
**Contributors:** Generated with Claude Ensemble


## Linux: Native Installation and Daily Use

Claude Ensemble runs natively on Linux. The supported service deployment model is **systemd user services**, which keeps the daemons scoped to the logged-in user rather than requiring system-wide root services. Direct execution is also supported on systems without systemd.

### What gets installed

Claude Ensemble has five optional background services:

| Service | systemd unit | Purpose | Dependency |
|---|---|---|---|
| Memory | `claude-memory.service` | Shared, concurrency-safe session memory | None |
| Thompson | `claude-thompson.service` | Selects models using Bayesian performance history | None |
| Learning | `claude-learning.service` | Records outcomes and updates learning state | Thompson |
| Alert | `claude-alert.service` | Detects configured operational anomalies and sends alerts | Learning |
| Messenger | `claude-messenger.service` | Inter-session topic/pub/sub messaging | None |

Memory and Messenger are independent. Learning starts after Thompson, and Alert starts after Learning.

### One-command service installation

Each service has an `install.sh` installer. To install all five services:

```bash
for svc in memory-service thompson-service learning-service alert_service session-messaging; do
  (cd "$svc" && ./install.sh)
done
```

Each installer creates the systemd user unit, reloads the user manager, enables the service for login, and starts it.

If you only need one service, install it from its directory:

```bash
cd memory-service
./install.sh
```

### Managing the services

Check status:

```bash
systemctl --user status claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

Start all services:

```bash
systemctl --user start claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

Stop all services:

```bash
systemctl --user stop claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

Restart all services:

```bash
systemctl --user restart claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

Enable services at login:

```bash
systemctl --user enable claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

Disable automatic startup:

```bash
systemctl --user disable claude-memory.service claude-thompson.service claude-learning.service claude-alert.service claude-messenger.service
```

For a single service, use the same commands with only its unit name, for example:

```bash
systemctl --user restart claude-thompson.service
systemctl --user status claude-thompson.service
```

### Linux Messenger

Linux Messenger uses an AF_UNIX socket. Its default runtime location is derived from the user runtime/cache environment and can be overridden with the Messenger socket environment setting.

The normal user service and interactive Claude Ensemble sessions run in the same user context, so the default per-user IPC location is shared. Do not replace the socket with a TCP listener just to make local messaging convenient.

### Logs and diagnostics

Follow all user-service logs:

```bash
journalctl --user -f
```

Follow one service:

```bash
journalctl --user-unit claude-thompson.service -f
journalctl --user-unit claude-learning.service -f
journalctl --user-unit claude-alert.service -f
journalctl --user-unit claude-messenger.service -f
```

Inspect the units and recent failures:

```bash
systemctl --user list-units --type=service
systemctl --user status claude-*.service
journalctl --user-unit claude-thompson.service -n 50 --no-pager
```

Check the runtime sockets:

```bash
ls -la "$XDG_RUNTIME_DIR/claude-ensemble/" 2>/dev/null || ls -la ~/.cache/claude-ensemble/
ls -la "$XDG_RUNTIME_DIR/claude-messenger/" 2>/dev/null || true
```

### Troubleshooting

If a service fails to start, inspect its journal first:

```bash
journalctl --user-unit claude-SERVICENAME.service -n 50 --no-pager
systemctl --user restart claude-SERVICENAME.service
```

After changing a unit file, reload the user manager:

```bash
systemctl --user daemon-reload
```

If a stale Unix socket remains, stop the affected service, remove only the stale socket, and start the service again. Avoid broad deletion of runtime directories because other Claude Ensemble services may be using them.

### Direct execution without systemd

systemd is the normal Linux service host, but it is not a requirement for the application daemons. For development, debugging, containers, minimal distributions, or other environments without a user systemd manager, launch the service implementations directly.

For example:

```bash
python3 memory-service/memory_service.py
python3 thompson-service/thompson_service.py
python3 learning-service/learning_service.py
python3 alert_service/alert_service.py
python3 session-messaging/messenger_service.py
```

Direct execution does not provide systemd's enablement, restart, dependency ordering, or journal management. Those are properties of the service host, not the application implementations.

### Linux without systemd

If the host has no systemd user manager, use the direct service commands above or another process supervisor appropriate to that environment. The core runtime does not require a Red Hat workstation layout, system-wide root service, or a particular Linux distribution.

### Service documentation

For architecture, socket details, diagnostics, and per-service installation behavior, see **[SERVICES_GUIDE.md](SERVICES_GUIDE.md)** and the individual service READMEs.


## Windows: Native Installation and Daily Use

Claude Ensemble runs natively on Windows. **WSL is not required, Git Bash/MSYS2 is supported for direct execution, and systemd is not required.** For a normal Windows deployment, use the Windows Service Control Manager (SCM).

### What gets installed

Claude Ensemble has **five background services**:

| Service | Windows SCM name | Purpose | Dependency |
|---|---|---|---|
| Memory | `ClaudeEnsembleMemory` | Shared, concurrency-safe session memory | None |
| Thompson | `ClaudeEnsembleThompson` | Selects models using Bayesian performance history | None |
| Learning | `ClaudeEnsembleLearning` | Records outcomes and updates learning state | Thompson |
| Alert | `ClaudeEnsembleAlert` | Detects configured operational anomalies and sends alerts | Learning |
| Messenger | `ClaudeEnsembleMessenger` | Inter-session topic/pub-sub messaging | None |

**Memory and Messenger are independent.** Learning starts after Thompson, and Alert starts after Learning.

These are the application daemons. Windows SCM is only the service host and lifecycle manager. The same Python service implementations remain the application layer.

### One-command Windows installation

1. Install a normal supported Python installation and ensure `python` is on PATH.
2. Clone this repository.
3. Open **PowerShell as Administrator**.
4. Run:

```powershell
cd C:\path\to\claude-ensemble
.\windows\install.ps1
```

The installer:

1. Installs the Windows dependency (`pywin32`).
2. Prompts for the Windows account that will run the services.
3. Creates `%PROGRAMDATA%\ClaudeEnsemble\run`.
4. Restricts that directory to the selected service account, SYSTEM, and local Administrators.
5. Generates the Messenger authentication key if one does not already exist.
6. Configures the Messenger endpoint and authentication key as machine-level settings.
7. Registers all five services with Windows SCM.
8. Configures Learning → Thompson and Alert → Learning dependencies.
9. Configures automatic recovery for failed services.
10. Starts the services.

When it finishes, verify:

```powershell
Get-Service ClaudeEnsemble*
```

You should see all five services.

### Windows Messenger

Users do **not** configure a socket path or copy a key.

Windows Messenger uses the fixed local named pipe:

```text
\\.\pipe\ClaudeEnsembleMessenger
```

The authentication key is stored at:

```text
%PROGRAMDATA%\ClaudeEnsemble\run\messenger.key
```

Both the SCM-hosted Messenger service and interactive Claude Ensemble clients use this same endpoint. The implementation deliberately does not derive the Windows endpoint from `Path.home()`, because Windows service profiles and interactive user profiles are not a reliable shared IPC location.

There is no TCP fallback. Linux continues to use AF_UNIX.

### Managing the services

Check status:

```powershell
Get-Service ClaudeEnsemble*
```

Start a service:

```powershell
Start-Service ClaudeEnsembleMemory
```

Stop a service:

```powershell
Stop-Service ClaudeEnsembleMemory
```

Restart a service:

```powershell
Restart-Service ClaudeEnsembleMemory
```

Or manage the complete service set with:

```powershell
python windows\claude_ensemble_service.py start
python windows\claude_ensemble_service.py stop
```

For a service-specific view:

```powershell
Get-Service ClaudeEnsembleMemory,ClaudeEnsembleThompson,ClaudeEnsembleLearning,ClaudeEnsembleAlert,ClaudeEnsembleMessenger
```

### Logs and diagnostics

Windows SCM lifecycle events are written to the Windows Event Log. Child-process stdout/stderr is captured under:

```text
%PROGRAMDATA%\ClaudeEnsemble\logs
```

The application services also retain their normal Claude Ensemble logging.

Useful checks:

```powershell
Get-Service ClaudeEnsemble*
Get-ChildItem "$env:ProgramData\ClaudeEnsemble\logs"
```

### Direct execution on Windows

The SCM layer is optional.

For development, debugging, or environments where service installation is inappropriate, the Python daemons can be launched directly from:

- PowerShell
- Command Prompt
- Git Bash / MSYS2
- Other supported Windows shells

For example:

```powershell
python session-messaging\messenger_service.py
```

Direct execution does not require WSL or systemd.

### Uninstall

From an elevated PowerShell prompt:

```powershell
.\windows\uninstall.ps1
```

This removes the Windows SCM services and clears the machine-level Messenger configuration and generated authentication key.

### Security notes

- Service installation requires Administrator elevation because SCM registration and machine-level configuration are administrative operations.
- Run the services under a dedicated non-administrative account where practical.
- The installer prompts for the service-account password rather than storing it in source control.
- The Messenger authentication key is generated locally and is not committed to the repository.
- Do not manually publish or copy the Messenger authentication key.

### Windows support files

- `windows/install.ps1` — elevated installer
- `windows/uninstall.ps1` — service removal
- `windows/claude_ensemble_service.py` — SCM service host and lifecycle management
- `windows/test_windows_service.py` — Windows service and Messenger integration tests
- `requirements-windows.txt` — Windows-only dependency set
- `windows/README.md` — detailed Windows service reference
- `SERVICES_GUIDE.md` — cross-platform service reference

For the Linux/systemd service model, see the **[Linux: Native Installation and Daily Use](#linux-native-installation-and-daily-use)** section above and `SERVICES_GUIDE.md`.
