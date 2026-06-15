# Multi-Vendor Model Distribution System

## Overview

The multi-vendor model distribution system extends NAS-based model management to support downloading AI models from ANY vendor, not just Ollama. This allows you to download models once to NAS from Hugging Face, TheBloke, Meta, Mistral, Google, Microsoft, Alibaba, and more, then distribute them efficiently across your fleet.

## Supported Vendors

### 1. Ollama (Native Registry)
- **Download Method**: `ollama pull`
- **Format**: Ollama-native (optimized)
- **Conversion**: None needed
- **Usage**: `download-multi-vendor.sh ollama:codestral:22b`

**Pros**:
- Easiest to use
- No conversion needed
- Ready to use immediately
- Built-in quantization

**Cons**:
- Limited model selection
- Must be available in Ollama library

### 2. Hugging Face Hub
- **Download Method**: `huggingface-cli download`
- **Format**: SafeTensors, PyTorch, GGUF, ONNX
- **Conversion**: Usually needed (to GGUF)
- **Usage**: `download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf`

**Pros**:
- Largest model repository
- Most comprehensive selection
- Official model weights
- Community contributions

**Cons**:
- May need conversion to GGUF
- Some models require authentication
- License approval for some models (LLaMA, Gemma)

### 3. TheBloke (Pre-quantized GGUF)
- **Download Method**: `wget` (direct download)
- **Format**: GGUF (pre-quantized)
- **Conversion**: None needed
- **Usage**: `download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf`

**Pros**:
- Pre-quantized (smaller size)
- Ready to use with llama.cpp/Ollama
- Multiple quantization levels available
- No conversion needed

**Cons**:
- Not all models available
- Depends on TheBloke's conversion schedule

### 4. Meta/Facebook (Official LLaMA)
- **Download Method**: Manual (license required)
- **Format**: PyTorch
- **Conversion**: Required (to GGUF)
- **Usage**: `download-multi-vendor.sh meta:llama-2-7b`

**Pros**:
- Official weights from Meta
- Most authoritative source

**Cons**:
- Requires license agreement
- Manual download process
- Must convert to GGUF
- Better to use HF or TheBloke versions

### 5. Mistral AI
- **Download Method**: Hugging Face
- **Format**: SafeTensors
- **Conversion**: Usually needed
- **Usage**: `download-multi-vendor.sh hf:mistralai/Mistral-7B-v0.1`

**Pros**:
- High-quality models
- Open license (Apache-2.0)
- Available on Hugging Face

### 6. Google (Gemma)
- **Download Method**: Hugging Face
- **Format**: SafeTensors
- **Conversion**: Usually needed
- **Usage**: `download-multi-vendor.sh hf:google/gemma-2b`

**Pros**:
- Efficient models
- Good performance

**Cons**:
- Requires license agreement
- Conversion needed

### 7. Microsoft (Phi)
- **Download Method**: Hugging Face
- **Format**: SafeTensors, ONNX
- **Conversion**: Usually needed
- **Usage**: `download-multi-vendor.sh hf:microsoft/phi-2`

**Pros**:
- Very efficient small models
- MIT license
- Good performance for size

### 8. Alibaba (Qwen)
- **Download Method**: Hugging Face
- **Format**: SafeTensors, some GGUF
- **Conversion**: Sometimes needed
- **Usage**: `download-multi-vendor.sh hf:Qwen/Qwen2.5-7B-Instruct`

**Pros**:
- Strong coding models
- Some available as GGUF
- Apache-2.0 license

## Directory Structure

```
/mnt/nas/ai-models/
├── ollama/                      # Ollama models (native format)
│   ├── codestral:22b/
│   │   ├── manifests/
│   │   └── blobs/
│   └── qwen2.5-coder:7b/
│       ├── manifests/
│       └── blobs/
│
├── huggingface/                 # Hugging Face models (original format)
│   ├── meta-llama/
│   │   ├── Llama-2-7b-chat-hf/
│   │   │   ├── config.json
│   │   │   ├── model.safetensors
│   │   │   └── tokenizer.model
│   │   └── Llama-3-8B/
│   ├── mistralai/
│   │   └── Mistral-7B-v0.1/
│   ├── microsoft/
│   │   └── phi-2/
│   └── Qwen/
│       └── Qwen2.5-7B-Instruct/
│
├── gguf/                        # GGUF files (direct download or converted)
│   ├── llama-2-7b-chat.Q4_K_M.gguf
│   ├── llama-2-7b-chat.Q5_K_M.gguf
│   ├── mistral-7b-instruct-v0.2.Q5_K_M.gguf
│   ├── codellama-13b.Q4_K_M.gguf
│   └── Llama-2-7b-chat-hf/      # Converted from HF
│       ├── model.gguf
│       └── model-q4_k_m.gguf
│
├── facebook/                    # Official Meta models (manual)
│   └── llama-2-7b/
│
├── conversions/                 # Temporary conversion workspace
│
└── manifests/                   # Metadata and inventory
    ├── model-inventory.json     # Central inventory
    ├── vendor-sources.json      # Vendor registry
    └── version-history.json     # Download history
```

