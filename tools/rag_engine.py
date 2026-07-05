#!/usr/bin/env python3
"""
RAG Orchestration Engine - Production Ready
Query → Vector Search → API Model → Answer + Sources

Features:
- PostgreSQL + pgvector for vector search (learning.experiences)
- Embedding generation via sentence-transformers
- Free API models (Groq, OpenRouter, Anthropic via proxy)
- Error recovery with exponential backoff
- Cost tracking and monitoring
- Full logging to PostgreSQL
- Graceful degradation if embeddings unavailable

Usage:
    from rag_engine import RAGEngine

    rag = RAGEngine()
    result = rag.query("How do I optimize fleet execution?")
    print(result['answer'])
    print(result['sources'])
"""

import sys
import os
import json
import time
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import fleet executor for API calls
from shared.fleet_executor import execute_on_worker, map_model_to_provider

# Import PostgreSQL adapters
try:
    from learning.postgres_adapter import get_db, get_experience_memory, get_cost_tracker, get_execution_monitor
    HAS_POSTGRES = True
except ImportError:
    print("⚠️  PostgreSQL adapter not available - running in degraded mode")
    HAS_POSTGRES = False

# Import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    print("⚠️  sentence-transformers not available - install with: pip3 install sentence-transformers")
    HAS_EMBEDDINGS = False


