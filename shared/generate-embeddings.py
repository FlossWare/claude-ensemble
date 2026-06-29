#!/usr/bin/env python3
"""
Embedding Generation Service
Generates 384-dim embeddings using sentence-transformers
Called from JavaScript via subprocess
"""

import sys
import json
import os

def generate_embeddings(texts):
    """
    Generate embeddings for one or more texts.

    Args:
        texts: List of strings to embed

    Returns:
        List of 384-dim vectors (as lists)
    """
    try:
        from sentence_transformers import SentenceTransformer

        # Use all-MiniLM-L6-v2: 384-dim, fast, good quality
        # Model auto-downloads to ~/.cache/torch/sentence_transformers/
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

        # Generate embeddings (returns numpy array)
        embeddings = model.encode(texts, convert_to_numpy=True)

        # Convert to list of lists for JSON serialization
        return embeddings.tolist()

    except ImportError:
        # Graceful fallback if sentence-transformers not installed
        sys.stderr.write("WARNING: sentence-transformers not installed. Install with: pip3 install sentence-transformers\n")
        return None
    except Exception as e:
        sys.stderr.write(f"ERROR generating embeddings: {e}\n")
        return None


def main():
    """
    CLI interface: reads JSON array from stdin, outputs JSON array to stdout

    Input format:  ["text1", "text2", ...]
    Output format: [[0.1, 0.2, ...], [0.3, 0.4, ...], ...]
    """
    try:
        # Read input from stdin
        input_data = sys.stdin.read()

        if not input_data.strip():
            print(json.dumps({"error": "No input provided"}), file=sys.stderr)
            sys.exit(1)

        # Parse JSON array of texts
        texts = json.loads(input_data)

        if not isinstance(texts, list):
            print(json.dumps({"error": "Input must be a JSON array"}), file=sys.stderr)
            sys.exit(1)

        # Generate embeddings
        embeddings = generate_embeddings(texts)

        if embeddings is None:
            # Return null for each text if embedding failed
            result = {"embeddings": [None] * len(texts), "error": "Embedding generation failed"}
        else:
            result = {"embeddings": embeddings, "dimension": len(embeddings[0]) if embeddings else 0}

        # Output JSON to stdout
        print(json.dumps(result))
        sys.exit(0)  # Explicit success exit

    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