## Usage Examples

### Basic Downloads

```bash
# Ollama model (easiest)
./scripts/download-multi-vendor.sh ollama:codestral:22b
./scripts/download-multi-vendor.sh codestral:22b  # Auto-detects Ollama

# Hugging Face model
./scripts/download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf
./scripts/download-multi-vendor.sh hf:mistralai/Mistral-7B-v0.1
./scripts/download-multi-vendor.sh hf:microsoft/phi-2
./scripts/download-multi-vendor.sh hf:Qwen/Qwen2.5-7B-Instruct

# Pre-quantized GGUF (recommended - no conversion)
./scripts/download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf
./scripts/download-multi-vendor.sh gguf:TheBloke/Mistral-7B-Instruct-v0.2-GGUF/mistral-7b-instruct-v0.2.Q5_K_M.gguf
./scripts/download-multi-vendor.sh gguf:TheBloke/CodeLlama-13B-GGUF/codellama-13b.Q4_K_M.gguf

# Direct GGUF URL
./scripts/download-multi-vendor.sh gguf:https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf
```

### List Available Options

```bash
# List supported vendors
./scripts/download-multi-vendor.sh --list-vendors

# List pre-configured models
./scripts/download-multi-vendor.sh --list-models
```

### Format Conversion

```bash
# Convert Hugging Face model to GGUF
./scripts/download-multi-vendor.sh --convert-to-gguf meta-llama/Llama-2-7b-chat-hf

# This will:
# 1. Convert to fp16 GGUF
# 2. Create Q4_K_M quantized version
# 3. Save to /mnt/nas/ai-models/gguf/
```

## Model Format Comparison

| Format | Size | Speed | Compatibility | Use Case |
|--------|------|-------|---------------|----------|
| **Ollama-native** | Optimized | Fast | Ollama only | Best for Ollama deployment |
| **GGUF** | Small (quantized) | Very fast | llama.cpp, Ollama | Best for local inference |
| **SafeTensors** | Large (full precision) | Medium | HF Transformers | Training, fine-tuning |
| **PyTorch** | Large | Medium | PyTorch | Training, research |
| **ONNX** | Medium | Fast | ONNX Runtime | Cross-platform inference |

## Quantization Levels (GGUF)

When downloading pre-quantized GGUF models, choose based on quality vs. size:

| Quantization | Size | Quality | Speed | Recommended For |
|--------------|------|---------|-------|-----------------|
| **Q2_K** | Smallest | Lowest | Fastest | Testing only |
| **Q3_K_M** | Very small | Low | Very fast | Resource-constrained |
| **Q4_K_M** | Small | Good | Fast | **Most common choice** |
| **Q5_K_M** | Medium | Very good | Fast | Quality-focused |
| **Q6_K** | Medium-large | Excellent | Medium | High quality |
| **Q8_0** | Large | Near-perfect | Slower | Maximum quality |
| **fp16** | Largest | Perfect | Slowest | Reference/conversion |

**Recommended**: Start with Q4_K_M for best balance, upgrade to Q5_K_M if quality is insufficient.

## Workflow Recommendations

### For Production Use

1. **Prefer pre-quantized GGUF** (TheBloke)
   - No conversion needed
   - Smaller download size
   - Ready to use immediately

2. **Use Ollama for simple deployments**
   - Easy management
   - Built-in serving
   - Auto-optimization

3. **Use Hugging Face for latest models**
   - Most up-to-date versions
   - Official releases
   - Convert to GGUF as needed

### For Research/Fine-tuning

1. **Download original formats** (SafeTensors, PyTorch)
   - Full precision weights
   - Compatible with training frameworks
   - Keep on NAS for team access

2. **Convert to GGUF for inference**
   - After training/fine-tuning
   - For deployment to production

## Authentication Setup

### Hugging Face

Some models require authentication:

```bash
# Install Hugging Face CLI
pip install -U huggingface_hub

# Login (one-time setup)
huggingface-cli login

# Follow prompts to enter your HF token
# Get token from: https://huggingface.co/settings/tokens
```

### Meta LLaMA Models

1. Visit: https://llama.meta.com/llama-downloads
2. Fill out license agreement
3. Wait for email approval
4. Use provided download script

**Easier alternative**: Use pre-converted versions:
- Hugging Face: `hf:meta-llama/Llama-2-7b-chat-hf`
- TheBloke: `gguf:TheBloke/Llama-2-7B-Chat-GGUF/...`

## Integration with Fleet

Once models are downloaded to NAS, distribute to nodes:

```bash
# Distribute specific model
./scripts/distribute-to-nodes.sh MODEL_NAME

# Distribute all models to specific node
./scripts/distribute-to-nodes.sh --node server-02

# Distribute all models to all nodes
./scripts/distribute-to-nodes.sh
```

The distribution script automatically detects vendor and format, handles conversions if needed.

