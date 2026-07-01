#!/bin/bash
#
# Activate Embedding Generation
# Installs sentence-transformers and verifies integration
#
# Usage: ./scripts/activate-embeddings.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SHARED_DIR="$PROJECT_ROOT/shared"

echo "🚀 Activating Embedding Generation System"
echo "=========================================="

# Check Python version
echo ""
echo "Checking Python installation..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

echo "  Python version: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
  echo "  ✗ Python 3.8+ required (found $PYTHON_VERSION)"
  exit 1
fi

echo "  ✓ Python version OK"

# Check if sentence-transformers is already installed
echo ""
echo "Checking sentence-transformers installation..."
if python3 -c "from sentence_transformers import SentenceTransformer" 2>/dev/null; then
  echo "  ✓ sentence-transformers already installed"
  ALREADY_INSTALLED=1
else
  echo "  ⚠ sentence-transformers not installed"
  ALREADY_INSTALLED=0
fi

# Install if needed
if [ "$ALREADY_INSTALLED" -eq 0 ]; then
  echo ""
  echo "Installing sentence-transformers..."
  echo "  This will download ~200MB of dependencies"

  # Install with user flag to avoid permission issues
  if pip3 install --user sentence-transformers; then
    echo "  ✓ sentence-transformers installed successfully"
  else
    echo "  ✗ Installation failed"
    echo ""
    echo "Try manually:"
    echo "  pip3 install --user sentence-transformers"
    exit 1
  fi
fi

# Download model (first run)
echo ""
echo "Downloading all-MiniLM-L6-v2 model..."
echo "  Size: ~90MB (downloads to ~/.cache/torch/sentence_transformers/)"

DOWNLOAD_START=$(date +%s)

python3 << 'PYTHON_SCRIPT'
from sentence_transformers import SentenceTransformer
import sys

try:
    # Download model (cached after first run)
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    # Test encoding
    test_embedding = model.encode("test firmware analysis")

    if len(test_embedding) == 384:
        print(f"  ✓ Model loaded successfully ({len(test_embedding)}-dim embeddings)")
        sys.exit(0)
    else:
        print(f"  ✗ Unexpected embedding dimension: {len(test_embedding)} (expected 384)")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Model download failed: {e}")
    sys.exit(1)
PYTHON_SCRIPT

MODEL_STATUS=$?
DOWNLOAD_END=$(date +%s)
DOWNLOAD_TIME=$((DOWNLOAD_END - DOWNLOAD_START))

if [ $MODEL_STATUS -ne 0 ]; then
  echo "  ✗ Model download failed"
  exit 1
fi

echo "  ⏱ Download took ${DOWNLOAD_TIME}s"

# Test embedding generation scripts
echo ""
echo "Testing embedding generation scripts..."

# Test 1: generate-embedding.py (single)
echo "  Testing generate-embedding.py (single text)..."
SINGLE_RESULT=$(echo "firmware reverse engineering" | python3 "$SHARED_DIR/generate-embedding.py")
SINGLE_DIM=$(echo "$SINGLE_RESULT" | python3 -c "import sys, json; vec = json.load(sys.stdin); print(len(vec) if vec else 0)")

if [ "$SINGLE_DIM" -eq 384 ]; then
  echo "    ✓ Single text embedding: 384-dim"
else
  echo "    ✗ Single text embedding failed (got ${SINGLE_DIM}-dim)"
  exit 1
fi

# Test 2: generate-embeddings.py (batch)
echo "  Testing generate-embeddings.py (batch)..."
BATCH_RESULT=$(echo '["text 1", "text 2", "text 3"]' | python3 "$SHARED_DIR/generate-embeddings.py")
BATCH_COUNT=$(echo "$BATCH_RESULT" | python3 -c "import sys, json; r = json.load(sys.stdin); print(len(r.get('embeddings', [])))")

if [ "$BATCH_COUNT" -eq 3 ]; then
  echo "    ✓ Batch embeddings: 3 vectors generated"
else
  echo "    ✗ Batch embeddings failed (got $BATCH_COUNT vectors)"
  exit 1
fi

# Test 3: JavaScript adapter
echo "  Testing JavaScript adapter (workflow-storage-adapter.cjs)..."
node -e "
const { generateEmbedding } = require('$SHARED_DIR/workflow-storage-adapter.cjs');
generateEmbedding('test').then(vec => {
  if (vec && vec.length === 384) {
    console.log('    ✓ JavaScript adapter: 384-dim vector');
    process.exit(0);
  } else {
    console.log('    ✗ JavaScript adapter failed');
    process.exit(1);
  }
}).catch(err => {
  console.log('    ✗ JavaScript adapter error:', err.message);
  process.exit(1);
});
"

if [ $? -ne 0 ]; then
  echo "    ✗ JavaScript adapter test failed"
  exit 1
fi

# Success summary
echo ""
echo "=========================================="
echo "✅ Embedding Generation ACTIVATED"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "  1. Embeddings will now auto-populate in PostgreSQL"
echo "  2. Semantic similarity search enabled"
echo "  3. Experience-based learning active"
echo ""
echo "Test semantic search:"
echo "  psql -h aio-01 -p 5433 -d learning -c \\"
echo "    \"SELECT workflow_name FROM workflow.executions \\"
echo "     WHERE task_description_embedding IS NOT NULL \\"
echo "     LIMIT 5\""
echo ""
echo "Documentation:"
echo "  docs/EMBEDDING_INTEGRATION.md"
echo ""
echo "Performance:"
echo "  Single embedding: ~50ms"
echo "  Batch 10 texts: ~200ms"
echo "  pgvector search: ~0.4ms"
echo ""
