# Model Downloads & Installation Inventory
**Generated:** 2026-06-16 00:08 UTC  
**Purpose:** Complete record of all models downloaded/planned across sessions

---

## 📊 Summary

- **Currently Installed (Ollama):** 20 models (65GB total)
- **Planned/Mentioned in Sessions:** 150+ models
- **Fine-Tuned Models (Planned):** 3 (deepseek-coder-java, phi-4-mini-routing, mistral-arbiter)
- **HuggingFace Downloads:** 3 attempted (microsoft/phi-4, deepseek-ai/deepseek-coder-6.7b, mistralai/Mistral-7B)

---

## ✅ Currently Installed (Ollama - Local)

| Model | Size | Modified | Purpose |
|-------|------|----------|---------|
| **dolphin-llama3** | 4.7 GB | 5 hours ago | General purpose, uncensored |
| **wizard-vicuna-uncensored** | 3.8 GB | 5 hours ago | General assistant |
| **dolphin-mistral** | 4.1 GB | 5 hours ago | General purpose |
| **mistral-7b-instruct-v0.3** | 4.4 GB | 8 hours ago | Code/reasoning |
| **deepseek-coder-v2-lite-instruct** | 10 GB | 8 hours ago | Code generation |
| **aya-23-8b** | 5.1 GB | 8 hours ago | Multilingual |
| **phi-4-mini** | 2.5 GB | 8 hours ago | Fast routing |
| **c4ai-command-r-v01** | 21 GB | 9 hours ago | Long context |
| **phi3.5** | 2.2 GB | 36 hours ago | Microsoft Phi |
| **mathstral:7b** | 4.1 GB | 2 days ago | Math reasoning |
| **zephyr:7b** | 4.1 GB | 2 days ago | Chat assistant |
| **wizardlm2:7b** | 4.1 GB | 2 days ago | Wizard family |
| **sqlcoder:7b** | 4.1 GB | 2 days ago | SQL generation |
| **starcoder2:7b** | 4.0 GB | 2 days ago | Code completion |
| **nomic-embed-text** | 274 MB | 2 days ago | Embeddings |
| **granite-embedding** | 62 MB | 2 days ago | IBM Granite embeddings |
| **gemma3:4b** | 3.3 GB | 2 days ago | Google Gemma |
| **stablelm-zephyr:3b** | 1.6 GB | 2 days ago | Lightweight chat |
| **openchat:7b** | 4.1 GB | 3 days ago | Open chat model |

**Total:** ~65 GB

---

## 🔄 Fine-Tuning Pipeline (Ready to Execute)

**Location:** `~/fine-tuning/`  
**Status:** Scripts created, NOT started  
**Strategy:** CPU fine-tuning with QDoRA + D2Z scheduler

### 1. phi-4-mini-routing (Priority 1)
- **Base Model:** microsoft/phi-4
- **Purpose:** Thompson Sampling routing optimizer
- **Dataset:** 500 synthetic routing decisions
- **Duration:** 2-3 hours
- **Output:** `phi-4-mini-routing:finetuned`

### 2. deepseek-coder-java (Priority 2)
- **Base Model:** deepseek-ai/deepseek-coder-6.7b-instruct
- **Purpose:** Java/Salesforce code specialist
- **Dataset:** 923 examples from 48,417 Java files
- **Duration:** 4-6 hours
- **Output:** `deepseek-coder-java:finetuned`

### 3. mistral-arbiter (Priority 3)
- **Base Model:** mistralai/Mistral-7B-Instruct-v0.3
- **Purpose:** Local multi-AI arbiter (diversity protection)
- **Dataset:** 300 consensus patterns (reward > 0.75)
- **Duration:** 3-4 hours
- **Output:** `mistral-arbiter:finetuned`

**Total Time:** ~10 hours (sequential on laptop-01)

---

## 📥 Planned Downloads (From Sessions)

### Code Generation Models
- codellama, codellama-13b, codellama-34b
- codestral:22b
- granite-code:20b, granite-code:34b, granite-code:8b
- qwen2.5-coder, qwen2.5-coder:14b, qwen2.5-coder:32b
- starcoder2, starcoder2:15b
- wizardcoder, wizardcoder:34b
- sqlcoder:15b
- yi-coder:9b

### Math/Reasoning Models
- deepseek-math
- qwen2-math:72b
- qwq:32b
- wizard-math:70b

### Large Context Models
- llama3.1:405b
- llama3.3:70b
- command-r:35b
- command-r-plus:104b
- mistral-large-3:123b
- mistral-large-3:675b

### Vision Models
- llama3.2-vision:11b, llama3.2-vision:90b
- llava:13b, llava:34b
- minicpm-v:8b
- qwen3-vl:32b
- moondream:1.8b

