---
name: detect-local-models
description: Auto-detect locally available Ollama models and update configuration
---

# Detect Local Models - Ollama Auto-Discovery

Automatically discover, test, and configure locally available Ollama models. This skill handles the complete lifecycle of local model detection, verification, and integration into your Claude Code workflow.

## Features

- **Installation Check**: Verifies Ollama is installed and accessible
- **Service Verification**: Detects if Ollama service is running, attempts auto-start
- **Model Discovery**: Lists all locally available models with sizes
- **Model Testing**: Validates each model can execute properly
- **Smart Categorization**: Automatically assigns models to roles (fast, balanced, powerful, code)
- **Config Management**: Updates local-models-config.json with detected models
- **Comprehensive Reporting**: Detailed status report with next steps
- **Robust Error Handling**: Graceful failures with helpful suggestions
- **Flexible Execution**: Test, dry-run, or auto-update modes

## Installation

Ensure Ollama is installed:

```bash
# macOS / Linux with Homebrew
brew install ollama

# Or download from https://ollama.ai
```

## Usage

### Basic Detection (Preview Mode)

```bash
# See what models would be detected without making changes
claude run detect-local-models

# Or via skill
/detect-local-models
```

### Auto-Update Configuration

```bash
# Detect models and automatically update local-models-config.json
claude run detect-local-models --auto

# Or via skill
/detect-local-models --auto
```

### Skip Model Testing

```bash
# Faster detection without testing each model
claude run detect-local-models --skip-test --auto
```

### Verbose Output

```bash
# Show all executed commands and detailed debug info
claude run detect-local-models --verbose --auto
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--auto` | Automatically update configuration without confirmation |
| `--skip-test` | Don't test each model (faster, less thorough) |
| `--verbose` | Show detailed debug output for all operations |

## Workflow Phases

### Phase 1: Check Ollama Installation

- Locates Ollama binary in PATH using `which ollama`
- Retrieves version information
- Fails gracefully with installation URL if not found

**Success**: Ollama found and versioned
**Failure**: Returns installation instructions

### Phase 2: Service Status Check

- Attempts to connect to Ollama service on localhost:11434
- If not running, automatically attempts to start the service
- Retries connection up to 3 times with 2-second delays
- Falls back to manual start instructions if auto-start fails

**Success**: Service confirmed running
**Warning**: Service not running but user can start manually
**Failure**: Cannot connect after auto-start attempts

### Phase 3: List Available Models

- Executes `ollama list` to retrieve all downloaded models
- Parses model names, IDs, and sizes
- Handles multiple size formats (MB, GB)
- Fails if no models are available (with suggestion to pull one)

**Output**: Array of model objects with metadata

### Phase 4: Test Models

Unless `--skip-test` is used:

