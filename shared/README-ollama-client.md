# Ollama Client for claude-global-skills

**SSH-based Ollama integration for the fleet.**

## Overview

Provides direct access to 12 Ollama models deployed across 4 fleet hosts (server-01/02/03, aio-01):
- 3 code generation models (starcoder2:7b, sqlcoder:7b, openchat:7b)
- 6 general models (phi3.5, wizardlm2:7b, zephyr:7b, gemma3:4b, stablelm-zephyr:3b)
- 1 reasoning model (mathstral:7b)
- 2 embedding models (nomic-embed, granite-embedding)

**Cost:** $0 (local inference only)

## Architecture

```
ollamaAgent(prompt, options)
    ↓
Query orchestrator (pi-02:8888) for routing
    ↓
SSH to fleet host (server-01/02/03/aio-01)
    ↓
Execute: ollama run <model> <prompt>
    ↓
Return response (text or parsed JSON if schema provided)
```

**Why SSH instead of HTTP API?**
- Ollama's HTTP API (port 11434) only listens on localhost
- Not exposed on network for security
- SSH execution is more secure and works across fleet

## Usage

### Basic Generation

```javascript
import { ollamaAgent } from './shared/ollama-client.js';

const response = await ollamaAgent('Write hello world in Java', {
  model: 'starcoder2:7b',
  host: 'server-01'  // Optional - auto-routes if omitted
});

console.log(response);
```

### Structured Output (JSON Schema)

```javascript
const BUG_SCHEMA = {
  type: 'object',
  properties: {
    bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          severity: { type: 'string' },
          description: { type: 'string' }
        },
        required: ['file', 'severity', 'description']
      }
    }
  },
  required: ['bugs']
};

const bugs = await ollamaAgent('Review this code for bugs...', {
  model: 'starcoder2:7b',
  schema: BUG_SCHEMA  // Forces JSON output
});

console.log(bugs.bugs.length);  // Parsed object, not string
```

### Parallel Execution (Multi-AI Consensus)

```javascript
import { ollamaAgent, ollamaParallel } from './shared/ollama-client.js';

const workers = await ollamaParallel([
  () => ollamaAgent(prompt, { model: 'starcoder2:7b', label: 'starcoder2-worker' }),
  () => ollamaAgent(prompt, { model: 'wizardlm2:7b', label: 'wizardlm2-worker' }),
  () => ollamaAgent(prompt, { model: 'phi3.5', label: 'phi35-worker' }),
  () => ollamaAgent(prompt, { model: 'mathstral:7b', label: 'mathstral-worker' })
]);

const validResponses = workers.filter(Boolean);  // Remove nulls (failures)
```

## Available Models

**Code Generation:**
- `starcoder2:7b` - Best for code generation/completion (4.0 GB)
- `sqlcoder:7b` - SQL generation and queries (4.1 GB)
- `openchat:7b` - General coding assistance (4.1 GB)

**Reasoning:**
- `mathstral:7b` - Math, logic, reasoning (4.1 GB)

**General Purpose:**
- `phi3.5:latest` - Fast, good quality (2.2 GB) **RECOMMENDED**
- `wizardlm2:7b` - Instruction following (4.1 GB)
- `zephyr:7b` - Chat-focused (4.1 GB)
- `gemma3:4b` - Lightweight (3.3 GB)
- `stablelm-zephyr:3b` - Very fast, smallest (1.6 GB)

**Embeddings:**
- `nomic-embed-text:latest` - Text embeddings for RAG (274 MB)
- `granite-embedding:latest` - Lightweight embeddings (62 MB)

## API Reference

### `ollamaAgent(prompt, options)`

Drop-in replacement for Claude Code's `agent()` API.

**Parameters:**
- `prompt` (string) - The prompt to send
- `options` (object):
  - `model` (string) - Model name, default: `'phi3.5:latest'`
  - `label` (string) - Label for logging, default: model name
  - `schema` (object) - JSON schema for structured output, optional
  - `host` (string) - Override host (skips routing), optional
  - `retries` (number) - Number of retries, default: 2
  - `timeout` (number) - Timeout in ms, default: 120000 (2 min)

