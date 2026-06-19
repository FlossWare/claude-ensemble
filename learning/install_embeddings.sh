#!/bin/bash
# Install sentence-transformers for workflow embedding generation
# Model: all-mpnet-base-v2 (768-dim, 420MB)

set -e

echo "Installing sentence-transformers for workflow embeddings..."

# Check if already installed
if python3 -c "import sentence_transformers" 2>/dev/null; then
    echo "✓ sentence-transformers already installed"
    python3 -c "from sentence_transformers import SentenceTransformer; print(f'Using model: all-mpnet-base-v2')"
    exit 0
fi

# Install via pip
echo "Installing sentence-transformers..."
pip3 install --user sentence-transformers

# Pre-download model (420MB)
echo "Downloading all-mpnet-base-v2 model (420MB)..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"

echo "✓ Installation complete"
echo "Model: all-mpnet-base-v2 (768-dim, state-of-the-art semantic similarity)"
echo "Storage: Embeddings consume 6KB per workflow (3KB vector + 3KB HNSW index)"
echo "Retention: Embeddings cleared after 90 days (daily at 3 AM)"
