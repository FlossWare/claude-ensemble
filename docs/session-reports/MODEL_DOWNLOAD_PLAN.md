# Model Download Execution Plan
**Created:** 2026-06-16 00:13 UTC  
**Purpose:** Download ALL models to server-03, keep only Red Hat approved on laptop-01

---

## 🎯 Strategy

### server-03 (ALL models)
- **Storage:** `/exports/ollama/models`
- **Models:** 150+ models (~500GB)
- **Purpose:** Central model repository for entire fleet

### laptop-01 (Red Hat approved ONLY)
- **Storage:** `~/.ollama/models` (local)
- **Models:** 22 Red Hat approved (Anthropic 4 + Local 18)
- **Purpose:** Work on Red Hat proprietary code safely

---

## 📋 Execution Steps

### Step 1: Fix SSH Access to server-03

```bash
# Test current access
ssh server-03 "hostname"

# If fails, copy SSH key
ssh-copy-id server-03

# Or manually
cat ~/.ssh/id_rsa.pub | ssh server-03 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Step 2: Configure server-03 Ollama

```bash
# SSH into server-03
ssh server-03

# Create /exports directory
sudo mkdir -p /exports/ollama/models
sudo chown ollama:ollama /exports/ollama/models

# Configure Ollama to use /exports
sudo mkdir -p /etc/systemd/system/ollama.service.d/
cat <<EOF | sudo tee /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_MODELS=/exports/ollama/models"
EOF

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl status ollama

# Verify
echo $OLLAMA_MODELS
ollama list
```

### Step 3: Download ALL Models to server-03

**Script:** `/tmp/download-all-models-server03.sh`

```bash
# Run from laptop-01 (after fixing SSH)
/tmp/download-all-models-server03.sh
```

**Models to download (150+):**
- Code generation: codellama, codestral, qwen2.5-coder, starcoder2, etc.
- Large LLMs: llama3.3:70b, llama3.1:405b, mixtral:8x7b, etc.
- Math/reasoning: deepseek-math, qwen2-math, qwq, wizard-math
- Vision: llava, llama3.2-vision, minicpm-v, qwen3-vl
- Specialized: OCR, safety, embeddings

**Estimated:**
- Time: 8-12 hours (parallel downloads, 3 at a time)
- Storage: ~500-700GB
- Bandwidth: Heavy (consider running overnight)

### Step 4: Install Red Hat Approved Models on laptop-01

**Script:** `/tmp/install-redhat-approved-laptop01.sh`

```bash
# Run on laptop-01
/tmp/install-redhat-approved-laptop01.sh
```

**Models (22 approved):**

**Anthropic (4) - via Vertex AI:**
- claude-fable-5
- claude-opus-4-8
- claude-sonnet-4-6
- claude-haiku-4-5

**Local Ollama (18):**
- Small/fast: phi3.5:3.8b, gemma3:4b, stablelm-zephyr:3b, tinyllama:1.1b
- Code: deepseek-coder-v2-lite, codestral:22b, qwen2.5-coder:7b, starcoder2:7b
- General: mistral-7b, dolphin-mistral, zephyr:7b, wizardlm2:7b
- Embeddings: nomic-embed-text, granite-embedding
- Currently installed: dolphin-llama3, wizard-vicuna-uncensored, aya-23-8b, phi-4-mini

**Storage:** ~50-70GB (much smaller than server-03)

---

## 🔧 Configuration Files

### server-03 Ollama Config

**File:** `/etc/systemd/system/ollama.service.d/override.conf`
```ini
[Service]
Environment="OLLAMA_MODELS=/exports/ollama/models"
```

### laptop-01 Environment (Red Hat Compliance)

**File:** `~/.bashrc`
```bash
# Red Hat AI Compliance - Local models only for RH code
export OLLAMA_MODELS=~/.ollama/models  # Local storage
export REDHAT_APPROVED_ONLY=1          # Flag for scripts
```

**File:** `~/.ollama/REDHAT_COMPLIANCE.txt`
```
RED HAT AI COMPLIANCE
=====================
These models are APPROVED for Red Hat proprietary code:
- Anthropic (4): Fable, Opus, Sonnet, Haiku (via Vertex)
- Local (18): All Ollama models installed here