**Returns:** `Promise<string|object>`
- String if no schema
- Parsed object if schema provided
- `null` on failure (after retries)

### `ollamaParallel(agentCalls)`

Execute multiple Ollama calls in parallel.

**Parameters:**
- `agentCalls` (Array<Function>) - Array of functions returning promises

**Returns:** `Promise<Array<string|object|null>>`
- Array of responses (nulls for failures)

### `getAvailableModels()`

Query orchestrator for list of available models.

**Returns:** `Promise<string[]>` - Array of model names

### `testOllamaConnection(host, model)`

Test connectivity to a fleet host.

**Parameters:**
- `host` (string) - Fleet hostname, default: `'server-01'`
- `model` (string) - Model to test, default: `'phi3.5:latest'`

**Returns:** `Promise<{success: boolean, response?: string, error?: string}>`

## CLI Usage

```bash
# Test connection
node shared/ollama-client.js test server-01

# List available models
node shared/ollama-client.js models

# Generate text
node shared/ollama-client.js generate server-01 starcoder2:7b "Write hello world in Java"
```

## Performance

**Typical Response Times:**
- `phi3.5:latest` (2.2GB): ~5-10s for short prompts
- `starcoder2:7b` (4.0GB): ~10-15s for code generation
- `mathstral:7b` (4.1GB): ~10-20s for reasoning

**Fleet Distribution:**
- All 4 hosts have identical models (consistency)
- Load balanced via orchestrator routing
- Parallel execution: 4× speedup (4 hosts × 1 model each)

## Hybrid Claude + Ollama Pattern

**Best practice: Free Ollama workers + Cheap Claude arbiter**

```javascript
// Workers: Free Ollama models in parallel
const workers = await ollamaParallel([
  () => ollamaAgent(prompt, { model: 'starcoder2:7b', schema: BUG_SCHEMA }),
  () => ollamaAgent(prompt, { model: 'wizardlm2:7b', schema: BUG_SCHEMA }),
  () => ollamaAgent(prompt, { model: 'phi3.5', schema: BUG_SCHEMA }),
  () => ollamaAgent(prompt, { model: 'openchat:7b', schema: BUG_SCHEMA })
]);

// Arbiter: Cheap Claude model for synthesis
const synthesis = await agent(`Synthesize these ${workers.filter(Boolean).length} reports...`, {
  model: 'haiku',  // $0.01 per synthesis
  schema: ARBITER_SCHEMA
});

// Cost: $0 workers + $0.01 arbiter = 93% cheaper than all-Claude
```

## Limitations

1. **Slower than cloud APIs** - Local inference ~10-20s vs <2s for Claude
2. **No native JSON schema** - We prompt for JSON and parse, less reliable than Claude's native support
3. **SSH overhead** - ~100ms per call for SSH connection
4. **Sequential per host** - Each host runs 1 inference at a time (no GPU parallelism)
5. **Quality varies** - 7B models weaker than Claude Opus/Sonnet for complex reasoning

## Troubleshooting

**"SSH ollama execution failed":**
- Check SSH key auth: `ssh server-01 echo OK`
- Verify Ollama installed: `ssh server-01 ollama list`

**"Failed to parse JSON":**
- 7B models struggle with strict JSON output
- Try simpler schema or increase retries
- Use Claude arbiter for final synthesis

**Slow responses:**
- Normal for 7B models (~10-15s)
- Use faster models: `phi3.5:latest` (2.2GB), `stablelm-zephyr:3b` (1.6GB)
- Consider parallel execution across 4 hosts

## Future Enhancements

- [ ] Orchestrator returns actual host mapping (not hardcoded server-01)
- [ ] Model-to-host affinity (route model X always to host Y)
- [ ] GPU detection and routing
- [ ] Streaming output support
- [ ] Connection pooling (persistent SSH sessions)
- [ ] Larger models (13B, 33B) on high-RAM hosts
