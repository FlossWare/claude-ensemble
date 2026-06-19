#!/usr/bin/env python3
"""
Generate text embeddings using sentence-transformers all-MiniLM-L6-v2

Reads text from stdin, outputs 384-dim embedding as JSON array.

Usage:
    echo "sample text" | python3 generate-embedding.py
"""

import sys
import json

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed", file=sys.stderr)
    print("Install: pip3 install sentence-transformers", file=sys.stderr)
    sys.exit(1)

# Load model (cached after first load)
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Read text from stdin
text = sys.stdin.read().strip()

if not text:
    print("ERROR: No text provided", file=sys.stderr)
    sys.exit(1)

# Generate embedding
embedding = model.encode(text).tolist()

# Output as JSON array
print(json.dumps(embedding))
