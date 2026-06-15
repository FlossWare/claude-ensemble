# Multi-Vendor Model Download - Quick Start

## TL;DR

Download AI models from ANY vendor to your NAS:

```bash
# Ollama (easiest)
./scripts/download-multi-vendor.sh codestral:22b

# Pre-quantized GGUF (recommended - no conversion)
./scripts/download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf

# Hugging Face (may need conversion)
./scripts/download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf

# List all options
./scripts/download-multi-vendor.sh --list-vendors
./scripts/download-multi-vendor.sh --list-models
```

## Top 5 Most Useful Commands

### 1. Download a Pre-Quantized GGUF Model (FASTEST)

```bash
./scripts/download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf
```

**Why this is best**:
- ✅ Small size (3.8 GB vs 13.5 GB)
- ✅ No conversion needed
- ✅ Ready to use immediately
- ✅ Works with llama.cpp and Ollama

### 2. Download an Ollama Model (EASIEST)

```bash
./scripts/download-multi-vendor.sh codestral:22b
```

**Why this is best**:
- ✅ Simplest command
- ✅ Auto-optimized for Ollama
- ✅ Built-in quantization
- ✅ Large model library

### 3. See What's Available

```bash
# See all vendors
./scripts/download-multi-vendor.sh --list-vendors

# See pre-configured models
./scripts/download-multi-vendor.sh --list-models
```

### 4. Download Latest Research Models

```bash
# Latest from Hugging Face
./scripts/download-multi-vendor.sh hf:mistralai/Mistral-7B-v0.1
./scripts/download-multi-vendor.sh hf:microsoft/phi-2
./scripts/download-multi-vendor.sh hf:Qwen/Qwen2.5-7B-Instruct
```

### 5. Convert HF Model to GGUF

```bash
# Download first
./scripts/download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf

# Then convert
./scripts/download-multi-vendor.sh --convert-to-gguf meta-llama/Llama-2-7b-chat-hf
```

## Model Selection Guide

### For Code Generation

**Best choice**: Pre-quantized coding models

```bash
# Code LLaMA (13B, good balance)
./scripts/download-multi-vendor.sh gguf:TheBloke/CodeLlama-13B-GGUF/codellama-13b.Q4_K_M.gguf

# Codestral (22B, higher quality)
./scripts/download-multi-vendor.sh codestral:22b

# Qwen Coder (7B, efficient)
./scripts/download-multi-vendor.sh hf:Qwen/Qwen2.5-Coder-7B-Instruct
```

### For Chat/Reasoning

**Best choice**: General-purpose models

```bash
# LLaMA 2 (7B, well-tested)
./scripts/download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf

# Mistral (7B, high quality)
./scripts/download-multi-vendor.sh gguf:TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q5_K_M.gguf

# Mixtral (8x7B, very powerful)
./scripts/download-multi-vendor.sh hf:mistralai/Mixtral-8x7B-v0.1
```

### For Small/Fast Models

**Best choice**: Efficient small models

```bash
# Phi-2 (2.7B, Microsoft)
./scripts/download-multi-vendor.sh hf:microsoft/phi-2

# Gemma (2B, Google)
./scripts/download-multi-vendor.sh hf:google/gemma-2b
```

## Quick Comparison

| Source | Download Time | Setup Time | Total Time | Ready to Use |
|--------|---------------|------------|------------|--------------|
| **GGUF (TheBloke)** | 5 min | 0 min | **5 min** | ✅ Yes |
| **Ollama** | 5 min | 0 min | **5 min** | ✅ Yes |
| **Hugging Face** | 18 min | 30 min | **48 min** | ⚠️ After conversion |

**Recommendation**: Use GGUF or Ollama for fastest deployment.

## Common Use Cases

### "I want the fastest download"

```bash
./scripts/download-multi-vendor.sh codestral:22b
```

### "I want the smallest file size"

```bash
./scripts/download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf
```

### "I want the best quality"

```bash
# Download HF model, convert to fp16 GGUF
./scripts/download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf
./scripts/download-multi-vendor.sh --convert-to-gguf meta-llama/Llama-2-7b-chat-hf
```

### "I want to try the latest research model"

```bash
# Check Hugging Face for new models, then:
./scripts/download-multi-vendor.sh hf:ORG/MODEL-NAME
```

### "I want a model for my low-RAM machine"

```bash
# Small quantized models (under 2GB)
./scripts/download-multi-vendor.sh hf:microsoft/phi-2        # 2.7B
./scripts/download-multi-vendor.sh hf:google/gemma-2b        # 2B
```

## Troubleshooting

### "Download fails"

Check internet connection and try again:
```bash
# Retry with same command
./scripts/download-multi-vendor.sh <your-command>
```

### "Authentication required"

For Hugging Face models:
```bash
pip install -U huggingface_hub
huggingface-cli login
# Enter token from https://huggingface.co/settings/tokens
```

### "NAS not found"

Set custom location:
```bash
export NAS_MODELS_DIR=/path/to/your/storage
./scripts/download-multi-vendor.sh <your-command>
```

### "Out of disk space"

Check space:
```bash
df -h /mnt/nas/ai-models
```

Delete unused models or use smaller quantization (Q2_K, Q3_K instead of Q5_K).

## Next Steps

After downloading models to NAS:

1. **Distribute to nodes**:
   ```bash
   ./scripts/distribute-to-nodes.sh MODEL_NAME
   ```

2. **Use with Ollama**:
   ```bash
   ollama run MODEL_NAME
   ```

3. **Use with llama.cpp**:
   ```bash
   ./llama.cpp/main -m /mnt/nas/ai-models/gguf/model.gguf -p "Your prompt"
   ```

## Resources

- Full documentation: `docs/multi-vendor-model-distribution.md`
- Schema reference: `schemas/vendor-sources.schema.json`
- Vendor registry: `scripts/vendor-sources.json`
- Model inventory: Check `/mnt/nas/ai-models/manifests/model-inventory.json` after downloads

## Tips

1. **Start with GGUF** - Fastest and easiest
2. **Use Q4_K_M quantization** - Best quality/size balance
3. **Check TheBloke first** - Pre-quantized versions of popular models
4. **Keep inventory clean** - Delete originals after conversion to save space
5. **Test locally first** - Download one model, test it, then batch download others

## Support

If you encounter issues:

1. Check logs in console output
2. Verify NAS is mounted: `ls /mnt/nas/ai-models`
3. Check disk space: `df -h`
4. Review vendor-sources.json for model details
5. Check documentation: `docs/multi-vendor-model-distribution.md`
