# Model Registry Configuration

## User Model Config: `~/.claude/rh-toolkit-models.yaml`

Personal model configuration file. Not shared in repo — each user maintains their own.

### What goes in the config:

**Models:**
- Remote workers (usable as consensus workers):
  - `claude-opus`, `claude-sonnet`, `claude-haiku` — Anthropic (via Vertex AI)
  - `gemini` — Google Gemini 2.0 Flash
  - `gpt-4` — OpenAI (when token configured)
  - `grok` — xAI (when token configured)
  - `ollama-local` — Local Ollama server

- Interactive IDE (not remotely callable):
  - `cursor` — IDE-integrated editing assistant (JetBrains)

**Accounts:**
- Anthropic (Vertex AI project)
- Google (workspace + OAuth)
- Atlassian (Jira)
- OpenAI, xAI (when tokens configured)
- Notion, Trello (optional integrations)

**Skill Defaults:**
- Which workers each skill uses
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

All 5 skills (`code-pr-review`, `code-doc`, `code-release-notes`, and auto variants) load this config:

```javascript
let userModelConfig = null
try {
  const configPath = path.expandUser('~/.claude/rh-toolkit-models.yaml')
  if (fs.existsSync(configPath)) {
    userModelConfig = yaml.load(fs.readFileSync(configPath, 'utf8'))
  }
} catch (err) {
  // Falls back to hardcoded defaults
}

const WORKERS = userModelConfig?.skill_defaults?.['code-pr-review']?.workers || [
  'opus', 'sonnet', 'haiku', 'gemini'  // Hardcoded fallback
]
```

### For Coworkers

Each person gets their own config:

```bash
# Yugank creates theirs
~/.claude/rh-toolkit-models-yugank.yaml

# Might have different:
# - Vertex AI project (different itpc- prefix)
# - Different MCP servers configured
# - Different models available (they have gpt-4, you have grok)
```

Skills auto-adapt. No code changes needed.

### Adding New Models

1. **Get API token** — e.g., OPENAI_API_KEY
2. **Update config** — mark `available: true`, fill in pricing
3. **Skills auto-use it** — next run picks it up from workers list

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

### IDE-Integrated Models (Not Remote Workers)

**Cursor** is available in the config but marked `access_via: ide-plugin`:
- Can't be called remotely
- Used for interactive, real-time IDE suggestions
- Good for direct code editing
- Not suitable for automated consensus reviews

When writing direct code, you'd use Cursor interactively in the IDE.
When running automated workflows, skills use remote workers (opus, sonnet, etc.).

---

**Location:** `~/.claude/rh-toolkit-models.yaml` (user home, not repo)  
**Shared by:** All RH skills and workflows  
**Updated by:** User when adding new API keys or changing model availability
