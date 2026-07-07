#!/usr/bin/env python3
"""
Scale Testing Framework for PostgreSQL + pgvector RAG System

Tests production readiness at 1M searches/day (12 searches/second sustained)

Test Suite:
1. Ingestion at scale (10,000 documents)
2. Search load (12 concurrent searches/sec for 10 min)
3. Concurrent writes (100 simultaneous uploads)
4. Database growth (100K+ chunks with HNSW index)
5. Memory/resource usage tracking
6. Latency under load (P50, P95, P99)

Usage:
    python3 scale_testing.py --test ingestion --documents 10000
    python3 scale_testing.py --test search_load --duration 600 --qps 12
    python3 scale_testing.py --test concurrent_writes --workers 100
    python3 scale_testing.py --test full --output results.json
"""

import sys
import os
import time
import json
import psycopg2
import psycopg2.extras
from psycopg2 import sql as psycopg2_sql
import hashlib
import argparse
import threading
import subprocess
import random
import statistics
from datetime import datetime
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# Import vector store
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import VectorStore directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "vector_store_postgres",
    os.path.join(os.path.dirname(__file__), '..', 'shared', 'vector-store-postgres.py')
)
vector_store_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vector_store_module)
VectorStore = vector_store_module.VectorStore


class ScaleTestRunner:
    """Execute scale tests against PostgreSQL + pgvector"""

    def __init__(self, host='aio-01', port=5433, database='learning', user='sfloess'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.conn = psycopg2.connect(host=host, port=port, database=database, user=user)
        self.conn.autocommit = True

        # Test collection
        self.test_collection = f'scale_test_{int(time.time())}'
        self.vector_store = VectorStore(
            collection=self.test_collection,
            host=host,
            port=port,
            database=database,
            user=user,
            verbose=False
        )

        # Metrics
        self.metrics = {
            'start_time': time.time(),
            'tests': {},
            'resource_usage': []
        }

    def generate_test_document(self, doc_id: int, size: str = 'medium') -> str:
        """Generate synthetic test document"""
        sizes = {
            'small': 100,   # ~100 words
            'medium': 500,  # ~500 words
            'large': 2000   # ~2000 words
        }

        word_count = sizes.get(size, 500)

        # Generate realistic technical content
        topics = [
            'firmware reverse engineering and security analysis',
            'vector database indexing strategies with HNSW',
            'PostgreSQL query optimization techniques',
            'machine learning model fine-tuning approaches',
            'distributed systems architecture patterns',
            'network protocol analysis and debugging',
            'compiler optimization and code generation',
            'cryptographic algorithm implementation'
        ]

        topic = random.choice(topics)
        words = [f'word{i}' for i in range(word_count)]

        return f"Document {doc_id}: {topic}. " + " ".join(words)

    def test_ingestion_scale(self, num_documents: int = 10000, batch_size: int = 100) -> Dict[str, Any]:
        """Test 1: Ingestion at scale"""
        print(f"\n{'='*70}")
        print(f"TEST 1: Ingestion at Scale ({num_documents:,} documents)")
        print(f"{'='*70}")

        start_time = time.time()
        ingestion_times = []

        for batch_start in range(0, num_documents, batch_size):
            batch_end = min(batch_start + batch_size, num_documents)
            batch_num = batch_start // batch_size + 1

            batch_start_time = time.time()

            # Generate batch
            texts = [self.generate_test_document(i) for i in range(batch_start, batch_end)]
            metadatas = [{'doc_id': i, 'batch': batch_num} for i in range(batch_start, batch_end)]

            # Insert batch
            self.vector_store.add_batch(texts, metadatas=metadatas)

            batch_time = time.time() - batch_start_time
            ingestion_times.append(batch_time)

            if batch_num % 10 == 0:
                avg_time = statistics.mean(ingestion_times[-10:])
                print(f"  Batch {batch_num:4d}/{num_documents//batch_size}: {batch_time:.2f}s ({batch_size/batch_time:.1f} docs/s, avg: {batch_size/avg_time:.1f} docs/s)")

        total_time = time.time() - start_time

        # Metrics
        result = {
            'documents_inserted': num_documents,
            'total_time_seconds': total_time,
            'throughput_docs_per_second': num_documents / total_time,
            'batch_size': batch_size,
            'avg_batch_time': statistics.mean(ingestion_times),
            'p50_batch_time': statistics.median(ingestion_times),
            'p95_batch_time': statistics.quantiles(ingestion_times, n=20)[18] if len(ingestion_times) >= 20 else max(ingestion_times),
            'p99_batch_time': statistics.quantiles(ingestion_times, n=100)[98] if len(ingestion_times) >= 100 else max(ingestion_times)
        }

        print(f"\n✓ Ingestion Complete:")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Throughput: {result['throughput_docs_per_second']:.1f} docs/s")
        print(f"  Batch times: P50={result['p50_batch_time']:.2f}s, P95={result['p95_batch_time']:.2f}s, P99={result['p99_batch_time']:.2f}s")

        self.metrics['tests']['ingestion'] = result
        return result

    def test_search_load(self, duration_seconds: int = 600, target_qps: int = 12, concurrency: int = 8) -> Dict[str, Any]:
        """Test 2: Search load testing"""
        print(f"\n{'='*70}")
        print(f"TEST 2: Search Load ({target_qps} QPS for {duration_seconds}s, {concurrency} threads)")
        print(f"{'='*70}")

        # Pre-generate search queries
        query_templates = [
            "firmware security analysis",
            "vector database optimization",
            "PostgreSQL performance tuning",
            "machine learning training",
            "distributed system design",
            "network protocol debugging",
            "compiler code generation",
            "cryptographic implementation"
        ]

        search_latencies = []
        search_results_counts = []
        errors = []

        start_time = time.time()
        end_time = start_time + duration_seconds

        def search_worker(worker_id: int):
            """Worker thread executing searches"""
            local_latencies = []
            local_counts = []
            local_errors = []

            while time.time() < end_time:
                query = random.choice(query_templates)

                search_start = time.time()
                try:
                    results = self.vector_store.query(query, top_k=10)
                    search_time = time.time() - search_start

                    local_latencies.append(search_time * 1000)  # Convert to ms
                    local_counts.append(len(results))
                except Exception as e:
                    local_errors.append(str(e))
                    search_time = time.time() - search_start
                    local_latencies.append(search_time * 1000)

                # Rate limiting to achieve target QPS
                sleep_time = (1.0 / target_qps) - search_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

            return local_latencies, local_counts, local_errors

        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(search_worker, i) for i in range(concurrency)]

            # Progress reporting
            last_report = start_time
            while time.time() < end_time:
                time.sleep(5)
                elapsed = time.time() - start_time
                completed_searches = sum(len(f.result()[0]) for f in futures if f.done())
                current_qps = completed_searches / elapsed if elapsed > 0 else 0
                print(f"  Progress: {elapsed:.0f}s / {duration_seconds}s, Searches: {completed_searches:,}, QPS: {current_qps:.1f}")

            # Collect results
            for future in futures:
                latencies, counts, errs = future.result()
                search_latencies.extend(latencies)
                search_results_counts.extend(counts)
                errors.extend(errs)

        total_time = time.time() - start_time
        total_searches = len(search_latencies)

        # Metrics
        result = {
            'duration_seconds': total_time,
            'total_searches': total_searches,
            'target_qps': target_qps,
            'actual_qps': total_searches / total_time,
            'concurrency': concurrency,
            'latency_p50_ms': statistics.median(search_latencies),
            'latency_p95_ms': statistics.quantiles(search_latencies, n=20)[18] if len(search_latencies) >= 20 else max(search_latencies),
            'latency_p99_ms': statistics.quantiles(search_latencies, n=100)[98] if len(search_latencies) >= 100 else max(search_latencies),
            'latency_min_ms': min(search_latencies),
            'latency_max_ms': max(search_latencies),
            'latency_avg_ms': statistics.mean(search_latencies),
            'avg_results_per_search': statistics.mean(search_results_counts) if search_results_counts else 0,
            'error_count': len(errors),
            'error_rate': len(errors) / total_searches if total_searches > 0 else 0
        }

        print(f"\n✓ Search Load Complete:")
        print(f"  Total searches: {total_searches:,}")
        print(f"  Actual QPS: {result['actual_qps']:.1f}")
        print(f"  Latency: P50={result['latency_p50_ms']:.1f}ms, P95={result['latency_p95_ms']:.1f}ms, P99={result['latency_p99_ms']:.1f}ms")
        print(f"  Errors: {len(errors)} ({result['error_rate']:.2%})")

        self.metrics['tests']['search_load'] = result
        return result

    def test_concurrent_writes(self, num_workers: int = 100, writes_per_worker: int = 10) -> Dict[str, Any]:
        """Test 3: Concurrent write load"""
        print(f"\n{'='*70}")
        print(f"TEST 3: Concurrent Writes ({num_workers} workers, {writes_per_worker} writes each)")
        print(f"{'='*70}")

        write_latencies = []
        errors = []

        def write_worker(worker_id: int):
            """Worker performing concurrent writes"""
            local_latencies = []
            local_errors = []

            for i in range(writes_per_worker):
                doc_text = self.generate_test_document(worker_id * writes_per_worker + i)
                metadata = {'worker': worker_id, 'write_num': i}

                write_start = time.time()
                try:
                    self.vector_store.add(doc_text, metadata=metadata)
                    write_time = time.time() - write_start
                    local_latencies.append(write_time * 1000)
                except Exception as e:
                    local_errors.append(str(e))

            return local_latencies, local_errors

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(write_worker, i) for i in range(num_workers)]

            for future in as_completed(futures):
                latencies, errs = future.result()
                write_latencies.extend(latencies)
                errors.extend(errs)

        total_time = time.time() - start_time
        total_writes = num_workers * writes_per_worker

        # Metrics
        result = {
            'num_workers': num_workers,
            'writes_per_worker': writes_per_worker,
            'total_writes': total_writes,
            'total_time_seconds': total_time,
            'throughput_writes_per_second': total_writes / total_time,
            'latency_p50_ms': statistics.median(write_latencies),
            'latency_p95_ms': statistics.quantiles(write_latencies, n=20)[18] if len(write_latencies) >= 20 else max(write_latencies),
            'latency_p99_ms': statistics.quantiles(write_latencies, n=100)[98] if len(write_latencies) >= 100 else max(write_latencies),
            'error_count': len(errors),
            'error_rate': len(errors) / total_writes if total_writes > 0 else 0
        }

        print(f"\n✓ Concurrent Writes Complete:")
        print(f"  Total writes: {total_writes:,}")
        print(f"  Throughput: {result['throughput_writes_per_second']:.1f} writes/s")
        print(f"  Latency: P50={result['latency_p50_ms']:.1f}ms, P95={result['latency_p95_ms']:.1f}ms, P99={result['latency_p99_ms']:.1f}ms")
        print(f"  Errors: {len(errors)} ({result['error_rate']:.2%})")

        self.metrics['tests']['concurrent_writes'] = result
        return result

    def test_database_growth(self) -> Dict[str, Any]:
        """Test 4: Database growth and index performance"""
        print(f"\n{'='*70}")
        print(f"TEST 4: Database Growth Analysis")
        print(f"{'='*70}")

        table_ident = psycopg2_sql.Identifier('learning', f'vec_{self.test_collection}')
        table_literal = psycopg2_sql.Literal(f'learning.vec_{self.test_collection}')
        tablename_literal = psycopg2_sql.Literal(f'vec_{self.test_collection}')

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Table stats
            cur.execute(psycopg2_sql.SQL("""
                SELECT
                    COUNT(*) as total_rows,
                    pg_size_pretty(pg_total_relation_size({})) as total_size,
                    pg_size_pretty(pg_relation_size({})) as table_size,
                    pg_size_pretty(pg_indexes_size({})) as index_size
                FROM {}
            """).format(table_literal, table_literal, table_literal, table_ident))
            stats = dict(cur.fetchone())

            # Index stats
            cur.execute(psycopg2_sql.SQL("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = {}
            """).format(tablename_literal))
            indexes = [dict(row) for row in cur.fetchall()]

        result = {
            'total_rows': stats['total_rows'],
            'total_size': stats['total_size'],
            'table_size': stats['table_size'],
            'index_size': stats['index_size'],
            'indexes': indexes
        }

        print(f"\n✓ Database Growth:")
        print(f"  Total rows: {result['total_rows']:,}")
        print(f"  Total size: {result['total_size']}")
        print(f"  Table size: {result['table_size']}")
        print(f"  Index size: {result['index_size']}")
        print(f"  Indexes: {len(indexes)}")

        self.metrics['tests']['database_growth'] = result
        return result

    def test_resource_usage(self) -> Dict[str, Any]:
        """Test 5: Resource usage monitoring"""
        print(f"\n{'='*70}")
        print(f"TEST 5: Resource Usage")
        print(f"{'='*70}")

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Database connections
            cur.execute("""
                SELECT
                    COUNT(*) as total_connections,
                    COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity
                WHERE datname = 'learning'
            """)
            connections = dict(cur.fetchone())

            # Cache hit ratio
            cur.execute("""
                SELECT
                    SUM(heap_blks_read) as heap_read,
                    SUM(heap_blks_hit) as heap_hit,
                    CASE
                        WHEN SUM(heap_blks_hit) + SUM(heap_blks_read) > 0
                        THEN ROUND(100.0 * SUM(heap_blks_hit) / (SUM(heap_blks_hit) + SUM(heap_blks_read)), 2)
                        ELSE 0
                    END as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            cache = dict(cur.fetchone())

        result = {
            'connections': connections,
            'cache_hit_ratio': float(cache['cache_hit_ratio']) if cache['cache_hit_ratio'] else 0.0
        }

        print(f"\n✓ Resource Usage:")
        print(f"  Active connections: {connections['active_connections']}")
        print(f"  Idle connections: {connections['idle_connections']}")
        print(f"  Cache hit ratio: {result['cache_hit_ratio']:.2f}%")

        self.metrics['tests']['resource_usage'] = result
        return result

    def calculate_scale_projection(self) -> Dict[str, Any]:
        """Calculate scale projections for 1M searches/day"""
        print(f"\n{'='*70}")
        print(f"SCALE PROJECTION: 1M Searches/Day")
        print(f"{'='*70}")

        target_daily_searches = 1_000_000
        target_qps = target_daily_searches / 86400  # ~11.6 QPS

        search_test = self.metrics['tests'].get('search_load', {})
        actual_qps = search_test.get('actual_qps', 0)
        p99_latency = search_test.get('latency_p99_ms', 0)

        # Scale projections
        headroom_factor = actual_qps / target_qps if target_qps > 0 else 0

        projection = {
            'target_daily_searches': target_daily_searches,
            'target_qps': target_qps,
            'tested_qps': actual_qps,
            'headroom_factor': headroom_factor,
            'can_handle_target': actual_qps >= target_qps,
            'max_daily_searches': int(actual_qps * 86400),
            'p99_latency_at_scale_ms': p99_latency,
            'recommendation': 'PASS' if headroom_factor >= 1.0 else 'NEEDS_OPTIMIZATION'
        }

        print(f"\n✓ Scale Projection:")
        print(f"  Target: {target_daily_searches:,} searches/day ({target_qps:.1f} QPS)")
        print(f"  Tested: {int(projection['max_daily_searches']):,} searches/day ({actual_qps:.1f} QPS)")
        print(f"  Headroom: {headroom_factor:.1f}x")
        print(f"  P99 latency at scale: {p99_latency:.1f}ms")
        print(f"  Verdict: {'✓ PRODUCTION READY' if projection['can_handle_target'] else '✗ NEEDS OPTIMIZATION'}")

        self.metrics['scale_projection'] = projection
        return projection

    def run_full_test_suite(self, num_documents: int = 10000) -> Dict[str, Any]:
        """Run complete test suite"""
        print(f"\n{'#'*70}")
        print(f"# SCALE TEST SUITE - PostgreSQL + pgvector RAG System")
        print(f"# Target: 1M searches/day ({1_000_000/86400:.1f} QPS sustained)")
        print(f"{'#'*70}")

        # Test 1: Ingestion
        self.test_ingestion_scale(num_documents=num_documents)

        # Test 2: Search load
        self.test_search_load(duration_seconds=600, target_qps=12)

        # Test 3: Concurrent writes
        self.test_concurrent_writes(num_workers=100, writes_per_worker=10)

        # Test 4: Database growth
        self.test_database_growth()

        # Test 5: Resource usage
        self.test_resource_usage()

        # Scale projection
        self.calculate_scale_projection()

        # Final summary
        self.metrics['end_time'] = time.time()
        self.metrics['total_duration'] = self.metrics['end_time'] - self.metrics['start_time']

        print(f"\n{'#'*70}")
        print(f"# TEST SUITE COMPLETE")
        print(f"# Total duration: {self.metrics['total_duration']:.1f}s")
        print(f"{'#'*70}")

        return self.metrics

    def cleanup(self):
        """Cleanup test data"""
        print(f"\nCleaning up test collection: {self.test_collection}")
        table_ident = psycopg2_sql.Identifier('learning', f'vec_{self.test_collection}')
        with self.conn.cursor() as cur:
            cur.execute(psycopg2_sql.SQL("DROP TABLE IF EXISTS {}").format(table_ident))
        self.conn.close()
        print("Cleanup complete")


def main():
    parser = argparse.ArgumentParser(description='Scale testing for PostgreSQL + pgvector RAG system')
    parser.add_argument('--test', choices=['ingestion', 'search_load', 'concurrent_writes', 'full'], default='full',
                        help='Test to run')
    parser.add_argument('--documents', type=int, default=10000, help='Number of documents for ingestion test')
    parser.add_argument('--duration', type=int, default=600, help='Duration in seconds for search load test')
    parser.add_argument('--qps', type=int, default=12, help='Target queries per second for search load test')
    parser.add_argument('--workers', type=int, default=100, help='Number of concurrent workers for write test')
    parser.add_argument('--output', type=str, help='Output file for results (JSON)')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup after tests')

    args = parser.parse_args()

    runner = ScaleTestRunner()

    try:
        if args.test == 'ingestion':
            result = runner.test_ingestion_scale(num_documents=args.documents)
        elif args.test == 'search_load':
            result = runner.test_search_load(duration_seconds=args.duration, target_qps=args.qps)
        elif args.test == 'concurrent_writes':
            result = runner.test_concurrent_writes(num_workers=args.workers)
        elif args.test == 'full':
            result = runner.run_full_test_suite(num_documents=args.documents)

        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(runner.metrics, f, indent=2)
            print(f"\n✓ Results saved to: {args.output}")

    finally:
        if not args.no_cleanup:
            runner.cleanup()


if __name__ == '__main__':
    main()
