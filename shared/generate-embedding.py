#!/usr/bin/env python3
"""
Generate text embeddings using sentence-transformers all-mpnet-base-v2

Reads text from stdin, outputs 768-dim embedding as JSON array.
Compatible with command substitution: $(python3 generate-embedding.py)

Usage:
    echo "sample text" | python3 generate-embedding.py
    python3 generate-embedding.py < file.txt
    embedding=$(echo "text" | python3 generate-embedding.py)

Output format: [0.123, -0.456, ..., 0.789]  (768 numbers)
"""

import sys
import json
import warnings

# Suppress sentence-transformers warnings/progress bars for clean JSON output
warnings.filterwarnings('ignore')

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    # Graceful fallback - output null instead of failing
    json.dump(None, sys.stdout)
    print("", file=sys.stderr)  # stderr: silent failure for command substitution
    sys.exit(0)  # Exit 0 so command substitution doesn't break

try:
    # Load model (cached after first load in ~/.cache/torch/sentence_transformers/)
    # First run downloads ~90MB model, subsequent runs load from cache (~2s)
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    # Read text from stdin
    text = sys.stdin.read().strip()

    if not text:
        # Empty input - return null (graceful)
        json.dump(None, sys.stdout)
        sys.exit(0)

    # Generate embedding (returns numpy array, convert to list)
    embedding = model.encode(text, convert_to_numpy=True).tolist()

    # Output as compact JSON array (no newline for command substitution)
    json.dump(embedding, sys.stdout)

except Exception as e:
    # Any error - return null (graceful fallback for workflows)
    json.dump(None, sys.stdout)
    print(f"", file=sys.stderr)  # silent error for command substitution
    sys.exit(0)  # Exit 0 so command substitution doesn't break
