# FREE LLM API Configuration

**Date**: 2026-06-12  
**Status**: ✅ ALL WORKING  
**Cost**: $0 Forever

---

## 🚀 Deployed APIs

### 1. Cerebras (14,400 req/day)
- **Models**: 
  - gpt-oss-120b (120B parameters) ⭐ PRIMARY
  - zai-glm-4.7 (alternative)
- **Endpoint**: https://api.cerebras.ai/v1/chat/completions
- **Key**: `CEREBRAS_API_KEY` (in .bashrc)
- **Limits**: 
  - 5 req/min
  - 150 req/hour
  - 2,400 req/day (14,400 across 3 models)
  - 30K tokens/min

### 2. Cloudflare Workers AI (10,000 req/day)
- **Working Models** (6 tested):
  - @cf/meta/llama-3.2-1b-instruct (1B, fast, basic)
  - @cf/meta/llama-3.2-3b-instruct (3B, fast, better)
  - @cf/qwen/qwen2.5-coder-32b-instruct (32B) ⭐ **CODE SPECIALIST**
  - @cf/mistralai/mistral-small-3.1-24b-instruct (24B)
  - @cf/qwen/qwen3-30b-a3b-fp8 (30B, efficient)
  - @cf/meta/llama-3.3-70b-instruct-fp8-fast (70B) ⭐ **LARGE & FAST**
- **Endpoint**: https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{MODEL}
- **Keys**: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_KEY` (in .bashrc)
- **Limits**: 10,000 Neurons/day

### 3. OpenRouter (200 req/day, 26+ models)
- **Best FREE models**:
  - nvidia/nemotron-3-ultra-550b-a55b:free (550B params!) ⭐⭐⭐ **LARGEST**
  - nvidia/nemotron-3-super-120b-a12b:free (120B params)
  - qwen/qwen3-next-80b-a3b-instruct:free (80B params)
  - google/gemma-4-31b-it:free (31B params)
  - google/gemma-4-26b-a4b-it:free (26B params)
  - openai/gpt-oss-120b:free (120B params)
  - + 20 more free models
- **Endpoint**: https://openrouter.ai/api/v1/chat/completions
- **Key**: `OPENROUTER_API_KEY` (in .bashrc)
- **Limits**: 20 req/min, 200 req/day

---

## 🖥️ Fleet Deployment

| Server | CPU | RAM | Role | APIs | Status |
|--------|-----|-----|------|------|--------|
| **laptop-01** | ? | **31GB** | Development/ChromaDB | 3/3 | ✅ WORKING |
| **aio-01** | 2C | **8GB** | Controller/Orchestration | 3/3 | ✅ WORKING |
| **server-01** | 8C | **15GB** | Worker | 3/3 | ✅ WORKING |
| **server-02** | 8C | **23GB** | Worker | 3/3 | ✅ WORKING |
| **server-03** | 8C | **31GB** | Worker | 3/3 | ✅ WORKING |

**Total Fleet Capacity**: 123,000 req/day  
**Total Fleet RAM**: ~108GB

---

## 🏆 Best Models for Code

| Rank | Model | Size | Platform | Daily Limit | Best For |
|------|-------|------|----------|-------------|----------|
| 🥇 | **Qwen 2.5 Coder** | 32B | Cloudflare | 10,000 | Code generation, debugging |
| 🥈 | **Llama 3.3 70B Fast** | 70B | Cloudflare | 10,000 | Large code analysis, fast |
| 🥉 | **GPT-OSS-120B** | 120B | Cerebras | 14,400 | Architecture, deep analysis |
| 4 | **Qwen3 Next 80B** | 80B | OpenRouter | 200 | Complex reasoning |
| 5 | **Nemotron 3 Ultra** | 550B | OpenRouter | 200 | Massive analysis (limited) |

---

## 💻 Best Servers for Code Tasks

| Server | RAM | CPU | Recommendation | Use For |
|--------|-----|-----|----------------|---------|
| **laptop-01** | 31GB | ? | 🥇 **BEST** | Heavy tasks, ChromaDB, development |
| **server-03** | 31GB | 8C | 🥇 **BEST** | Heavy tasks, dedicated worker |
| **server-02** | 23GB | 8C | 🥈 **EXCELLENT** | Large projects |
| **server-01** | 15GB | 8C | 🥉 **VERY GOOD** | Medium projects |
| **aio-01** | 8GB | 2C | **GOOD** | Light tasks, orchestration |

---

## 🗄️ Vector Database (ChromaDB)

### Current Setup
- **Location**: `~/claude-global-skills/knowledge/chromadb`
- **Platform**: ChromaDB v1.5.9 (SQLite-backed)
- **Host**: laptop-01 (31GB RAM)
- **Storage**: NFS-shared (accessible from all servers)
- **Current Size**: 14 vectors in 2 collections
- **Capacity**: 5-10 million vectors

### Collections
- `code-learning-code`: 6 vectors (code snippets)
- `code-learning-nl`: 8 vectors (natural language descriptions)

### Capacity Estimates (laptop-01, 31GB RAM)
- Conservative: 2-3M vectors
- Optimized: 5-10M vectors
- Target for "repos galore + PDFs": 150K-350K vectors (3-10% capacity)

---

## 📦 Ingestion Tools

### Created Scripts
All located in: `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/`

1. **ingest-github-repos.sh** - Clone & ingest GitHub repositories
   ```bash
   ./ingest-github-repos.sh repos.txt
   ./ingest-github-repos.sh https://github.com/user/repo
   ```

2. **ingest-codebase.sh** - Ingest local codebases
   ```bash
   ./ingest-codebase.sh /path/to/repo
   ```

3. **ingest-pdfs.sh** - Ingest PDF documents
   ```bash
   ./ingest-pdfs.sh /path/to/pdfs/
   ```

4. **example-repos.txt** - Sample list of 23 popular repos to start

### Features
- Automatic chunking (2KB pieces)
- Progress logging with colors
- Metadata tracking (file, repo, extension, chunk)
- Skips common junk (node_modules, .git, venv)
- Updates existing repos (git pull)
- Error handling & reporting

---

## 🧪 Testing

### Test All APIs on Current Server
```bash
bash /tmp/test-all-apis-fixed.sh
```

### Test Individual APIs

**OpenRouter:**
```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it:free","messages":[{"role":"user","content":"Hi"}]}'
```

**Cerebras:**
```bash
curl https://api.cerebras.ai/v1/chat/completions \
  -H "Authorization: Bearer ${CEREBRAS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"Hi"}]}'