class RAGEngine:
    """RAG Orchestration Engine with vector search + API models"""

    # Verified free API models (2026-07-04)
    VERIFIED_FREE_MODELS = [
        'llama-3.3-70b-versatile',           # Groq - fast, reliable
        'llama-3.1-8b-instant',               # Groq - ultra fast
        'gpt-4o-mini',                        # OpenAI - high quality
        'claude-3-5-haiku-20241022',          # Anthropic - best reasoning
        'gemini-2.5-flash',                   # Google - fast + cheap
    ]

    def __init__(
        self,
        model: Optional[str] = None,
        embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2',
        max_sources: int = 5,
        enable_logging: bool = True
    ):
        """
        Initialize RAG engine

        Args:
            model: API model to use (auto-selects if None)
            embedding_model: Sentence transformer model for embeddings
            max_sources: Maximum number of sources to retrieve
            enable_logging: Enable PostgreSQL logging
        """
        self.model = model or self.VERIFIED_FREE_MODELS[0]
        self.max_sources = max_sources
        self.enable_logging = enable_logging

        # Initialize database connections
        if HAS_POSTGRES:
            try:
                self.db = get_db()
                self.experience_memory = get_experience_memory()
                self.cost_tracker = get_cost_tracker()
                self.execution_monitor = get_execution_monitor()
                print(f"✅ Connected to PostgreSQL (learning database)")
            except Exception as e:
                print(f"⚠️  PostgreSQL connection failed: {e}")
                self.db = None
                self.experience_memory = None
                self.cost_tracker = None
                self.execution_monitor = None
        else:
            self.db = None
            self.experience_memory = None
            self.cost_tracker = None
            self.execution_monitor = None

        # Initialize embedding model
        if HAS_EMBEDDINGS:
            try:
                import warnings
                warnings.filterwarnings('ignore')
                self.embedding_model = SentenceTransformer(embedding_model)
                print(f"✅ Loaded embedding model: {embedding_model}")
            except Exception as e:
                print(f"⚠️  Embedding model load failed: {e}")
                self.embedding_model = None
        else:
            self.embedding_model = None

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text"""
        if not self.embedding_model:
            return None

        try:
            embedding = self.embedding_model.encode(text.strip())
            return embedding.tolist()
        except Exception as e:
            print(f"⚠️  Embedding generation failed: {e}")
            return None

    def vector_search(
        self,
        query: str,
        limit: int = None,
        filters: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant examples using vector similarity

        Args:
            query: Search query
            limit: Max results (default: self.max_sources)
            filters: Optional filters (success=True, min_reward=0.7, etc.)

        Returns:
            List of relevant examples with metadata
        """
        limit = limit or self.max_sources

        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            print("⚠️  No embeddings available - returning empty results")
            return []

        # Search PostgreSQL
        if not self.experience_memory:
            print("⚠️  Experience memory not available - returning empty results")
            return []

        try:
            results = self.experience_memory.find_similar(
                embedding=query_embedding,
                limit=limit,
                filters=filters or {'success': True, 'min_reward': 0.5}
            )

            print(f"📊 Found {len(results)} relevant examples (distance: {results[0]['distance']:.4f} - {results[-1]['distance']:.4f})")
            return results

        except Exception as e:
            print(f"⚠️  Vector search failed: {e}")
            traceback.print_exc()
            return []

    def format_context(self, sources: List[Dict[str, Any]]) -> str:
        """Format sources into context for LLM"""
        if not sources:
            return "No relevant examples found in knowledge base."

        context_parts = ["Here are relevant examples from the knowledge base:\n"]

        for i, source in enumerate(sources, 1):
            context_parts.append(f"\n=== Example {i} (Reward: {source.get('reward', 0):.2f}) ===")
            context_parts.append(f"Problem Type: {source.get('problem_type', 'unknown')}")
            context_parts.append(f"Strategy: {source.get('strategy', 'unknown')}")

            # Include context if available
            if source.get('context'):
                try:
                    ctx = json.loads(source['context']) if isinstance(source['context'], str) else source['context']
                    context_parts.append(f"Context: {json.dumps(ctx, indent=2)}")
                except:
                    pass

            context_parts.append(f"Success: {source.get('success', False)}")
            context_parts.append(f"Novelty: {source.get('novelty_score', 0):.2f}")
            context_parts.append("")

        return "\n".join(context_parts)

    def call_api_model(
        self,
        prompt: str,
        max_tokens: int = 2048,
        timeout_ms: int = 30000
    ) -> Dict[str, Any]:
        """
        Call free API model via fleet executor

        Args:
            prompt: Full prompt (context + query)
            max_tokens: Max response tokens
            timeout_ms: Timeout in milliseconds

        Returns:
            Dict with output, duration_ms, tokens, cost_usd, error (if failed)
        """
        try:
            result = execute_on_worker(
                worker='aio-01',  # Local orchestrator
                model=self.model,
                task=prompt,
                max_tokens=max_tokens,
                timeout_ms=timeout_ms,
                max_retries=2,
                backoff_seconds=1.0
            )

            return result

        except Exception as e:
            print(f"❌ API call failed: {e}")
            traceback.print_exc()
            return {
                'error': str(e),
                'duration_ms': 0,
                'input_tokens': 0,
                'output_tokens': 0,
                'cost_usd': 0.0
            }

    def query(
        self,
        question: str,
        include_sources: bool = True,
        max_tokens: int = 2048
    ) -> Dict[str, Any]:
        """
        RAG query: vector search → format context → call API → return answer + sources

        Args:
            question: User question
            include_sources: Include source metadata in response
            max_tokens: Max tokens for API response

        Returns:
            Dict with:
                - answer: LLM response
                - sources: List of source documents (if include_sources=True)
                - metadata: Execution metadata (duration, cost, model, etc.)
                - error: Error message (if failed)
        """
        start_time = time.time()

        print(f"\n🔍 RAG Query: {question}\n")

        # Step 1: Vector search
        print("📊 Searching knowledge base...")
        sources = self.vector_search(question)

        # Step 2: Format context
        context = self.format_context(sources)

        # Step 3: Build full prompt
        prompt = f"""You are a helpful AI assistant with access to a knowledge base of past experiences.

{context}

Based on the above examples and your knowledge, please answer this question:

{question}

Provide a clear, actionable answer. If the examples are relevant, reference them. If not, use your general knowledge."""

        # Step 4: Call API model
        print(f"🤖 Calling {self.model}...")
        api_result = self.call_api_model(prompt, max_tokens=max_tokens)

        # Step 5: Extract answer
        if 'error' in api_result:
            answer = f"Error: {api_result['error']}"
            success = False
        else:
            answer = api_result.get('output', api_result.get('text', 'No response'))
            success = True

        # Step 6: Calculate metadata
        total_duration_ms = int((time.time() - start_time) * 1000)

        metadata = {
            'model': self.model,
            'provider': map_model_to_provider(self.model),
            'total_duration_ms': total_duration_ms,
            'api_duration_ms': api_result.get('duration_ms', 0),
            'vector_search_duration_ms': total_duration_ms - api_result.get('duration_ms', 0),
            'input_tokens': api_result.get('input_tokens', 0),
            'output_tokens': api_result.get('output_tokens', 0),
            'cost_usd': api_result.get('cost_usd', 0.0),
            'sources_found': len(sources),
            'timestamp': datetime.now().isoformat()
        }

        # Step 7: Log to PostgreSQL
        if self.enable_logging and success:
            self._log_execution(question, answer, metadata, sources)

        # Step 8: Build response
        response = {
            'answer': answer,
            'metadata': metadata,
            'success': success
        }

        if include_sources:
            response['sources'] = [
                {
                    'problem_type': s.get('problem_type'),
                    'strategy': s.get('strategy'),
                    'reward': s.get('reward'),
                    'success': s.get('success'),
                    'distance': s.get('distance'),
                    'context': s.get('context')
                }
                for s in sources
            ]

        print(f"\n✅ RAG query complete ({total_duration_ms}ms, {len(sources)} sources, ${metadata['cost_usd']:.6f})\n")

        return response

    def _log_execution(
        self,
        question: str,
        answer: str,
        metadata: Dict[str, Any],
        sources: List[Dict]
    ):
        """Log execution to PostgreSQL"""
        try:
            # Log to execution monitor
            if self.execution_monitor:
                self.execution_monitor.log_execution({
                    'model': metadata['model'],
                    'workflow': 'rag_query',
                    'task_type': 'retrieval_augmented_generation',
                    'quality_score': 0.8,  # Default score (could add evaluation later)
                    'input_tokens': metadata['input_tokens'],
                    'output_tokens': metadata['output_tokens'],
                    'cost_usd': metadata['cost_usd'],
                    'duration_ms': metadata['api_duration_ms'],
                    'outcome': 'success'
                })

            # Log to cost tracker
            if self.cost_tracker:
                self.cost_tracker.log_cost({
                    'model': metadata['model'],
                    'input_tokens': metadata['input_tokens'],
                    'output_tokens': metadata['output_tokens'],
                    'total_cost': metadata['cost_usd']
                })

        except Exception as e:
            print(f"⚠️  Logging failed (non-fatal): {e}")


