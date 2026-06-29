# All FREE Models in /exports ✅

## Structure

```
/exports/ai-models/
├── huggingface/
│   └── hub/
│       └── models--sentence-transformers--all-MiniLM-L6-v2/  (88MB)
├── ollama/          (for future Ollama models)
├── gguf/            (for future GGUF models)
└── local-ai/        (for future LocalAI models)
```

## Current Setup (laptop-01)

**HuggingFace Models:**
- Location: `/exports/ai-models/huggingface/`
- Model: `all-MiniLM-L6-v2` (384 dims, 88MB)
- Usage: Set `HF_HOME=/exports/ai-models/huggingface`
- **NO files in home directory** ✅

**Search Script:**
- `~/bin/search-sessions-local.py`
- Automatically uses `/exports/ai-models/huggingface`
- DB_HOST: `localhost`

## For Servers (server-01/02/03)

Servers should symlink or mount `/exports` from laptop-01:

```bash
# On each server
mkdir -p ~/.cache/huggingface/hub
ln -s /path/to/laptop-01-exports/ai-models/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2 \
      ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2
```

Or set environment variable:
```bash
export HF_HOME=/path/to/laptop-01-exports/ai-models/huggingface
```

## Future FREE Vendors

All future models go in `/exports/ai-models/`:

### Ollama
```bash
export OLLAMA_MODELS=/exports/ai-models/ollama
```

### vLLM / text-generation-webui
```bash
# Point to /exports/ai-models/gguf/
```

### LocalAI
```bash
# Config: model_path: /exports/ai-models/local-ai/
```

## Rules

1. ✅ **All models in `/exports/ai-models/`**
2. ✅ **NO models in home directories**
3. ✅ **Servers can symlink from laptop-01's /exports**
4. ✅ **Use environment variables (HF_HOME, OLLAMA_MODELS, etc.)**

## Verification

```bash
# Check no models in home
du -sh ~/.cache ~/.local 2>/dev/null | grep -i hugg || echo "✅ Clean"

# Check models in /exports
du -sh /exports/ai-models/

# Test model loads
python3 << 'EOF'
import os
os.environ['HF_HOME'] = '/exports/ai-models/huggingface'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"✅ Model loaded: {model.get_embedding_dimension()} dims")
EOF
```

---

**Status:** ✅ All models centralized in `/exports`, home directories clean
