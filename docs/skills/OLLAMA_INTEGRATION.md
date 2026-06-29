# Ollama Integration Guide

Comprehensive guide for integrating Ollama local models into the claude-global-skills multi-AI workflow system.

---

## Table of Contents

1. [What Is Ollama and Why Use It](#1-what-is-ollama-and-why-use-it)
2. [Hardware Requirements and GPU/CPU Guidance](#2-hardware-requirements-and-gpucpu-guidance)
3. [Installation on Linux](#3-installation-on-linux)
4. [Downloading Models](#4-downloading-models)
5. [Starting the Ollama Service](#5-starting-the-ollama-service)
6. [Testing That Ollama Is Working](#6-testing-that-ollama-is-working)
7. [Integrating with Multi-AI Workflows](#7-integrating-with-multi-ai-workflows)
8. [Model Strings Reference](#8-model-strings-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What Is Ollama and Why Use It

### What Is Ollama

Ollama is an open-source tool for running large language models (LLMs) locally on your own hardware. It packages model weights, configuration, and a REST API server into a single binary. You download a model once, and then interact with it entirely offline through an OpenAI-compatible HTTP API on `localhost:11434`.

### Why Use Ollama with Our Workflows

**Zero API cost.** Ollama models run on your local GPU (or CPU). There are no per-token charges, no rate limits, and no monthly bills. Every query to an Ollama model is free after the initial download.

**Privacy.** Code, prompts, and responses never leave your machine. This matters for proprietary codebases, security audits, and regulated environments where sending code to external APIs is prohibited or undesirable.

**Diversity in consensus.** Our multi-AI workflows use multiple models voting in parallel. Adding Ollama models (Llama 3, DeepSeek Coder, Codestral, Qwen) introduces fundamentally different model architectures and training data into the consensus pool. Different models catch different bugs. A 6-model consensus (opus + sonnet + haiku + gemini + ollama/llama3 + ollama/deepseek-coder) provides far broader coverage than a 3-model consensus from a single provider.

**Offline operation.** Ollama works without internet. You can run full code reviews, security audits, and SDLC workflows on an airplane or in an air-gapped environment (Claude itself still requires connectivity, but Ollama workers operate locally).

**Speed for small models.** Models like Llama 3 8B and Qwen 2.5 7B respond in under a second on modern GPUs. They can serve as fast "first pass" workers while heavier cloud models handle deep analysis.

**Cost optimization examples:**

| Configuration | Workers | API Cost per Run |
|---------------|---------|-----------------|
| Claude-only (default) | opus + sonnet + haiku | 3 API calls |
| Claude + Gemini | opus + sonnet + haiku + gemini | 4 API calls |
| Claude + Ollama | opus + sonnet + ollama/llama3 + ollama/deepseek-coder | 2 API calls |
| Full hybrid | opus + haiku + gemini + ollama/llama3 + ollama/codestral | 2 API calls |

By replacing some cloud workers with Ollama models, you cut API costs while maintaining (or increasing) consensus diversity.

---

## 2. Hardware Requirements and GPU/CPU Guidance

**Read this section before installing.** Knowing your hardware determines which models you can run and how fast they will be. There is no point in downloading a 40 GB model if your GPU only has 8 GB of VRAM.

### GPU Support

Ollama supports NVIDIA GPUs (via CUDA), AMD GPUs (via ROCm), and CPU-only mode.

| Model Size | Minimum VRAM | Recommended VRAM | CPU-only Viable? |
|------------|-------------|-------------------|------------------|
| 7B-8B params | 4 GB | 8 GB | Yes (slow) |
| 13B-14B params | 8 GB | 16 GB | Marginal |
| 34B params | 16 GB | 24 GB | No |
| 70B params | 40 GB | 48 GB | No |

**Check your GPU:**

```bash
# NVIDIA
nvidia-smi

# AMD
rocm-smi

# No GPU? See CPU Fallback below.
```

### CPU Fallback Guidance

If you have no GPU, or your GPU does not have enough VRAM, Ollama will automatically fall back to running the model on your CPU. This works but is significantly slower (5-20x slower than GPU). Here is how to get the best experience on CPU-only hardware:

- **Stick to small models (7B or fewer parameters).** Models like `llama3` (8B), `deepseek-coder` (6.7B), `llama3.2:3b` (3B), and `phi3` (3.8B) are your best options. Avoid anything above 14B.
- **Expect 10-60 second response times** depending on model size and prompt length. This is normal for CPU inference.
- **Ensure you have enough RAM.** CPU inference loads the model into system RAM instead of VRAM. A 7B model needs roughly 4-6 GB of free RAM; a 13B model needs roughly 8-10 GB.
- **Use only one Ollama worker in your workflow config.** Running multiple CPU-based Ollama workers in parallel will thrash your system. One local worker plus cloud models is the sweet spot.
- **Consider the 3B models for fast CPU iteration.** `llama3.2:3b` and `phi3` are small enough to run at reasonable speed on modern CPUs and still contribute meaningfully to consensus.

CPU-only is perfectly viable for development and testing. For production consensus workflows where speed matters, a GPU is strongly recommended.

### Disk Space Requirements

Models are stored in `~/.ollama/models/` (or `/usr/share/ollama/.ollama/models/` if using systemd with the ollama user).

**Quick summary:** The recommended core set of 4 models (llama3 + codestral + deepseek-coder + qwen2.5-coder) requires approximately 27 GB of disk space. Make sure you have at least 30 GB free before starting.

| Model | Approximate Size |
|-------|-----------------|
| llama3 (8B, Q4) | ~4.7 GB |
| llama3:70b (Q4) | ~40 GB |
| codestral (22B, Q4) | ~13 GB |
| deepseek-coder (6.7B, Q4) | ~3.8 GB |
| deepseek-coder:33b (Q4) | ~19 GB |
| qwen2.5 (7B, Q4) | ~4.4 GB |
| qwen2.5-coder (7B, Q4) | ~4.4 GB |

### What "Q4" (Quantization) Means

You will see labels like "Q4" or "q4_0" in model names and this guide. Quantization is a compression technique that reduces a model's memory footprint by storing its numerical weights at lower precision. Here is what the common labels mean:

- **Q4 (4-bit quantization):** Each weight is stored using 4 bits instead of the original 16 or 32 bits. This cuts the model size to roughly 25-30% of the original, with a small quality loss that is usually acceptable for code review and consensus tasks. This is the default quantization for most Ollama models.
- **Q8 (8-bit quantization):** Higher quality than Q4 but uses roughly twice the disk space and VRAM. Good if you have the headroom and want better output.
- **Q2 / Q3:** More aggressive compression. Noticeably lower quality. Only use these if you are very constrained on memory.

**Rule of thumb:** The default Ollama downloads (which are Q4) are the right choice for most users. You do not need to think about quantization unless you are troubleshooting memory issues or chasing quality improvements.

---

## 3. Installation on Linux

### Which Method Should I Use?

| Criteria | Method 1: Install Script | Method 2: Manual Binary |
|----------|------------------------|------------------------|
| **Best for** | Most users, quick setup | Security-conscious users, custom setups |
| **Ease** | One command, fully automated | Multiple steps, you control each one |
| **What it does** | Downloads binary, creates systemd service, detects GPU drivers | You download the binary and optionally create the service yourself |
| **Requires piping to sh** | Yes | No |
| **Customizable** | Limited (uses defaults) | Full control over user, paths, and service config |

**Recommendation:** Use Method 1 unless your organization prohibits piping remote scripts to `sh`, or you need to customize the installation (non-standard paths, specific user/group, proxy configuration, etc.).

### Method 1: Official Install Script (Recommended)

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

This installs the `ollama` binary to `/usr/local/bin/ollama` and sets up a systemd service called `ollama.service`. It works on Ubuntu, Debian, Fedora, RHEL, Arch, and most other mainstream Linux distributions.

### Method 2: Manual Binary Download

If you prefer not to pipe scripts to `sh`:

```bash
# Download the latest binary
curl -L https://ollama.com/download/ollama-linux-amd64 -o ollama
chmod +x ollama
sudo mv ollama /usr/local/bin/

# Create a dedicated user (optional but recommended for systemd)
sudo useradd -r -s /bin/false -m -d /usr/share/ollama ollama

# Create a systemd service file
sudo tee /etc/systemd/system/ollama.service > /dev/null <<'SERVICEEOF'
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="HOME=/usr/share/ollama"

[Install]
WantedBy=default.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
```

### Method 3: Fedora / DNF

```bash
# Ollama is available via the official install script on Fedora as well
curl -fsSL https://ollama.com/install.sh | sh
```

### Verify Installation

```bash
ollama --version
# Expected output: ollama version 0.x.x (or similar)
```

---

## 4. Downloading Models

### Recommended Models for Code Workflows

Pull these models to get a strong set of local workers for code review, security audit, and general consensus tasks.

#### Llama 3 -- General-purpose reasoning

```bash
# 8B parameter version (recommended starting point)
ollama pull llama3

# 70B parameter version (requires 40+ GB VRAM)
ollama pull llama3:70b

# Llama 3.1 (latest iteration with larger context)
ollama pull llama3.1

# Llama 3.2 (smallest variants, good for fast consensus)
ollama pull llama3.2:3b
```

**Strengths:** Strong general reasoning, good at code review, broad knowledge base.
**Best for:** General-purpose worker in multi-AI consensus, documentation review, broad code analysis.

#### Codestral -- Code-specialized by Mistral

```bash
# 22B parameter code model
ollama pull codestral

# Smaller Mistral code model alternative
ollama pull mistral
```

**Strengths:** Purpose-built for code generation and analysis, strong at multiple programming languages, understands code structure deeply.
**Best for:** Code review, code generation, refactoring suggestions, finding code smells.

#### DeepSeek Coder -- Deep code understanding

```bash
# 6.7B version (good balance of speed and quality)
ollama pull deepseek-coder

# 33B version (much better quality, needs more VRAM)
ollama pull deepseek-coder:33b

# DeepSeek Coder V2 (latest, improved)
ollama pull deepseek-coder-v2
```

**Strengths:** Excellent at code completion, bug detection, and understanding code semantics. Trained on massive code corpora.
**Best for:** Bug hunting, security vulnerability detection, code completion, test generation.

#### Qwen 2.5 -- Versatile multilingual coder

```bash
# General Qwen 2.5 (7B)
ollama pull qwen2.5

# Code-specialized variant (recommended for workflows)
ollama pull qwen2.5-coder

# Larger variant (14B, better quality)
ollama pull qwen2.5-coder:14b
```

**Strengths:** Strong multilingual support, excellent code understanding, good at following structured output schemas.
**Best for:** Structured analysis tasks, multi-language codebases, schema-constrained responses.

### Pulling All Recommended Models at Once

```bash
# Core set (approximately 27 GB total disk space)
ollama pull llama3
ollama pull codestral
ollama pull deepseek-coder
ollama pull qwen2.5-coder

# Verify all models are downloaded
ollama list
```

Expected output from `ollama list`:

```
NAME                    ID              SIZE      MODIFIED
codestral:latest        <hash>          13 GB     just now
deepseek-coder:latest   <hash>          3.8 GB    just now
llama3:latest           <hash>          4.7 GB    just now
qwen2.5-coder:latest   <hash>          4.4 GB    just now
```

---

## 5. Starting the Ollama Service

### Option A: Systemd Service (Recommended for Always-On)

If you installed via the official script, the service is already configured:

```bash
# Start the service
sudo systemctl start ollama

# Enable on boot
sudo systemctl enable ollama

# Check status
sudo systemctl status ollama
```

Expected output:

```
  ollama.service - Ollama Service
     Loaded: loaded (/etc/systemd/system/ollama.service; enabled)
     Active: active (running) since ...
```

### Option B: Manual Foreground (Development / Debugging)

```bash
# Run in foreground (useful to see logs)
ollama serve
```

This starts the API server on `http://localhost:11434`. Press Ctrl+C to stop.

### Option C: Background Process

```bash
# Start in background
ollama serve &

# Or with nohup for persistence
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

### Configuring the Listen Address

By default, Ollama listens on `127.0.0.1:11434`. To change this:

```bash
# Listen on all interfaces (for remote access)
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Or set in systemd override
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"
```

### Configuring GPU Layers

Control how much of the model is offloaded to GPU:

```bash
# Use all available GPU memory
OLLAMA_GPU_LAYERS=999 ollama serve

# Limit GPU usage (useful when sharing GPU with other processes)
OLLAMA_GPU_LAYERS=20 ollama serve
```

---

## 6. Testing That Ollama Is Working

### Test 1: Health Check

```bash
curl http://localhost:11434/
# Expected: "Ollama is running"
```

### Test 2: List Available Models

```bash
ollama list
# Should show all models you pulled in step 4
```

### Test 3: Interactive Chat

```bash
ollama run llama3 "What is 2+2? Reply with just the number."
# Expected: "4"
```

### Test 4: API Endpoint (OpenAI-Compatible)

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Say hello in exactly 3 words"}],
    "temperature": 0.1
  }'
```

Expected: A JSON response with a `choices[0].message.content` field containing a greeting.

### Test 5: Structured Output (Critical for Workflows)

Our workflows rely on structured JSON output. Test that the model can produce it:

```bash
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "prompt": "Analyze this code for bugs: function add(a,b) { return a - b; }\n\nReturn JSON with fields: bug_found (boolean), description (string), fix (string)",
    "format": "json",
    "stream": false
  }'
```

Expected: A JSON response where the `response` field contains parseable JSON describing the bug.

### Test 6: Test Each Downloaded Model

```bash
for model in llama3 codestral deepseek-coder qwen2.5-coder; do
  echo "Testing $model..."
  result=$(ollama run "$model" "Reply with exactly: OK" 2>/dev/null | head -1)
  if echo "$result" | grep -qi "ok"; then
    echo "  PASS: $model is working"
  else
    echo "  WARN: $model responded with: $result"
  fi
done
```

### Test 7: Test from Our Workflow System

Use the `ai-prompt` skill to verify end-to-end integration:

```bash
# After enabling Ollama models in workflows (see section 7)
/ai-prompt "What is 1+1? Reply concisely."
```

Check the output for worker labels showing Ollama models responding successfully.

---

## 7. Integrating with Multi-AI Workflows

### Step 1: Enable Ollama Models in Workflow Files

Each workflow has a model detection function or a `WORKERS` array. Uncomment the Ollama models.

**In `ai-prompt.js`** (and similar workflows), find the `getAvailableWorkers` function:

```javascript
// Before (Ollama commented out):
// models.push('ollama/llama3', 'ollama/codestral', 'ollama/deepseek-coder')

// After (Ollama enabled):
models.push('ollama/llama3', 'ollama/codestral', 'ollama/deepseek-coder')
```

**In workflow files with `WORKERS` arrays** (code-solve.js, code-review.js, etc.):

```javascript
// Before:
const WORKERS = ['opus', 'sonnet', 'haiku', 'gemini']

// After (add Ollama models):
const WORKERS = [
  'opus', 'sonnet', 'haiku',     // Claude (always available)
  'gemini',                       // Google (via MCP)
  'ollama/llama3',                // Ollama local
  'ollama/deepseek-coder',        // Ollama local (code-specialized)
]
```

### Step 2: Update the Multi-AI Config (Optional)

Edit `~/.claude/workflows/multi-ai-config.json` to include Ollama models in the global configuration:

```json
{
  "enabled": true,
  "workers": {
    "models": ["opus", "sonnet", "haiku", "ollama/llama3", "ollama/deepseek-coder"],
    "count": 5
  },
  "arbiter": {
    "enabled": true,
    "model": "opus"
  }
}
```

This gives you 5 workers (3 cloud + 2 local) plus 1 arbiter. Cost is only 4 API calls instead of 6 because the two Ollama workers are free.

### Step 3: Override Workers Per-Invocation

You can specify Ollama models on any individual workflow call without editing config files:

```bash
# Use Ollama models for a specific run
/code-solve 42 --workers=opus,sonnet,ollama/llama3,ollama/deepseek-coder

# All-local consensus (zero API cost for workers, only arbiter costs)
/code-review --workers=ollama/llama3,ollama/codestral,ollama/deepseek-coder
```

### Step 4: Using Ollama as Arbiter (Advanced)

For fully local operation, you can also use an Ollama model as the arbiter:

```json
{
  "enabled": true,
  "workers": {
    "models": ["ollama/llama3", "ollama/codestral", "ollama/deepseek-coder"],
    "count": 3
  },
  "arbiter": {
    "enabled": true,
    "model": "ollama/llama3:70b"
  }
}
```

Note: Using a local model as arbiter is only recommended if you have a large model (70B+) available. The arbiter needs strong reasoning to synthesize worker results. For most use cases, keep `opus` as the arbiter.

### How It Works Under the Hood

In short: when you add an `ollama/` model to your workflow, the system sends prompts to your local Ollama server instead of a cloud API. If Ollama is not running or a model is missing, that worker is silently skipped and the remaining models continue. You never need to worry about Ollama being down breaking your workflows.

Here is the step-by-step flow for those who want the technical details:

1. The workflow calls `agent(prompt, { model: 'ollama/llama3' })`.
2. The Claude Code runtime sees the `ollama/` prefix and routes the request to `http://localhost:11434` (your local Ollama API) instead of a cloud endpoint.
3. The Ollama server loads the model into GPU/CPU memory (if not already loaded) and generates a response.
4. The response comes back to the workflow in the same format as cloud model responses, so the rest of the workflow does not know or care that it came from a local model.
5. If the request fails for any reason (Ollama not running, model not downloaded, timeout), `agent()` returns `null`.
6. The workflow's `.filter(Boolean)` call automatically drops any `null` results, so the consensus continues with whichever models did respond.

This fail-safe design means you can always have Ollama models in your config -- if Ollama is not running, those workers simply produce no result and the remaining cloud models carry the consensus.

### Workflow Files to Update

Here is the complete list of workflow files that accept model configuration:

| File | Purpose | Where to Add Ollama |
|------|---------|-------------------|
| `ai-prompt.js` | Multi-model consensus | `getAvailableWorkers()` function |
| `ai-consensus.js` | Consensus helper | Worker array in parallel block |
| `code-solve.js` | Issue solving | `WORKERS` array |
| `code-solve-auto.js` | Auto issue solving | `WORKERS` array |
| `code-review.js` | Code review | Worker model list |
| `code-review-auto.js` | Auto code review | Worker model list |
| `code-pr-review.js` | PR review | Worker model list |
| `code-pr-review-auto.js` | Auto PR review | Worker model list |
| `code-security.js` | Security audit | Worker model list |
| `code-security-auto.js` | Auto security audit | Worker model list |
| `code-test.js` | Comprehensive tests | Worker model list |
| `code-test-auto.js` | Auto tests | Worker model list |
| `code-doc.js` | Documentation | Worker model list |
| `code-doc-auto.js` | Auto documentation | Worker model list |
| `code-release-notes.js` | Release notes | Worker model list |
| `code-release-notes-auto.js` | Auto release notes | Worker model list |

---

## 8. Model Strings Reference

### Format

Model strings follow the pattern: `ollama/<model-name>` or `ollama/<model-name>:<tag>`

### Complete Reference Table

| Model String | Parameters | Specialization | Speed | Quality | VRAM |
|-------------|-----------|----------------|-------|---------|------|
| `ollama/llama3` | 8B | General purpose | Fast | Good | 4 GB |
| `ollama/llama3:70b` | 70B | General purpose | Slow | Excellent | 40 GB |
| `ollama/llama3.1` | 8B | General (long context) | Fast | Good | 5 GB |
| `ollama/llama3.1:70b` | 70B | General (long context) | Slow | Excellent | 40 GB |
| `ollama/llama3.2:3b` | 3B | Fast consensus | Very Fast | Fair | 2 GB |
| `ollama/codestral` | 22B | Code generation | Medium | Very Good | 13 GB |
| `ollama/deepseek-coder` | 6.7B | Code analysis | Fast | Good | 4 GB |
| `ollama/deepseek-coder:33b` | 33B | Code analysis | Medium | Very Good | 19 GB |
| `ollama/deepseek-coder-v2` | 16B | Code (latest) | Medium | Very Good | 9 GB |
| `ollama/qwen2.5` | 7B | Multilingual | Fast | Good | 4 GB |
| `ollama/qwen2.5-coder` | 7B | Code + multilingual | Fast | Good | 4 GB |
| `ollama/qwen2.5-coder:14b` | 14B | Code + multilingual | Medium | Very Good | 9 GB |
| `ollama/mistral` | 7B | General purpose | Fast | Good | 4 GB |
| `ollama/mixtral` | 8x7B MoE | General purpose | Medium | Very Good | 26 GB |
| `ollama/phi3` | 3.8B | Compact reasoning | Very Fast | Fair | 2 GB |
| `ollama/starcoder2` | 7B | Code generation | Fast | Good | 4 GB |

### Recommended Configurations by Hardware

**Low VRAM (8 GB or less):**
```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'ollama/llama3',           // 4 GB
  'ollama/deepseek-coder',   // 4 GB (swap with llama3, not concurrent)
]
```
Note: With limited VRAM, only one Ollama model can be loaded at a time. Ollama handles model swapping automatically, but it adds latency.

**Medium VRAM (16-24 GB):**
```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'ollama/llama3',           // 4 GB
  'ollama/codestral',        // 13 GB
]
```

**High VRAM (40+ GB or multi-GPU):**
```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'ollama/llama3:70b',       // Best general reasoning
  'ollama/codestral',        // Best code analysis
  'ollama/deepseek-coder:33b', // Deep code understanding
]
```

**CPU-only (no GPU):**
```javascript
const WORKERS = [
  'opus', 'sonnet', 'haiku',
  'ollama/llama3',           // 8B runs acceptably on CPU
  // Use only one Ollama worker to avoid thrashing
]
```
Note: Expect 10-60 second response times per Ollama worker on CPU. Keep the Ollama worker count to 1. Consider `llama3.2:3b` for faster responses at the cost of some quality.

### Recommended Configurations by Use Case

**Code review (bug hunting):**
```javascript
['opus', 'sonnet', 'ollama/deepseek-coder', 'ollama/codestral']
```

**Security audit:**
```javascript
['opus', 'sonnet', 'haiku', 'ollama/llama3', 'ollama/deepseek-coder']
```

**Documentation generation:**
```javascript
['opus', 'sonnet', 'ollama/llama3', 'ollama/qwen2.5']
```

**Fast iteration (development):**
```javascript
['haiku', 'ollama/llama3.2:3b', 'ollama/phi3']
```

**Maximum consensus (production release):**
```javascript
['opus', 'sonnet', 'haiku', 'gemini', 'ollama/llama3', 'ollama/codestral', 'ollama/deepseek-coder']
```

---

## 9. Troubleshooting

### Problem: "Connection refused" when workflows try to use Ollama

**Symptom:** Worker logs show `ollama/llama3 failed: Connection refused` or similar.

**Cause:** The Ollama server is not running.

**Fix:**
```bash
# Check if Ollama is running
curl http://localhost:11434/
# If "Connection refused", start it:
sudo systemctl start ollama
# Or:
ollama serve &
```

### Problem: Model not found

**Symptom:** Error message `model 'codestral' not found` in worker output.

**Cause:** The model has not been downloaded yet.

**Fix:**
```bash
# List downloaded models
ollama list

# Pull the missing model
ollama pull codestral

# Verify
ollama list | grep codestral
```

### Problem: Out of memory (OOM) / model fails to load

**Symptom:** Ollama process crashes, system becomes unresponsive, or model returns errors about insufficient memory.

**Cause:** The model requires more VRAM (or RAM) than available.

**Fix:**
```bash
# Check available VRAM
nvidia-smi

# Use a smaller model
ollama pull llama3        # 8B instead of 70B
ollama pull deepseek-coder  # 6.7B instead of 33B

# Or use a more aggressively quantized variant (smaller file, less memory,
# slightly lower quality -- see "What Q4 Means" in section 2)
ollama pull llama3:8b-q4_0   # 4-bit quantization, smallest

# Or limit concurrent models
# Only use one Ollama worker instead of multiple
```

### Problem: Ollama responses are very slow

**Symptom:** Ollama workers take 30+ seconds to respond, causing workflow timeouts.

**Causes and fixes:**

1. **No GPU detected:** Check `nvidia-smi` or `rocm-smi`. Install CUDA/ROCm drivers. If you have no GPU, see the CPU Fallback Guidance in section 2.
2. **Model swapping:** Multiple Ollama models in the worker list cause constant model loading/unloading. Reduce to 1-2 Ollama workers.
3. **Model too large for GPU:** Part of the model runs on CPU. Use a smaller model or increase GPU layers:
   ```bash
   OLLAMA_NUM_GPU=999 ollama serve
   ```
4. **CPU-only mode:** Expected to be 5-20x slower. Use smaller models (3B-7B). See section 2 for CPU-specific recommendations.

### Problem: Ollama workers return null but no error message

**Symptom:** Workflow log shows `3/5 workers completed` but no explicit error for the failed Ollama workers.

**Cause:** This is normal behavior. The workflow's `.filter(Boolean)` silently drops failed workers. The workflow continues with available models.

**Diagnosis:**
```bash
# Test the specific model directly
ollama run llama3 "test"

# Check Ollama logs
journalctl -u ollama -n 50

# Or if running manually, check the terminal output
```

### Problem: Ollama returns malformed JSON (schema validation failures)

**Symptom:** Worker completes but the structured output is missing fields or contains invalid JSON.

**Cause:** Smaller models (3B-7B) sometimes struggle with complex JSON schemas.

**Fixes:**
1. Use larger models (14B+) for tasks requiring structured output
2. Use models specifically trained for instruction following (llama3, qwen2.5-coder)
3. Simplify the schema if possible
4. This is generally acceptable in consensus workflows -- the arbiter will ignore malformed responses

### Problem: Ollama service will not start on boot

**Symptom:** After reboot, `ollama list` fails with connection error.

**Fix:**
```bash
# Enable the systemd service
sudo systemctl enable ollama
sudo systemctl start ollama

# Verify it starts on boot
sudo systemctl is-enabled ollama
# Should output: enabled
```

### Problem: Permission denied when pulling models

**Symptom:** `ollama pull llama3` fails with permission errors.

**Cause:** The model storage directory has incorrect ownership.

**Fix:**
```bash
# If using systemd with ollama user
sudo chown -R ollama:ollama /usr/share/ollama

# If running as your own user
mkdir -p ~/.ollama
chown -R $(whoami) ~/.ollama
```

### Problem: Ollama uses too much disk space

**Symptom:** Disk space filling up from accumulated models.

**Fix:**
```bash
# List all models with sizes
ollama list

# Remove models you no longer need
ollama rm mixtral
ollama rm llama3:70b

# Check disk usage
du -sh ~/.ollama/models/
```

### Problem: Port 11434 is already in use

**Symptom:** `ollama serve` fails with "address already in use".

**Fix:**
```bash
# Find what is using the port
lsof -i :11434

# Kill the existing process
kill $(lsof -t -i :11434)

# Or use a different port
OLLAMA_HOST=0.0.0.0:11435 ollama serve
```

Note: If you change the port, you must also update any workflow configuration that references the Ollama endpoint.

### Problem: Models run slowly the first time

**Symptom:** First request to a model takes 30-60 seconds, subsequent requests are fast.

**Cause:** Ollama loads the model into VRAM on first request. This is normal and expected.

**Mitigation:**
```bash
# Pre-warm models by sending a short request before running workflows
ollama run llama3 "warmup" > /dev/null 2>&1
ollama run deepseek-coder "warmup" > /dev/null 2>&1
```

You can add this to a shell script or cron job to keep models warm.

### Problem: Workflows time out waiting for Ollama

**Symptom:** Workflow fails because Ollama workers exceed the agent timeout.

**Fix:** Pre-warm models (see above) and use appropriately sized models for your hardware. If timeouts persist, reduce the number of Ollama workers or use smaller models.

---

## Appendix A: Quick Setup Checklist

```
[ ] 1. Check hardware:            nvidia-smi (GPU) or verify 8+ GB free RAM (CPU)
[ ] 2. Verify disk space:         df -h (need ~30 GB free for core model set)
[ ] 3. Install Ollama:            curl -fsSL https://ollama.com/install.sh | sh
[ ] 4. Start the service:         sudo systemctl start ollama && sudo systemctl enable ollama
[ ] 5. Pull core models:          ollama pull llama3 && ollama pull deepseek-coder
[ ] 6. Verify working:            curl http://localhost:11434/ && ollama list
[ ] 7. Test a model:              ollama run llama3 "Hello, respond with OK"
[ ] 8. Edit workflow files:       Uncomment ollama/ models in WORKERS arrays
[ ] 9. Test in workflow:          /ai-prompt "test"
[ ] 10. (Optional) Update config: Edit multi-ai-config.json to include ollama models
```

## Appendix B: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `127.0.0.1:11434` | Address and port for the Ollama API |
| `OLLAMA_MODELS` | `~/.ollama/models` | Directory for storing model files |
| `OLLAMA_NUM_PARALLEL` | `1` | Number of concurrent model requests |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | Maximum models loaded in memory simultaneously |
| `OLLAMA_GPU_LAYERS` | auto | Number of layers to offload to GPU |
| `OLLAMA_KEEP_ALIVE` | `5m` | How long to keep a model loaded after last request |

To increase concurrent model handling (requires sufficient VRAM):

```bash
OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=2 ollama serve
```

## Appendix C: Useful Commands Reference

```bash
# Service management
ollama serve                    # Start server (foreground)
sudo systemctl start ollama     # Start via systemd
sudo systemctl stop ollama      # Stop via systemd
sudo systemctl restart ollama   # Restart via systemd
sudo systemctl status ollama    # Check status

# Model management
ollama list                     # List downloaded models
ollama pull <model>             # Download a model
ollama rm <model>               # Delete a model
ollama show <model>             # Show model details (parameters, template, license)
ollama cp <src> <dst>           # Copy/rename a model

# Running models
ollama run <model> "prompt"     # One-shot prompt
ollama run <model>              # Interactive chat

# API endpoints
curl http://localhost:11434/                          # Health check
curl http://localhost:11434/api/tags                   # List models (API)
curl http://localhost:11434/v1/chat/completions ...    # OpenAI-compatible chat
curl http://localhost:11434/api/generate ...           # Native generate
```

---

**Last Updated**: 2026-06-10
**Applicable Workflows**: All multi-AI workflows (16 total)
**Default Ollama Models**: ollama/llama3, ollama/codestral, ollama/deepseek-coder, ollama/qwen2.5-coder
**Required Ollama Version**: 0.1.0 or later
