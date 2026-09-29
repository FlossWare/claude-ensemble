# Model Registry Configuration

## User Model Config: `~/.claude/claude-ensemble-models.yaml`

Personal model configuration file. Not shared in repo — each user maintains their own.

### What goes in the config:

**Models:**
- Remote workers (usable as consensus workers):
  - `claude-opus`, `claude-sonnet`, `claude-haiku` — Anthropic (via Vertex AI)
  - `gemini` — Google Gemini 2.0 Flash
  - `cursor` — JetBrains Cursor (via API token)
  - `gpt-4` — OpenAI (when token configured)
  - `grok` — xAI (when token configured)
  - `ollama-local` — Local Ollama server

**Accounts:**
- Anthropic (Vertex AI project)
- Google (workspace + OAuth)
- Atlassian (Jira)
- OpenAI, xAI (when tokens configured)
- Notion, Trello (optional integrations)

**Skill Defaults:**
- Which models each skill uses
- Arbiter model
- When new models become available, auto-enable them

### Example Setup

```yaml
models:
  claude-opus:
    available: true
    access_via: vertex-ai
  gpt-4:
    available: false  # No token yet
    reason: "OPENAI_API_KEY not set"

accounts:
  openai:
    status: missing
    notes: "Add key to enable gpt-4"
```

### How Skills Use It

All skills use the shared `models` schema under `skill_defaults`. The loader validates the schema before a skill can route work:

```yaml
skill_defaults:
  code-pr-review:
    models: [claude-opus, claude-sonnet, cursor, gemini]
    arbiter: claude-opus
```

Each entry in `models` must name a model defined under the top-level `models` map. `arbiter` must also name a configured model. Unavailable models are filtered from worker routing; malformed configuration is rejected with a validation error.

### For Coworkers

Each person gets their own config:

```bash
# Yugank creates theirs
~/.claude/claude-ensemble-models-yugank.yaml

# Might have different:
# - Vertex AI project (different itpc- prefix)
# - Different MCP servers configured
# - Different models available (they have gpt-4, you have grok)
```

Skills auto-adapt. No code changes needed.

### Adding New Models

1. **Get API token** — e.g., OPENAI_API_KEY
2. **Update config** — mark `available: true`, fill in pricing
3. **Skills auto-use it** — next run picks it up from the skill's models list

### Pricing Reference

```yaml
haiku:
  input: 0.80 per M
  output: 2.40 per M

sonnet:
  input: 3.00 per M
  output: 15.00 per M

opus:
  input: 15.00 per M
  output: 45.00 per M

gemini:  # Cheapest
  input: 0.075 per M
  output: 0.30 per M
```

### Thompson Routing

Config includes Thompson Sampling settings:
- `enabled: true` — Dynamic model selection
- `task_types` — Which tasks get routed
- `model_selection: cost-quality-tradeoff` — Optimization strategy
- `required_capability: 0.7` — Minimum capability threshold

Skills use Thompson to pick models based on cost, past performance, and task type.

### Cursor as a Remote Worker

**Cursor** has a JetBrains API and can be used as a consensus worker:
- Accessible via `CURSOR_API_KEY` environment variable
- Can participate in multi-worker code reviews
- Zero pricing (included in Cursor subscription)
- Different reasoning style — provides unique perspective
- Good for both interactive IDE suggestions AND automated consensus patterns

Add Cursor to your skill models:
```yaml
skill_defaults:
  rh-pr-review:
    models: [claude-opus, claude-sonnet, cursor, gemini]  # Cursor as 4th worker
    arbiter: claude-opus
```

This gives consensus from: Claude (2 models), Google (Gemini), and JetBrains (Cursor).

---

**Location:** `~/.claude/claude-ensemble-models.yaml` (user home, not repo)  
**Shared by:** All Claude Ensemble skills and workflows  
**Updated by:** User when adding new API keys or changing model availability