- Runs a simple prompt on each model: "Say hello in one word"
- Records success/failure status with error messages
- Non-blocking failures (failed model doesn't stop detection)
- Creates detailed test report for each model

**Result**: Categorized models (working vs failed)

### Phase 5: Smart Categorization

Automatically assigns models to roles based on name patterns:

```
Code Models:      "code", "coder", "phi"
Fast Models:      "lite", "tiny", "mini"
Powerful Models:  "dolphin", "wizard", "neural"
Balanced Models:  default fallback
```

Ensures fallback assignment if patterns don't match.

### Phase 6: Update Configuration

Updates `/home/sfloess/.claude/repos/claude-global-skills/local-models-config.json`:

```json
{
  "enabled": false,
  "provider": "ollama",
  "baseUrl": "http://localhost:11434",
  "models": {
    "fast": "model-name",
    "balanced": "model-name",
    "powerful": "model-name",
    "code": "model-name"
  },
  "detected_at": "2026-06-10T15:30:00.000Z",
  "detected_models": {
    "model-name": {
      "name": "model-name",
      "id": "sha256:...",
      "size": 4096,
      "sizeStr": "4.0GB",
      "status": "working",
      "tested_at": "2026-06-10T15:30:00.000Z"
    }
  },
  "fallback_to_claude": true
}
```

### Phase 7: Status Report

Returns comprehensive JSON report:

```json
{
  "success": true,
  "timestamp": "2026-06-10T15:30:00.000Z",
  "ollama": {
    "installed": true,
    "path": "/usr/local/bin/ollama",
    "version": "0.1.0",
    "service_running": true,
    "service_version": "0.1.0"
  },
  "models": {
    "available": 3,
    "working": 3,
    "failed": 0,
    "details": { /* model objects */ }
  },
  "detection": {
    "auto_update": true,
    "config_path": "/home/sfloess/.claude/repos/claude-global-skills/local-models-config.json",
    "fast": "phi:latest",
    "balanced": "llama2:latest",
    "powerful": "neural-chat:latest",
    "code": null
  },
  "next_steps": [
    "Run with --auto to update configuration",
    "Enable in workflows: detect-local-models --enable"
  ],
  "ready_to_use": true
}
```

## Error Handling

### Ollama Not Installed

```
❌ Ollama not found in PATH
⚠️ Install Ollama from https://ollama.ai
```

**Resolution**: Visit https://ollama.ai and download the installer

### Service Not Running

```
⚠️ Service not responding on localhost:11434
✓ Service started successfully
```

**Automatic**: The skill attempts auto-start with 3 retries
**Manual**: Run `ollama serve` in a terminal

### No Models Available

```
⚠️ No models available. Pull some first: ollama pull <model>
```

**Resolution**: Pull a model first:
```bash
ollama pull llama2
ollama pull phi
ollama pull neural-chat
```

### Model Test Failures

```
⚠️ Failed to test model-name
  Error: timeout after 30 seconds
```

**Resolution**: Model may have issues or be slow. Try:
1. Test manually: `echo "test" | ollama run model-name`
2. Check model integrity: `ollama show model-name`
3. Pull fresh copy: `ollama pull model-name`

## Configuration File

### Location
```
/home/sfloess/.claude/repos/claude-global-skills/local-models-config.json
```

### Manual Updates

Edit directly to override auto-detected models:

```json
{
  "enabled": true,
  "models": {
    "fast": "phi:latest",
    "balanced": "llama2:13b",
    "powerful": "neural-chat:latest",
    "code": "codellama:latest"
  }
}
```

### Roles Explained

| Role | Use Case | Example |
|------|----------|---------|
| `fast` | Quick responses, low latency | phi, tinyllama |
| `balanced` | General purpose, good tradeoff | llama2, mistral |
| `powerful` | Complex tasks, best quality | neural-chat, dolphin |
| `code` | Code generation and analysis | codellama, phi-coder |

## Integration with Workflows

Once models are detected, enable them in workflows:

1. Run detection: `detect-local-models --auto`
2. Verify config: `cat local-models-config.json`
3. Enable in workflows: Set `"enabled": true` in config
4. Use in your skill: Reference model roles in queries

## Example: Using Detected Models

In a custom skill:

```javascript
// Reference auto-detected models
const modelConfig = require('./local-models-config.json')

if (modelConfig.enabled && modelConfig.models.code) {
  const codeModel = modelConfig.models.code
  // Use for code generation tasks
}
```

## Performance Considerations

### Testing Impact

- Each model test takes 5-30 seconds depending on model size and system
- Total time: 30 seconds - 5 minutes for typical local setups
- Use `--skip-test` for faster detection in CI/CD

### Memory Usage

- Ollama keeps loaded models in memory
- Large models (7B+) may need 8GB+ RAM
- Use `ollama show MODEL` to check requirements

### Network

- Initial model pulls can be large (2GB-30GB+)
- Use stable, fast internet connection
- Resume capability in newer Ollama versions

## Troubleshooting

### "curl: command not found"

Install curl:
```bash
# macOS
brew install curl

# Linux (Ubuntu/Debian)
sudo apt-get install curl

# Linux (Fedora)
sudo dnf install curl
```

### "Ollama serve: command not found"

Service auto-start may fail. Start manually:
```bash
ollama serve
```

### Model hangs during test

Some models are slow. Either:
1. Skip tests: `--skip-test`
2. Increase timeout in source code (line 160)
3. Test model manually to diagnose

### Config not updating

Check file permissions:
```bash
ls -la local-models-config.json
chmod 644 local-models-config.json  # if needed
```

## Advanced Usage

### Integration with Multi-AI Consensus

Use detected models as fallback in multi-AI queries:

```javascript
// Use fast local model for quick synthesis
const localModel = modelConfig.models.fast
if (modelConfig.enabled) {
  // Include local model in consensus
}
```

### Scheduled Detection

Run detection periodically:

```bash
# Check for new models every day
0 8 * * * /path/to/detect-local-models --auto
```

### CI/CD Integration

```bash
# Non-interactive, skip tests, fast
detect-local-models --auto --skip-test --verbose
```

## Future Enhancements

- [ ] Support for other local model providers (LM Studio, vLLM)
- [ ] Model performance benchmarking
- [ ] Automatic model pulling for common use cases
- [ ] GPU availability detection
- [ ] Model fine-tuning workflow integration
- [ ] Health checks and monitoring
- [ ] Fallback model configuration
- [ ] Rate limiting per model

## Related Skills

- `/ai-prompt` - Use detected models in multi-AI consensus
- `/ai-chat` - Interactive chat with local models
- `/code-review` - Code review using local models

## Support

For Ollama-specific issues:
- GitHub: https://github.com/jmorganca/ollama
- Docs: https://github.com/jmorganca/ollama/tree/main/docs
- Models: https://ollama.ai/library

For skill issues:
- Check verbose output: `--verbose`
- Review error messages in "Error Handling" section above