def main():
    """CLI interface for RAG engine"""
    import argparse

    parser = argparse.ArgumentParser(description='RAG Orchestration Engine')
    parser.add_argument('question', nargs='?', help='Question to ask (or use --interactive)')
    parser.add_argument('--model', '-m', default=None, help='API model to use')
    parser.add_argument('--max-sources', '-s', type=int, default=5, help='Max sources to retrieve')
    parser.add_argument('--max-tokens', '-t', type=int, default=2048, help='Max response tokens')
    parser.add_argument('--no-sources', action='store_true', help='Hide source metadata')
    parser.add_argument('--no-logging', action='store_true', help='Disable PostgreSQL logging')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    parser.add_argument('--json', action='store_true', help='JSON output')

    args = parser.parse_args()

    # Initialize engine
    rag = RAGEngine(
        model=args.model,
        max_sources=args.max_sources,
        enable_logging=not args.no_logging
    )

    # Interactive mode
    if args.interactive:
        print("\n🤖 RAG Engine - Interactive Mode")
        print("Type your questions (Ctrl+D to exit)\n")

        while True:
            try:
                question = input("❓ Question: ").strip()
                if not question:
                    continue

                result = rag.query(
                    question,
                    include_sources=not args.no_sources,
                    max_tokens=args.max_tokens
                )

                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(f"\n💡 Answer:\n{result['answer']}\n")
                    if not args.no_sources and result.get('sources'):
                        print(f"📚 Sources: {len(result['sources'])} relevant examples")
                    print(f"⏱️  {result['metadata']['total_duration_ms']}ms, ${result['metadata']['cost_usd']:.6f}\n")

            except EOFError:
                print("\n👋 Goodbye!")
                break
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break

    # Single question mode
    elif args.question:
        result = rag.query(
            args.question,
            include_sources=not args.no_sources,
            max_tokens=args.max_tokens
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n💡 Answer:\n{result['answer']}\n")
            if not args.no_sources and result.get('sources'):
                print(f"\n📚 Sources ({len(result['sources'])}):")
                for i, source in enumerate(result['sources'], 1):
                    print(f"  {i}. {source['problem_type']} (reward={source['reward']:.2f}, strategy={source['strategy']})")
            print(f"\n⏱️  {result['metadata']['total_duration_ms']}ms, ${result['metadata']['cost_usd']:.6f}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
