# FREE Local AI Vendors - Complete Setup
**Date:** 2026-06-16 00:42 UTC

## 🎯 Strategy Summary

**NAS Central Storage:** All models on `/mnt/nas/ai-models/`
**Server Distribution:**
- server-01: text-generation-webui (web UI)
- server-02: vLLM (high-performance API)
- server-03: LocalAI (OpenAI-compatible API)

**All vendors use NFS models from NAS** - zero duplication!

---

## 📦 Current Models on NAS (88GB GGUF)

✅ **Already Available:**
1. llama-3.3-70b-q4 (40GB) - Best overall
2. mixtral-8x7b-q4 (25GB) - MoE, fast
3. gemma-2-27b-q4 (16GB) - Google
4. llama-3.1-8b-q4 (4.6GB) - Fast
5. mistral-7b (578MB) - Lightweight
6. phi-3-mini (159MB) - Tiny, fast

---

## 🚀 Missing Uncensored Models

Based on session history, you wanted these **uncensored** models:

### To Download to NAS:
```bash
# On any server (auto-saves to /mnt/nas via Ollama NFS config)
ollama pull dolphin-llama3:latest
ollama pull wizard-vicuna-uncensored:latest
ollama pull dolphin-mistral:latest
ollama pull nous-hermes-uncensored:latest
ollama pull samantha-mistral:latest

# These go to /mnt/nas/ai-models/ollama-from-laptop-01/
# Already shared across all servers!
```

These are **already in Ollama format** on NAS (137GB). Need GGUF versions?

---

## 🛠️ Vendor Setup Commands

### 1. LocalAI (server-03) - ✅ INSTALLED
```bash
# Already installed on server-03
# Binary at: /usr/local/bin/local-ai
# Models from: /mnt/nas/ai-models/gguf/

# Start manually:
ssh server-03 "MODELS_PATH=/mnt/nas/ai-models/gguf local-ai"

# API: http://server-03:8080/v1/
```

### 2. text-generation-webui (server-01)
```bash
cd /tmp
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui
./start_linux.sh --model-dir /mnt/nas/ai-models/gguf

# Web UI: http://server-01:7860
```

### 3. vLLM (server-02)
```bash
pip3 install vllm
vllm serve /mnt/nas/ai-models/gguf/llama-3.3-70b-q4.gguf \
  --host 0.0.0.0 --port 8000

# API: http://server-02:8000/v1/
```

### 4. llamafile (Any server)
```bash
# Convert GGUF to llamafile executable
curl -Lo llamafile https://github.com/Mozilla-Ocho/llamafile/releases/download/0.8.13/llamafile-0.8.13
chmod +x llamafile

# Run any GGUF model
./llamafile -m /mnt/nas/ai-models/gguf/llama-3.3-70b-q4.gguf
```

---

## 📥 Download Missing Uncensored Models

All commands download to NAS automatically (NFS-shared):
```bash
# Uncensored models (Ollama format - already configured for NAS)
ssh server-01 "
  ollama pull dolphin-llama3
  ollama pull wizard-vicuna-uncensored  
  ollama pull nous-hermes-uncensored
  ollama pull samantha-mistral
"

# GGUF uncensored versions (for LocalAI/vLLM/webui)
ssh server-01 "
  cd /mnt/nas/ai-models/gguf/
  # Dolphin LLaMA 3 70B GGUF
  curl -Lo dolphin-llama3-70b-q4.gguf https://huggingface.co/cognitivecomputations/dolphin-2.9.4-llama3.1-70b-GGUF/resolve/main/dolphin-2.9.4-llama3.1-70b-Q4_K_M.gguf
  
  # Wizard Vicuna Uncensored 13B
  curl -Lo wizard-vicuna-13b-uncensored-q4.gguf https://huggingface.co/TheBloke/Wizard-Vicuna-13B-Uncensored-GGUF/resolve/main/wizard-vicuna-13b-uncensored.Q4_K_M.gguf
"
```

