# Model Maintenance System

Automatically keeps the `api_models` PostgreSQL table up-to-date with provider APIs.

## Features

- **Auto-discovers new models** from provider APIs
- **Flags deprecated models** no longer in provider lists
- **Auto-assigns tiers** based on model name patterns
- **Runs daily** via systemd timer (3 AM)
- **Logs to journald** for monitoring

## Usage

### Manual run (interactive):
```bash
ssh root@aio-01
cd /mnt/aio-01/claude-orchestrator/scripts
python3 maintain-models.py
```

### Check only (no changes):
```bash
python3 maintain-models.py --check
```

### Auto-approve changes:
```bash
python3 maintain-models.py --auto
```

### View timer status:
```bash
systemctl status model-maintenance.timer
journalctl -u model-maintenance -n 50
```

### Force run now:
```bash
systemctl start model-maintenance.service
```

## What it does

1. Fetches current model lists from:
   - OpenAI API
   - Groq API
   - Anthropic (hardcoded - no API endpoint)
   - Google Gemini (hardcoded)
   - Cohere (hardcoded)

2. Compares with PostgreSQL `api_models` table

3. Proposes changes:
   - **New models** → ADD to database
   - **Missing models** → DISABLE (mark deprecated)

4. Auto-assigns tier based on model name:
   - **High tier**: gpt-4o, opus, pro, plus, o1-
   - **Fast tier**: mini, haiku, flash, lite, 7b, 8b
   - **Medium tier**: everything else

## Schedule

- **Daily:** 3:00 AM (via systemd timer)
- **On boot:** 5 minutes after startup
- **Manual:** Any time via `systemctl start model-maintenance`

## Logs

```bash
# View recent runs
journalctl -u model-maintenance -n 100

# Follow live
journalctl -u model-maintenance -f
```

## Database Impact

- New models: `INSERT ... ON CONFLICT DO NOTHING`
- Deprecated: `UPDATE enabled = false` (preserves history)
- Cost defaults: $0.001/$0.002 per 1K tokens (update manually after)
