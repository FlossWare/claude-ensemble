# Final Model & Compliance Strategy
**Date:** 2026-06-16 00:31 UTC

---

## 🎯 The Solution

### Key Insight
- `/home` is NFS-mounted from laptop-01 on ALL servers
- Disabling Ollama on laptop-01 breaks it for everyone
- **Solution:** Keep Ollama enabled, control USAGE not installation

---

## 🔐 Red Hat Compliance (laptop-01)

### For Red Hat Proprietary Code Work

**Allowed:**
- ✅ Anthropic APIs via Vertex (4 models)
  - Access via `ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-uie-eng-claude`

**NOT Allowed:**
- ❌ Ollama/local models
- ❌ OpenAI, Google, DeepSeek, etc.

**Enforcement:** MANUAL (use discipline)
- Ollama runs but DON'T use for RH code
- Only use `ANTHROPIC_VERTEX_PROJECT_ID` for RH work

---

## 🆓 Model Distribution (All FREE)

### NAS Centralized Storage (Via Autofs)

**Location:** `/mnt/nas/ai-models/ollama-from-laptop-01/`  
**Size:** 137GB (108 blobs = 20 models)  
**Access:** All machines via NFS autofs

**Current Models (FREE):**
- dolphin-llama3 (4.7 GB)
- wizard-vicuna-uncensored (3.8 GB)
- dolphin-mistral (4.1 GB)
- mistral-7b-instruct-v0.3 (4.4 GB)
- deepseek-coder-v2-lite-instruct (10 GB)
- aya-23-8b (5.1 GB)
- phi-4-mini (2.5 GB)
- c4ai-command-r-v01 (21 GB)
- phi3.5 (2.2 GB)
- mathstral:7b (4.1 GB)
- zephyr:7b (4.1 GB)
- wizardlm2:7b (4.1 GB)
- sqlcoder:7b (4.1 GB)
- starcoder2:7b (4.0 GB)
- nomic-embed-text (274 MB)
- granite-embedding (62 MB)
- gemma3:4b (3.3 GB)
- stablelm-zephyr:3b (1.6 GB)
- openchat:7b (4.1 GB)
- (1 more not shown)

---

## 🖥️ Per-Machine Configuration

| Machine | Ollama | Models Source | For RH Code? | For Personal? |
|---------|--------|---------------|--------------|---------------|
| **laptop-01** | Running | NFS `/mnt/nas` | ❌ No (APIs only) | ✅ Yes |
| **server-01** | Running | NFS `/mnt/nas` | N/A | ✅ Yes |
| **server-02** | Running | NFS `/mnt/nas` | N/A | ✅ Yes |
| **server-03** | Running | NFS `/mnt/nas` | N/A | ✅ Yes |
| **aio-01** | Running | NFS `/mnt/nas` | N/A | ✅ Yes |

**Note:** All machines use same `/mnt/nas` models via NFS autofs

---

## 💾 Storage Analysis

### Why NFS?

**Before (downloading to each server):**
- server-01: 4.1GB free (100% full) ❌
- server-02: Would use 137GB local
- server-03: Would use 137GB local
- **Total:** 274GB + downloads

**After (NFS from NAS):**
- server-01: 0GB used (reads from NAS) ✅
- server-02: 0GB used (reads from NAS) ✅
- server-03: 0GB used (reads from NAS) ✅
- NAS: 137GB (already there!)
- **Total:** 137GB shared, no downloads needed

**Savings:** 274GB local storage + no internet downloads

---

## 🚀 Adding New Models

### To add models (affects ALL machines):

```bash
# Option 1: Download to NAS (from any machine)
ssh server-01  # or any server
ollama pull llama3.3:70b
# Automatically goes to /mnt/nas (shared by all)

# Option 2: Copy from NAS backup
ssh root@server-01
rsync -av /mnt/nas/ai-models/gguf/ /mnt/nas/ai-models/ollama-from-laptop-01/
```

**All machines** instantly see new models (shared NFS).

---

## 🔧 Ollama Configuration

### Current Setup (Correct)

All servers already configured via NFS autofs:
- Ollama reads from `/mnt/nas/ai-models/ollama-from-laptop-01/`
- No systemd override needed (autofs handles it)
- 108 blobs accessible to all

### To Verify

```bash
# On any server
ollama list | wc -l  # Should show 20
ls /mnt/nas/ai-models/ollama-from-laptop-01/blobs | wc -l  # Should show 108
```

---

## 📋 Red Hat Compliance Checklist (laptop-01)

When working on Red Hat proprietary code:

- [ ] Use ONLY Anthropic APIs (Vertex)
- [ ] Set `ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-uie-eng-claude`
- [ ] Do NOT use `ollama run` commands
- [ ] Do NOT use Groq, OpenRouter, etc.
- [ ] OK to use for personal projects

**For personal code (non-RH):**
- [x] Use any FREE models
- [x] Use Ollama, Groq, OpenRouter, etc.
- [x] No restrictions

---

## 🆓 FREE API Summary

**Cloud APIs (configured in ~/.bashrc):**
1. Groq - 500+ tok/s
2. OpenRouter - Multi-model
3. Cerebras - Fast inference
4. DeepSeek - Code generation
5. Cloudflare Workers AI - Edge inference

**Local Models (via NFS):**
- 20 models (137GB) on `/mnt/nas`
- Shared across all 5 machines
- Zero download, zero local storage

**Total Cost:** $0.00/month

---

## 📝 Summary

✅ **NFS model sharing working via autofs**  
✅ **137GB models accessible to all servers**  
✅ **Zero local storage used**  
✅ **Ollama enabled (needed for NFS /home access)**  
✅ **Red Hat compliance: Manual discipline on laptop-01**  
✅ **5 FREE cloud APIs configured**  
✅ **20 FREE local models via NFS**

**No additional downloads needed** - 225GB already on NAS!