### Specialized Models
- deepseek-ocr:3b
- glm-ocr
- reader-lm:1.5b
- bespoke-minicheck:7b (verification)
- shieldgemma:27b (safety)
- llama-guard3:8b (content moderation)

### Cutting-Edge Models
- deepseek-r1:14b, deepseek-r1:32b
- deepseek-v3:671b
- deepseek-v4-flash, deepseek-v4-pro
- cogito-2.1:671b
- devstral-2:123b
- kimi-k2.6, kimi-k2.7-code
- minimax-m2.7, minimax-m3
- nemotron-3-ultra:550b
- qwen3:235b, qwen3-coder-next

### Embedding Models
- bge-m3
- mxbai-embed-large
- snowflake-arctic-embed2

---

## 🗂️ Custom Models Created

From `ollama create` commands found in sessions:

- **deepseek-coder-java:finetuned** - Java specialist (planned)
- **deepseek-debugger:14b** - Debugging specialist
- **deepseek-myproject** - Project-specific variant
- **llama-3.3-70b-local** - Local LLaMA variant
- **mistral-arbiter:finetuned** - Consensus arbiter (planned)
- **phi-4-mini-routing:finetuned** - Routing optimizer (planned)
- **qwen-custom** - Custom Qwen variant
- **qwen-mycode:7b** - Code-specific Qwen
- **qwen-myproject:7b** - Project-specific Qwen
- **wizard-mydomainn:70b** - Domain-specific Wizard

---

## 📊 Model Distribution by Type

### By Size
- **Tiny (<2GB):** 4 models (stablelm, phi, gemma, embeddings)
- **Small (2-5GB):** 11 models (phi-4, dolphin variants, mistral, etc.)
- **Medium (5-15GB):** 4 models (aya, deepseek-coder, etc.)
- **Large (15-30GB):** 1 model (command-r)
- **XL (30GB+):** 0 currently installed

### By Purpose
- **Code Generation:** 4 models (deepseek-coder, starcoder2, sqlcoder, etc.)
- **General Chat:** 6 models (dolphin variants, wizard, openchat, etc.)
- **Math/Reasoning:** 2 models (mathstral, zephyr)
- **Embeddings:** 2 models (nomic, granite)
- **Specialized:** 6 models (phi-4-mini for routing, multilingual, etc.)

---

## 🎯 Recommended Next Downloads

Based on analysis of sessions and usage patterns:

### High Priority (for local fleet)
1. **llama3.3:70b** - Best open-source LLM, multi-purpose
2. **qwen2.5-coder:32b** - Code generation powerhouse
3. **deepseek-r1:32b** - Reasoning specialist
4. **mixtral-8x7b** - MoE architecture, efficient

### Medium Priority (for specialized tasks)
5. **llava:34b** - Vision tasks
6. **granite-code:20b** - IBM's code model
7. **wizardlm2:8x22b** - Large MoE for complex tasks
8. **command-r-plus:104b** - Ultra long context

### Low Priority (nice to have)
9. **hermes3:70b** - Alternative general model
10. **yi:34b** - Another option for comparison

---

## 💾 Storage Planning

### Current Usage
- **Local (laptop-01):** 65 GB Ollama models
- **NAS (/mnt/nas/models/):** Ollama blobs/manifests
- **PostgreSQL:** 1,168 execution logs tracking model performance

### Recommended Storage Strategy
1. **Keep on laptop-01 (local disk):** 
   - Frequently used models (current 20)
   - Fast models for routing (<5GB)
   - Embeddings models (<1GB)

2. **Store on NAS (/mnt/nas/ollama/models):**
   - Large models (>20GB)
   - Infrequently used models
   - Fine-tuned checkpoints

3. **Archive to NAS:**
   - Old model versions
   - Experimental fine-tunes
   - Backups before cleanup

---

## 🔄 Model Updates Detected

Recent pulls (last 8 hours):
- mistral-7b-instruct-v0.3
- deepseek-coder-v2-lite-instruct
- aya-23-8b
- phi-4-mini
- c4ai-command-r-v01

These suggest active testing of:
- Code generation improvements (deepseek-coder-v2)
- Fast routing experiments (phi-4-mini)
- Multilingual support (aya-23)
- Long context handling (command-r)

---

## 📝 Notes

- Many models mentioned but not downloaded (150+ planned vs 20 installed)
- Fine-tuning pipeline ready but not executed
- HuggingFace downloads attempted but may have failed (check logs)
- Custom Ollama models created via `ollama create` (qwen variants, etc.)

---

## 🔗 Related Documents

- `~/fine-tuning/README.md` - Fine-tuning pipeline documentation
- `~/INTEGRATIONS_INVENTORY.md` - API keys and integrations
- `~/.claude/model-config.json` - Model registry and strategies
- `/mnt/nas/claude-backups/LATEST/` - Latest backup with model state

---

**Last Updated:** 2026-06-16 00:08 UTC
