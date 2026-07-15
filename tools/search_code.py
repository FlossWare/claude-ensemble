#!/usr/bin/env python3
"""
Semantic code search using embeddings

Search code and documentation using natural language queries.

Usage:
    python3 tools/search_code.py "how to generate embeddings"
    python3 tools/search_code.py "PostgreSQL connection" --type code
    python3 tools/search_code.py "fleet orchestration" --limit 20

Options:
    --type {code,documentation,all}   Filter by file type (default: all)
    --limit N                         Number of results (default: 10)
    --show-content                    Show file content snippets
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict
import psycopg2

# Add parent directory to path for imports
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("ERROR: sentence-transformers not installed", file=sys.stderr)
    print("Install: pip3 install sentence-transformers", file=sys.stderr)
    sys.exit(1)

# Database connection
DB_CONFIG = {
    'dbname': 'learning',
    'user': 'claude',
    'host': 'aio-01',
    'port': 5433
}

# Embedding model
_model = None


def get_model() -> SentenceTransformer:
    """Get or load embedding model (singleton)"""
    global _model
    if _model is None:
        _model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    return _model


def search_embeddings(query: str, file_type: str = None, limit: int = 10) -> List[Dict]:
    """
    Search code/docs using semantic similarity

    Args:
        query: Natural language search query
        file_type: Filter by 'code', 'documentation', or None for all
        limit: Maximum results to return

    Returns:
        List of dicts with keys: file_path, file_type, distance, content_preview, metadata
    """
    # Generate query embedding
    model = get_model()
    query_embedding = model.encode(query, convert_to_numpy=True).tolist()

    # Connect and search
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    sql = """
        SELECT file_path, file_type, content_preview, metadata,
               embedding <=> %s::vector as distance
        FROM knowledge.code_embeddings
    """
    params = [query_embedding]

    if file_type and file_type != 'all':
        sql += " WHERE file_type = %s"
        params.append(file_type)

    sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
    params.extend([query_embedding, limit])

    cursor.execute(sql, params)
    results = cursor.fetchall()

    conn.close()

    # Format results
    return [
        {
            'file_path': row[0],
            'file_type': row[1],
            'content_preview': row[2],
            'metadata': row[3],
            'distance': float(row[4]),
            'similarity': 1.0 - float(row[4])  # Convert distance to similarity
        }
        for row in results
    ]


def read_file_snippet(file_path: str, lines: int = 20) -> str:
    """Read first N lines of a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            snippet = []
            for i, line in enumerate(f):
                if i >= lines:
                    break
                snippet.append(line.rstrip())
            return '\n'.join(snippet)
    except Exception as e:
        return f"[Could not read file: {e}]"


def format_result(result: Dict, index: int, show_content: bool = False) -> str:
    """Format a single search result"""
    rel_path = result['file_path'].replace('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/', '')

    output = []
    output.append(f"\n{index}. {rel_path}")
    output.append(f"   Type: {result['file_type']}, Similarity: {result['similarity']:.3f}")

    if show_content:
        output.append(f"\n   Preview:")
        preview = result['content_preview']
        for line in preview.split('\n')[:5]:
            output.append(f"   │ {line}")
        if len(preview.split('\n')) > 5:
            output.append(f"   │ ...")

    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description='Semantic code search')
    parser.add_argument('query', help='Search query (natural language)')
    parser.add_argument('--type', choices=['code', 'documentation', 'all'], default='all',
                        help='Filter by file type')
    parser.add_argument('--limit', type=int, default=10, help='Number of results')
    parser.add_argument('--show-content', action='store_true', help='Show content snippets')
    args = parser.parse_args()

    # Search
    print(f"Searching for: '{args.query}'")
    if args.type != 'all':
        print(f"File type: {args.type}")

    results = search_embeddings(args.query, args.type if args.type != 'all' else None, args.limit)

    if not results:
        print("\nNo results found")
        return

    print(f"\nFound {len(results)} results:")

    for i, result in enumerate(results, 1):
        print(format_result(result, i, args.show_content))

    # Summary stats
    code_count = sum(1 for r in results if r['file_type'] == 'code')
    doc_count = sum(1 for r in results if r['file_type'] == 'documentation')
    avg_sim = sum(r['similarity'] for r in results) / len(results)

    print(f"\nSummary: {code_count} code files, {doc_count} docs, avg similarity: {avg_sim:.3f}")


if __name__ == '__main__':
    main()
