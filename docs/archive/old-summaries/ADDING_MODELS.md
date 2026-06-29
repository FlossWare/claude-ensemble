# Adding New AI Models to Workflows

All workflows now support dynamic model detection. You can easily add new models like Grok, Ollama, OpenAI, etc.

## Current Model Support

### Always Available
- **Claude Opus** (`opus`) - Premium tier, complex reasoning
- **Claude Sonnet** (`sonnet`) - Balanced tier, general purpose
- **Claude Haiku** (`haiku`) - Fast tier, quick tasks

### Currently Enabled
- **Gemini** (`gemini`) - Via MCP or Google AI API

### Available to Enable
- **Grok** (`grok`) - xAI's model via API
- **Ollama** (local models) - Run locally without API costs
- **OpenAI** (`gpt-4`, `gpt-4-turbo`) - Via MCP integration
- **Custom models** - Any model accessible via agent() calls

## How Models Work in Workflows

Workflows use the `parallel()` function to run multiple models concurrently. Models that fail (not configured, not available, network error) simply return `null` and are filtered out:

```javascript
const reviews = await parallel(workers.map(model =>
  () => agent(prompt, { model, schema })
))

const validReviews = reviews.filter(Boolean)  // Filters out null results
```

**This means you can safely add any model** - if it's not available, it's simply skipped!

## How to Add Models

### Option 1: Edit Workflow Files Directly

Find the `WORKERS` array or `workers:` config in any workflow:

```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',  // Claude models (always available)
  'gemini',                    // Gemini (via MCP/Google AI API)
  // 'grok',                   // Grok (via xAI API) - uncomment when configured
  // 'ollama/llama3',          // Ollama (local) - uncomment when running
  // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
]
```

Simply **uncomment the models you want to use**:

```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'gemini',
  'grok',                   // ✅ Now enabled!
  'ollama/llama3',          // ✅ Now enabled!
  'gpt-4',                  // ✅ Now enabled!
]
```

### Option 2: Override via Args

Pass custom workers when invoking a workflow:

```bash
# Use specific models
/code-solve 42 --workers=opus,gemini,grok

# Or via args object
/code-solve { "workers": ["opus", "grok", "ollama/llama3"] }
```

### Option 3: Create Model Configuration File

Create `~/.claude/workflows/shared/models.js`:

```javascript
export const DEFAULT_WORKERS = [
  'opus', 'sonnet', 'haiku',
  'gemini',
  'grok',
  'ollama/llama3',
]
```

Then import in workflows (note: imports currently don't work in workflows, use inline instead).

## Workflow Files to Update

### Interactive Workflows
- `ai-prompt.js` - Multi-model consensus responses
- `code-solve.js` - Issue solving
- `code-pr-review.js` - PR reviews
- `code-release-notes.js` - Release notes generation
- `code-doc.js` - Documentation generation
- `code-security.js` - Security audits
- `code-test.js` - Comprehensive testing

### Autonomous Workflows
- `code-solve-auto.js`
- `code-pr-review-auto.js`
- `code-review-auto.js`
- `code-test-auto.js`
- `code-security-auto.js`
- `code-doc-auto.js`
- `code-release-notes-auto.js`

## Model-Specific Setup

### Grok (xAI)

1. Get API key from https://console.x.ai/
2. Set environment variable:
   ```bash
   export XAI_API_KEY="xai-..."
   ```
3. Uncomment `'grok'` in workflows
4. Test: `/ai-prompt test grok`

### Ollama (Local Models)

1. Install Ollama: https://ollama.ai/
2. Pull models:
   ```bash
   ollama pull llama3
   ollama pull codestral
   ollama pull deepseek-coder
   ```
3. Uncomment Ollama models in workflows:
   ```javascript
   'ollama/llama3',
   'ollama/codestral',
   'ollama/deepseek-coder',
   ```
4. Test: `/ai-prompt test ollama`

### OpenAI (GPT-4, etc.)

1. Requires MCP server for OpenAI
2. Configure in `~/.claude/settings.json`:
   ```json
   {
     "mcpServers": {
       "openai": {
         "command": "npx",
         "args": ["-y", "@anthropic/mcp-server-openai"],
         "env": {
           "OPENAI_API_KEY": "sk-..."
         }
       }
     }
   }
   ```
3. Uncomment OpenAI models in workflows
4. Test: `/ai-prompt test openai`

### Gemini (Already Enabled)

Gemini is already enabled in all workflows via MCP integration.

## Benefits of Multi-Model Workflows

### Diversity
- Different models catch different issues
- Reduces blind spots from single-model bias
- Better coverage across problem domains

### Consensus
- 4+ models voting increases confidence
- Reduces false positives in reviews
- Adversarial verification catches edge cases

### Cost Optimization
- Use Haiku + Gemini for cheap verification
- Reserve Opus for complex arbiter decisions
- Ollama models = zero API cost (local)

### Performance
- All models run in parallel
- Wall-clock time = slowest single model
- No sequential bottleneck

## Example: Adding Grok and Ollama

1. **Edit code-solve.js**:

```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'gemini',
  'grok',              // ✅ Added
  'ollama/llama3',     // ✅ Added
]
```

2. **Configure Grok**:
```bash
export XAI_API_KEY="xai-..."
```

3. **Start Ollama**:
```bash
ollama serve
ollama pull llama3
```

4. **Test**:
```bash
/code-solve 42
# Now uses 6 workers: opus, sonnet, haiku, gemini, grok, ollama/llama3
```

## Troubleshooting

### Model Not Working?

Models that fail are automatically filtered out. Check logs:

```
🤖 Workers: opus, sonnet, haiku, gemini, grok (5 models)
🔄 Running 5-model review...
⚠️ grok failed: Network error
✅ Received responses from 4 models
```

This is **normal** - the workflow continues with available models.

### Want More Details?

Enable debug logging:
```bash
export DEBUG=claude:workflows
/code-solve 42
```

### Minimum Models Required

Most workflows need at least 2-3 models for consensus. If too few models are available, workflows may skip consensus and use a single model as fallback.

## Future: Auto-Discovery

Future enhancement: workflows could auto-detect available models by pinging each one:

```javascript
const availableModels = []
for (const model of ALL_POSSIBLE_MODELS) {
  try {
    await agent('ping', { model, timeout: 1000 })
    availableModels.push(model)
  } catch {
    // Model not available
  }
}
```

Currently this is commented out to avoid startup delays, but you can enable it in `code-test.js` which already has this pattern implemented!

## Contributing

Found a new model that works well? Update this guide and submit a PR!

- What model did you add?
- How did you configure it?
- What are the tradeoffs vs existing models?
- Cost/performance comparison?

---

**Last Updated**: 2026-06-06  
**Workflows Updated**: All (11 total)  
**Default Workers**: 4 (opus, sonnet, haiku, gemini)  
**Available to Enable**: Grok, Ollama, OpenAI, and more
