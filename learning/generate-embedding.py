#!/usr/bin/env python3
"""
Fast embedding generation script for postgres-adapter.js
Uses sentence-transformers to generate 768-dim embeddings
"""
import sys
from sentence_transformers import SentenceTransformer

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

# Load model once
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

# Read text from stdin or file
if len(sys.argv) > 1:
    with open(sys.argv[1], 'r') as f:
        text = f.read()
else:
    text = sys.stdin.read()

# Generate embedding
embedding = model.encode(text.strip())

# Output as comma-separated floats
print(','.join(map(str, embedding)))
