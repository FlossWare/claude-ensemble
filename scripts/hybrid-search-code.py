#!/usr/bin/env python3
"""
Hybrid Search on ChromaDB for Code Learning

Executes hybrid search combining:
1. Semantic search in NL collection (natural language descriptions)
2. Semantic search in code collection (code snippets)
3. AST metadata filtering
4. Combined ranking by relevance
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
import json
import sys
from typing import List, Dict, Any, Optional


class HybridCodeSearch:
    """Hybrid search across NL and code collections with AST filtering"""

    def __init__(
        self,
        db_path: str = '~/.claude/knowledge/chromadb',
        embedding_model: str = 'all-MiniLM-L6-v2',
        verbose: bool = False
    ):
        self.verbose = verbose
        persist_path = Path(db_path).expanduser()

        if not persist_path.exists():
            raise FileNotFoundError(f"ChromaDB not found at {persist_path}")

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )

        # Create embedding function
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        if verbose:
            print(f"Initialized ChromaDB at {persist_path}", file=sys.stderr)

    def list_collections(self) -> List[str]:
        """List all collections in ChromaDB"""
        collections = self.client.list_collections()
        return [c.name for c in collections]

    def search_nl_collection(
        self,
        query: str,
        collection_pattern: str = 'code-*-nl',
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search natural language collections"""
        results = []
        collections = self.list_collections()

        # Find matching NL collections
        nl_collections = [c for c in collections if '-nl' in c and c.startswith('code-')]

        if self.verbose:
            print(f"NL collections found: {nl_collections}", file=sys.stderr)

        for coll_name in nl_collections:
            try:
                collection = self.client.get_collection(
                    name=coll_name,
                    embedding_function=self.embedding_fn
                )

                query_results = collection.query(
                    query_texts=[query],
                    n_results=top_k
                )

                # Format results
                for i in range(len(query_results['ids'][0])):
                    results.append({
                        'id': query_results['ids'][0][i],
                        'pattern': query_results['documents'][0][i],
                        'metadata': query_results['metadatas'][0][i],
                        'distance': query_results['distances'][0][i],
                        'score': 1 - query_results['distances'][0][i],
                        'collection': coll_name,
                        'type': 'nl'
                    })
            except Exception as e:
                if self.verbose:
                    print(f"Error querying {coll_name}: {e}", file=sys.stderr)

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def search_code_collection(
        self,
        query: str,
        collection_pattern: str = 'code-*-code',
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Search code collections"""
        results = []
        collections = self.list_collections()

        # Find matching code collections
        code_collections = [c for c in collections if '-code' in c and c.startswith('code-')]

        if self.verbose:
            print(f"Code collections found: {code_collections}", file=sys.stderr)

        for coll_name in code_collections:
            try:
                collection = self.client.get_collection(
                    name=coll_name,
                    embedding_function=self.embedding_fn
                )

                query_results = collection.query(
                    query_texts=[query],
                    n_results=top_k
                )

                # Format results
                for i in range(len(query_results['ids'][0])):
                    results.append({
                        'id': query_results['ids'][0][i],
                        'pattern': query_results['documents'][0][i],
                        'metadata': query_results['metadatas'][0][i],
                        'distance': query_results['distances'][0][i],
                        'score': 1 - query_results['distances'][0][i],
                        'collection': coll_name,
                        'type': 'code'
                    })
            except Exception as e:
                if self.verbose:
                    print(f"Error querying {coll_name}: {e}", file=sys.stderr)

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def filter_by_ast(
        self,
        results: List[Dict[str, Any]],
        ast_criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Filter results by AST metadata"""
        if not ast_criteria:
            return results

        filtered = []
        for result in results:
            metadata = result.get('metadata', {})

            # Check AST criteria
            match = True
            for key, value in ast_criteria.items():
                if key not in metadata or metadata[key] != value:
                    match = False
                    break

            if match:
                filtered.append(result)

        return filtered

    def combine_and_rank(
        self,
        nl_results: List[Dict[str, Any]],
        code_results: List[Dict[str, Any]],
        nl_weight: float = 0.4,
        code_weight: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Combine and rank NL + code results"""
        combined = {}

        # Add NL results with weighted scores
        for result in nl_results:
            doc_id = result['id']
            if doc_id not in combined:
                combined[doc_id] = result.copy()
                combined[doc_id]['combined_score'] = result['score'] * nl_weight
                combined[doc_id]['sources'] = ['nl']
            else:
                combined[doc_id]['combined_score'] += result['score'] * nl_weight
                if 'nl' not in combined[doc_id]['sources']:
                    combined[doc_id]['sources'].append('nl')

        # Add code results with weighted scores
        for result in code_results:
            doc_id = result['id']
            if doc_id not in combined:
                combined[doc_id] = result.copy()
                combined[doc_id]['combined_score'] = result['score'] * code_weight
                combined[doc_id]['sources'] = ['code']
            else:
                combined[doc_id]['combined_score'] += result['score'] * code_weight
                if 'code' not in combined[doc_id]['sources']:
                    combined[doc_id]['sources'].append('code')

        # Convert to list and sort by combined score
        ranked = list(combined.values())
        ranked.sort(key=lambda x: x['combined_score'], reverse=True)

        return ranked

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        ast_criteria: Optional[Dict[str, Any]] = None,
        nl_weight: float = 0.4,
        code_weight: float = 0.6
    ) -> Dict[str, Any]:
        """
        Execute hybrid search across NL and code collections

        Args:
            query: Search query
            top_k: Number of results per collection
            ast_criteria: Optional AST metadata filter
            nl_weight: Weight for NL results (0-1)
            code_weight: Weight for code results (0-1)

        Returns:
            Dictionary with semantic results, AST filtered results, combined ranking
        """
        if self.verbose:
            print(f"\nExecuting hybrid search for: '{query}'", file=sys.stderr)
            print(f"Top-K: {top_k}, NL weight: {nl_weight}, Code weight: {code_weight}", file=sys.stderr)

        # Step 1: Semantic search in NL collection
        nl_results = self.search_nl_collection(query, top_k=top_k)

        # Step 2: Semantic search in code collection
        code_results = self.search_code_collection(query, top_k=top_k)

        # Step 3: Filter by AST metadata if provided
        ast_filtered_nl = self.filter_by_ast(nl_results, ast_criteria) if ast_criteria else nl_results
        ast_filtered_code = self.filter_by_ast(code_results, ast_criteria) if ast_criteria else code_results

        # Step 4: Combine and rank results
        combined = self.combine_and_rank(
            ast_filtered_nl,
            ast_filtered_code,
            nl_weight=nl_weight,
            code_weight=code_weight
        )

        return {
            'semantic_results': {
                'nl': [{'pattern': r['pattern'], 'score': r['score'], 'metadata': r['metadata']} for r in nl_results],
                'code': [{'pattern': r['pattern'], 'score': r['score'], 'metadata': r['metadata']} for r in code_results]
            },
            'ast_filtered_results': {
                'nl': [{'pattern': r['pattern'], 'score': r['score'], 'metadata': r['metadata']} for r in ast_filtered_nl],
                'code': [{'pattern': r['pattern'], 'score': r['score'], 'metadata': r['metadata']} for r in ast_filtered_code]
            },
            'combined_ranking': [
                {
                    'pattern': r['pattern'],
                    'combined_score': r['combined_score'],
                    'sources': r['sources'],
                    'metadata': r['metadata']
                }
                for r in combined[:top_k]
            ],
            'total_results': len(combined)
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Hybrid search on ChromaDB for code learning')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--db-path', default='~/.claude/knowledge/chromadb', help='ChromaDB path')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results per collection')
    parser.add_argument('--nl-weight', type=float, default=0.4, help='Weight for NL results')
    parser.add_argument('--code-weight', type=float, default=0.6, help='Weight for code results')
    parser.add_argument('--ast-filter', help='AST filter as JSON (e.g., {"language": "rust"})')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--list-collections', action='store_true', help='List all collections and exit')

    args = parser.parse_args()

    # Initialize search
    searcher = HybridCodeSearch(
        db_path=args.db_path,
        verbose=args.verbose
    )

    # List collections if requested
    if args.list_collections:
        collections = searcher.list_collections()
        print(json.dumps({'collections': collections}, indent=2))
        return

    # Require query if not listing collections
    if not args.query:
        parser.error('query argument is required unless --list-collections is used')
        return

    # Parse AST filter if provided
    ast_criteria = None
    if args.ast_filter:
        ast_criteria = json.loads(args.ast_filter)

    # Execute hybrid search
    results = searcher.hybrid_search(
        query=args.query,
        top_k=args.top_k,
        ast_criteria=ast_criteria,
        nl_weight=args.nl_weight,
        code_weight=args.code_weight
    )

    # Output results as JSON
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