PROHIBITED:
- OpenAI, Google Cloud, DeepSeek Cloud, etc.
```

---

## 🌐 Fleet Access to server-03 Models

Once server-03 has all models, other machines can access them:

```bash
# From any machine (server-01, server-02, aio-01, pi-02)
export OLLAMA_HOST=http://server-03:11434
ollama list
ollama run llama3.3:70b "Hello"
```

**Benefits:**
- Central model repository
- No need to download on every machine
- Save ~500GB per machine
- Faster than NFS (direct HTTP)

---

## 📊 Storage Breakdown

| Machine | Storage | Models | Purpose |
|---------|---------|--------|---------|
| **server-03** | `/exports` (500-700GB) | 150+ ALL models | Central repository |
| **laptop-01** | `~/.ollama` (50-70GB) | 22 RH approved | Red Hat work |
| **server-01** | Remote access | 0 (use server-03) | Access via HTTP |
| **server-02** | Remote access | 0 (use server-03) | Access via HTTP |
| **aio-01** | Remote access | 0 (use server-03) | Access via HTTP |

**Total Fleet Storage:** ~550GB (vs ~3TB if every machine had all models)

---

## ✅ Verification

### After server-03 setup:
```bash
ssh server-03 "
    ollama list | wc -l  # Should show 150+
    du -sh /exports/ollama/models  # Should show ~500GB
    ls -lh /exports/ollama/models
"
```

### After laptop-01 setup:
```bash
ollama list | wc -l  # Should show 18-22
cat ~/.ollama/REDHAT_COMPLIANCE.txt
du -sh ~/.ollama/models  # Should show ~50-70GB
```

### Test remote access:
```bash
# From server-01
export OLLAMA_HOST=http://server-03:11434
ollama list | head -20
ollama run qwen2.5-coder:32b "Write a Python function"
```

---

## 🚨 Important Notes

### Red Hat Compliance
- **laptop-01** is for Red Hat proprietary code work
- ONLY use Anthropic (4) + Local Ollama (18) models
- NEVER use OpenAI, Google Cloud, DeepSeek Cloud, etc.
- Fine-tuning datasets for RH code: LOCAL models ONLY

### server-03 Considerations
- `/exports` must have 500-700GB free space
- Download will take 8-12 hours (run overnight)
- Check bandwidth limits (residential internet?)
- Models download in parallel (3 concurrent by default)

### Network Performance
- **server-03 HTTP access:** Fast, direct connection
- **NAS/NFS access:** Slower, 3-hop path for laptop-01
- **Recommendation:** Use server-03 HTTP for remote access

---

## 📝 Next Steps

1. **Fix SSH access to server-03**
   ```bash
   ssh-copy-id server-03
   ```

2. **Verify /exports space**
   ```bash
   ssh server-03 "df -h /exports"
   ```

3. **Run server-03 download** (overnight)
   ```bash
   /tmp/download-all-models-server03.sh &
   disown
   ```

4. **Install laptop-01 Red Hat approved models**
   ```bash
   /tmp/install-redhat-approved-laptop01.sh
   ```

5. **Update fleet configs** to point to server-03
   ```bash
   # Add to ~/.bashrc on server-01/02, aio-01
   export OLLAMA_HOST=http://server-03:11434
   ```

---

**Estimated Timeline:**
- SSH setup: 5 minutes
- server-03 config: 10 minutes
- server-03 downloads: 8-12 hours (overnight)
- laptop-01 installs: 1-2 hours
- Fleet config updates: 15 minutes

**Total:** ~10-14 hours (mostly automated downloads)

---

**Files Created:**
- `/tmp/download-all-models-server03.sh` - Download script
- `/tmp/install-redhat-approved-laptop01.sh` - Install script
- This document: `~/MODEL_DOWNLOAD_PLAN.md`