```

**Cloudflare (Llama 3.2 1B):**
```bash
curl https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.2-1b-instruct \
  -H "Authorization: Bearer ${CLOUDFLARE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hi"}]}'
```

**Cloudflare (Qwen 2.5 Coder - Code Tasks):**
```bash
curl https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/qwen/qwen2.5-coder-32b-instruct \
  -H "Authorization: Bearer ${CLOUDFLARE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Write a Python function to reverse a string"}]}'
```

---

## 📊 Usage in Multi-AI Workflows

These APIs can be integrated into consensus workflows as additional workers:

```javascript
// In workflows: add to worker list
const workers = [
  'fable',
  'opus', 
  'sonnet',
  'haiku',
  'gpt-4o',
  'gemini',
  // NEW FREE APIS:
  'cerebras-120b',      // 120B, 14.4k/day
  'openrouter-550b',    // 550B, 200/day (MASSIVE!)
  'cloudflare-qwen',    // 32B code specialist, 10k/day
  'cloudflare-70b'      // 70B fast, 10k/day
];
```

---

## 🔑 API Keys Location

All keys stored in: `~/.bashrc`  
(Symlinked to: `~/Development/redhat/scm/gitlab/cee/sfloess/config/bashrc`)

```bash
export CEREBRAS_API_KEY='csk-your-cerebras-api-key-here'
export CLOUDFLARE_ACCOUNT_ID='your-cloudflare-account-id-here'
export CLOUDFLARE_API_KEY='cfat_your-cloudflare-api-key-here'
export OPENROUTER_API_KEY='sk-or-v1-your-openrouter-api-key-here'
```

---

### 4. Groq (14,400 req/day) ✅ WORKING
- **Models** (16 total):
  - groq/compound (131K context)
  - groq/compound-mini (131K context)
  - llama-3.3-70b-versatile (131K context, 32K output) ⭐ **BEST**
  - llama-3.1-8b-instant (131K context, ultra-fast)
  - meta-llama/llama-4-scout-17b-16e-instruct (131K context)
  - openai/gpt-oss-120b (131K context)
  - openai/gpt-oss-20b (131K context)
  - qwen/qwen3-32b (131K context)
  - whisper-large-v3-turbo (audio transcription)
  - + 7 more models
- **Endpoint**: https://api.groq.com/openai/v1/chat/completions
- **Key**: `GROQ_API_KEY` (in .bashrc)
- **Limits**: 
  - 30 req/min
  - 14,400 req/day
  - Ultra-fast LPU inference (500+ tokens/sec)

**Status**: ✅ Previously had OAuth issues, now WORKING with API key

---

## 📦 Local AI Engines (35 models - $0 cost)

### 1. Ollama (12 models)
- **Location**: Installed on all 5 fleet nodes
- **Models**:
  - starcoder2:7b, sqlcoder:7b, openchat:7b (code)
  - mathstral:7b (reasoning)
  - phi3.5, wizardlm2:7b, zephyr:7b, gemma3:4b, stablelm-zephyr:3b (general)
  - nomic-embed-text, granite-embedding (embeddings)
- **Access**: SSH-based via `shared/ollama-client.js`
- **Status**: ✅ Fully integrated

### 2. LocalAI (3 GGUF models)
- **Location**: server-01/02/03 (`~/.local/share/localai/models/`)
- **Models**:
  - gemma-2-2b.gguf
  - phi-2.gguf
  - qwen-coder-7b.gguf
- **Status**: ⚠️ Installed but service not running
- **Action**: Start LocalAI service to activate

### 3. llama.cpp (20 GGUF models)
- **Location**: `~/ai-models/gguf/` (laptop-01)
- **Models**:
  - **Large (27B-70B)**: gemma-2-27b-q4, llama-3.3-70b-q4, mixtral-8x7b-q4
  - **Code (14B-32B)**: qwen2.5-coder-32b-q4, codestral-22b-q4, deepseek-coder-v2-lite-q4
  - **Reasoning (14B-32B)**: qwq-32b-q4, deepseek-r1-distill-qwen-14b/32b-q4
  - **General (7B-14B)**: llama-3.1-8b-q4, mistral-7b-instruct-q4, qwen2.5-14b-instruct-q4
  - **Specialized**: phi-4-mini-q4, hermes-3-llama-3.1-8b-q4, orca-2-13b-q4
  - **Chat**: mistral-nemo-instruct-2407-q4, c4ai-command-r-v01-q4, aya-23-8b-q4, yi-1.5-9b-chat-q4
- **Engine**: `/usr/local/lib/ollama/llama-server`
- **Status**: ✅ Ready (files present, server available)
- **Action**: Need integration script (like ollama-client.js)

### 4. Podman AI Lab (Red Hat)
- **Location**: Port 10434 (laptop-01)
- **Service**: `podman-ai-lab.service`
- **Status**: ⚠️ Installed but not running (auto-restart loop)
- **Action**: Debug service startup

### 5. OpenClaw (Execution Verification Agent)
- **Location**: Port 18789
- **Client**: `shared/openclaw-client.js`
- **Purpose**: Code execution verification worker
- **Status**: ✅ Integrated in consensus-engine.js
- **Action**: Start daemon when needed

---

## 🎯 Complete Summary

**Cloud FREE APIs (4 providers):**
✅ **Cerebras** - 3 models, 14,400 req/day  
✅ **Cloudflare** - 6+ models, 10,000 req/day  
✅ **OpenRouter** - 26+ FREE models, 200 req/day  
✅ **Groq** - 16 models, 14,400 req/day ⭐ **ULTRA-FAST (500+ tok/s)**

**Local AI Engines (5 platforms, 35 models):**
✅ **Ollama** - 12 models (active, all nodes)  
⚠️ **LocalAI** - 3 models (installed, not running)  
✅ **llama.cpp** - 20 GGUF models (ready, needs client)  
⚠️ **Podman AI Lab** - TBD models (service issue)  
✅ **OpenClaw** - 1 agent (execution verification)

**Grand Total:**
- **Cloud**: 45+ FREE models, 38,600 req/day
- **Local**: 35 models, unlimited usage
- **TOTAL**: **80+ FREE models**
- **Cost**: **$0 forever**
- **Servers**: 5 (laptop-01, server-01/02/03, aio-01)
- **Fleet RAM**: ~108GB
- **ChromaDB**: 5-10M vector capacity

**Performance Highlights:**
- ⚡ **Groq**: 500+ tokens/sec (fastest)
- 🧠 **OpenRouter**: 550B Nemotron (largest)
- 💻 **llama.cpp**: 70B local models
- 📊 **Total capacity**: 38,600 cloud req/day + unlimited local

---

## 📈 Next Steps (When Ready)

1. **Ingest GitHub Repos:**
   ```bash
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   ./ingest-github-repos.sh example-repos.txt
   ```

2. **Ingest PDFs:**
   ```bash
   ./ingest-pdfs.sh ~/Downloads/
   ```

3. **Query Your Data:**
   ```python
   import chromadb
   client = chromadb.PersistentClient(path="./knowledge/chromadb")
   collection = client.get_collection("code-myrepo")
   results = collection.query(query_texts=["authentication"], n_results=5)
   ```

4. **Use FREE APIs for RAG:**
   - Query ChromaDB for relevant code/docs
   - Send to Cerebras/Cloudflare/OpenRouter
   - Get AI-powered answers using YOUR data
