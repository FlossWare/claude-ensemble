# AI Models Centralized on NAS ✅

## Location: `/exports/nas/ai-models/`

All AI models now stored centrally on NAS and symlinked from local machines.

## HuggingFace Models

**Location:** `/exports/nas/ai-models/huggingface/`

### sentence-transformers Models
```
/exports/nas/ai-models/huggingface/
└── models--sentence-transformers--all-MiniLM-L6-v2/
    ├── snapshots/
    ├── refs/
    └── ... (90MB total)
```

**Symlinked from laptop-01:**
```
~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2
  → /exports/nas/ai-models/huggingface/models--sentence-transformers--all-MiniLM-L6-v2
```

## Ollama Models

**Location:** `/mnt/nas/ai-models/ollama-from-laptop-01/` (137GB)

All servers access via NFS:
- server-01: `OLLAMA_MODELS=/mnt/nas/ai-models/ollama-from-laptop-01`
- server-02: `OLLAMA_MODELS=/mnt/nas/ai-models/ollama-from-laptop-01`
- server-03: `OLLAMA_MODELS=/mnt/nas/ai-models/ollama-from-laptop-01`

## GGUF Models

**Location:** `/mnt/nas/ai-models/gguf/` (88GB)

6 models for vLLM, text-generation-webui, llamafile.

## Setup on Other Machines

To use the sentence-transformers model from NAS on other machines:

```bash
# Create symlink
mkdir -p ~/.cache/huggingface/hub
ln -s /exports/nas/ai-models/huggingface/models--sentence-transformers--all-MiniLM-L6-v2 \
      ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2

# Test
python3 -c "from sentence_transformers import SentenceTransformer; \
            model = SentenceTransformer('all-MiniLM-L6-v2'); \
            print('✅ Works!')"
```

## Total NAS Model Storage

```
/exports/nas/ai-models/
├── huggingface/            90 MB
├── ollama-from-laptop-01/ 137 GB
└── gguf/                   88 GB
────────────────────────────────
Total:                     ~225 GB
```

## Benefits

1. **Single source of truth** - One copy per model
2. **No duplication** - All machines share same models
3. **Easy updates** - Update once on NAS, all machines get it
4. **Backup included** - NAS is backed up to server-ap
5. **Red Hat compliant** - Local models, no external APIs

---

**Status:** ✅ All models centralized on NAS with symlinks