## Model Inventory

The system maintains a comprehensive inventory in `/mnt/nas/ai-models/manifests/model-inventory.json`:

```json
{
  "_version": "2.0",
  "_last_updated": "2026-06-13T00:00:00Z",
  "nas_path": "/mnt/nas/ai-models",
  "models": {
    "codestral:22b": {
      "vendor": "ollama",
      "format": "ollama-native",
      "disk_usage": "12G",
      "downloaded": "2026-06-13T10:00:00Z",
      "source_url": "ollama.com/library/codestral:22b",
      "nas_path": "/mnt/nas/ai-models/ollama/codestral:22b",
      "needs_conversion": false,
      "distributed_to": ["server-02"],
      "version": "latest"
    },
    "meta-llama/Llama-2-7b-chat-hf": {
      "vendor": "huggingface",
      "format": "safetensors",
      "disk_usage": "13.5G",
      "downloaded": "2026-06-13T10:15:00Z",
      "source_url": "https://huggingface.co/meta-llama/Llama-2-7b-chat-hf",
      "nas_path": "/mnt/nas/ai-models/huggingface/meta-llama/Llama-2-7b-chat-hf",
      "needs_conversion": true,
      "converted_to": "gguf",
      "conversion_path": "/mnt/nas/ai-models/gguf/Llama-2-7b-chat-hf",
      "distributed_to": [],
      "license": "Meta",
      "version": "latest"
    },
    "llama-2-7b-chat.Q4_K_M.gguf": {
      "vendor": "thebloke",
      "format": "gguf",
      "disk_usage": "3.8G",
      "downloaded": "2026-06-13T10:30:00Z",
      "source_url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf",
      "nas_path": "/mnt/nas/ai-models/gguf/llama-2-7b-chat.Q4_K_M.gguf",
      "needs_conversion": false,
      "quantization": "Q4_K_M",
      "distributed_to": ["server-03"],
      "license": "Meta",
      "version": "latest"
    }
  }
}
```

## Troubleshooting

### Hugging Face download fails

**Problem**: `huggingface-cli` not found

**Solution**:
```bash
pip install -U huggingface_hub
```

**Problem**: Authentication required

**Solution**:
```bash
huggingface-cli login
# Enter token from https://huggingface.co/settings/tokens
```

### Conversion fails

**Problem**: llama.cpp not found

**Solution**:
```bash
git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp
cd ~/llama.cpp
pip install -r requirements.txt
```

### NAS not mounted

**Problem**: `/mnt/nas/ai-models` not found

**Solution**:
```bash
# Check NAS mount
mount | grep nas

# Mount if needed
sudo mount -t nfs nas.local:/volume1/ai-models /mnt/nas/ai-models

# Or set custom location
export NAS_MODELS_DIR=/path/to/your/models
```

## Performance Comparison

### Download Times (100 Mbps internet)

| Model | Format | Size | Download Time | Post-Processing |
|-------|--------|------|---------------|-----------------|
| LLaMA-2-7B (Ollama) | Native | 3.8 GB | ~5 min | None |
| LLaMA-2-7B (HF) | SafeTensors | 13.5 GB | ~18 min | +30 min conversion |
| LLaMA-2-7B (GGUF Q4) | GGUF | 3.8 GB | ~5 min | None |

**Recommendation**: Use pre-quantized GGUF (TheBloke) or Ollama for fastest deployment.

### Storage Efficiency

| Source | Original Size | Converted Size | Total |
|--------|---------------|----------------|-------|
| Ollama native | 3.8 GB | N/A | 3.8 GB |
| HF + conversion | 13.5 GB | 3.8 GB (Q4) | 17.3 GB |
| GGUF direct | 3.8 GB | N/A | 3.8 GB |

**Recommendation**: Delete HF originals after conversion to save space, or don't download them at all - use GGUF directly.

## Best Practices

1. **Start with GGUF when available** (TheBloke)
   - Fastest to deploy
   - Smallest size
   - No conversion overhead

2. **Use Ollama for models in their library**
   - Simple management
   - Auto-optimization
   - Built-in serving

3. **Use Hugging Face for new/custom models**
   - Latest releases
   - Research models
   - Fine-tuned models

4. **Keep originals only if needed**
   - Training/fine-tuning
   - Multiple format conversions
   - Otherwise, delete after conversion

5. **Prefer Q4_K_M or Q5_K_M quantization**
   - Good quality/size balance
   - Fast inference
   - Works on most hardware

6. **Document license requirements**
   - Track which models need approval
   - Keep license files with models
   - Respect terms of use

## Future Enhancements

- [ ] Automatic format detection
- [ ] Parallel downloads
- [ ] Resume interrupted downloads
- [ ] Automatic quantization pipeline
- [ ] Model registry web UI
- [ ] Bandwidth usage tracking
- [ ] Automatic cleanup of old versions
- [ ] Model quality benchmarking
- [ ] Integration with Ollama import
- [ ] Support for custom model uploads
