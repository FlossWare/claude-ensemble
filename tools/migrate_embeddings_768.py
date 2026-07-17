#!/usr/bin/env python3
"""
Migrate all embeddings from 384-dim to 768-dim using all-mpnet-base-v2.
Runs on laptop-01 and laptop-02 ONLY (not aio-01, not servers).

Embedding generation: local all-mpnet-base-v2 model
DB operations: ALL via orchestrator REST API at aio-01:5000

Usage:
    python3 tools/migrate_embeddings_768.py --embed-only                     # All tables
    python3 tools/migrate_embeddings_768.py --embed-only --worker laptop-01  # knowledge.* only
    python3 tools/migrate_embeddings_768.py --embed-only --worker laptop-02  # Everything else
    python3 tools/migrate_embeddings_768.py --embed-only --table knowledge.documents
    python3 tools/migrate_embeddings_768.py --embed-only --batch-size 200
    python3 tools/migrate_embeddings_768.py --dry-run
"""

import argparse
import sys
import time
import json
import requests
from sentence_transformers import SentenceTransformer

API_BASE = 'http://aio-01:5000'
MODEL_NAME = 'all-mpnet-base-v2'
TARGET_DIM = 768
BATCH_SIZE = 100

# Tables to migrate: (schema.table, embedding_column, text_column)
TABLES = [
    # knowledge schema
    ('knowledge.documents', 'embedding', 'content'),
    ('knowledge.scraped_content', 'embedding', 'content'),
    ('knowledge.code_embeddings', 'embedding', 'content'),
    ('knowledge.scraped_data', 'embedding', 'chunk_text'),
    ('knowledge.entries', 'embedding', 'content'),
    ('knowledge.discoveries', 'embedding', 'content'),
    ('knowledge.pubmed_articles', 'embedding', 'abstract'),
    ('knowledge.web_articles', 'embedding', 'content'),
    ('knowledge.web_scrape', 'embedding', 'content'),
    ('knowledge.concepts', 'embedding', 'name'),
    ('knowledge.research_findings', 'embedding', 'content'),
    # learning schema
    ('learning.session_chunks', 'chunk_embedding', 'chunk_text'),
    ('learning.research_chunks', 'chunk_embedding', 'chunk_text'),
    ('learning.conversation_learnings', 'embedding', 'content'),
    ('learning.comprehensive_research', 'embedding', 'document'),
    ('learning.pdf_metadata', 'embedding', 'text_preview'),
    ('learning.experiences', 'embedding', 'strategy'),
    ('learning.codebase_analysis', 'embedding', 'embedding_text'),
    ('learning.pdf_knowledge', 'embedding', 'claim'),
    ('learning.memory', 'embedding', 'content'),
    ('learning.memories', 'embedding', 'content'),
    ('learning.icl_examples', 'embedding', 'input'),
    ('learning.sessions', 'content_embedding', 'full_content'),
    ('learning.sessions', 'summary_embedding', 'summary'),
    ('learning.sessions', 'title_embedding', 'title'),
    ('learning.gitlab_issues', 'embedding', 'description'),
    ('learning.claude_memory', 'embedding', 'document'),
    ('learning.research_findings', 'embedding', 'document'),
    ('learning.research_full', 'embedding', 'chunk_text'),
    ('learning.security_policies', 'embedding', 'description'),
    ('learning.security_violations', 'embedding', 'code_snippet'),
    ('learning.analogical_patterns', 'embedding', 'solution'),
    ('learning.error_logs', 'embedding', 'message'),
    ('learning.git_commits', 'embedding', 'message'),
    ('learning.vec_claude_memory', 'embedding', 'document'),
    ('learning.experiences_experiment', 'embedding', 'strategy'),
    ('learning.metadata_schema_test', 'embedding', 'content'),
    ('learning.vec_scale_test_1783055901', 'embedding', 'document'),
    ('learning.vec_scale_test_1783055962', 'embedding', 'document'),
    ('learning.vec_scale_test_1783055991', 'embedding', 'document'),
    ('learning.vec_scale_test_1783056573', 'embedding', 'document'),
    # processing schema
    ('processing.chunks', 'embedding', 'chunk_text'),
    # documents schema
    ('documents.chunks', 'embedding', 'content'),
    # workflow schema
    ('workflow.worker_results', 'result_embedding', 'result'),
    ('workflow.executions', 'task_embedding', 'task_description'),
    ('workflow.learnings', 'learning_embedding', 'description'),
    ('workflow.consensus_cache', 'question_embedding', 'question'),
    ('workflow.arbiter_decisions', 'decision_embedding', 'decision'),
    # orchestration schema
    ('orchestration.task_queue', 'embedding', 'description'),
    ('orchestration.auto_storage', 'embedding', 'text'),
    # reasoning schema
    ('reasoning.evidence', 'embedding', 'evidence_text'),
    ('reasoning.hypotheses', 'embedding', 'hypothesis_text'),
]

WORKER_SPLITS = {
    'laptop-01': [t for t in TABLES if t[0].startswith('knowledge.')],
    'laptop-02': [t for t in TABLES if not t[0].startswith('knowledge.')],
}


def api_query(sql: str) -> dict:
    """Execute SQL via orchestrator REST API."""
    try:
        resp = requests.post(f'{API_BASE}/storage/query',
                             json={'query': sql}, timeout=600)
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def local_embed(model, texts: list) -> list:
    """Generate 768-dim embeddings using local model."""
    safe_texts = [t if t else '' for t in texts]
    embeddings = model.encode(safe_texts, show_progress_bar=False,
                              normalize_embeddings=True)
    return embeddings.tolist()


def get_null_count(schema_table: str, embed_col: str) -> int:
    """Get count of rows with NULL embeddings."""
    r = api_query(f"SELECT COUNT(*) FROM {schema_table} WHERE {embed_col} IS NULL")
    if r.get('results'):
        return r['results'][0][0]
    return 0


def get_total_count(schema_table: str) -> int:
    """Get total row count."""
    r = api_query(f"SELECT COUNT(*) FROM {schema_table}")
    if r.get('results'):
        return r['results'][0][0]
    return -1


MAX_TEXT_LEN = 500

def fetch_batch(schema_table: str, embed_col: str, text_col: str,
                batch_size: int, reverse: bool = False) -> list:
    """Fetch a batch of rows with NULL embeddings via REST API."""
    order = "ORDER BY id DESC" if reverse else "ORDER BY id"
    sql = (f"SELECT id, left({text_col}, {MAX_TEXT_LEN}) FROM {schema_table} "
           f"WHERE {embed_col} IS NULL {order} LIMIT {batch_size}")
    r = api_query(sql)
    if r.get('results'):
        return [(row[0], row[1] or '') for row in r['results']]
    if r.get('error'):
        print(f'    Fetch error: {r["error"][:200]}')
    return []


def update_embeddings(schema_table: str, embed_col: str,
                      updates: list) -> int:
    """Update embeddings in batch via REST API. updates = [(id, embedding), ...]"""
    if not updates:
        return 0

    values = []
    for row_id, emb in updates:
        vec_str = '[' + ','.join(f'{x:.6f}' for x in emb) + ']'
        if isinstance(row_id, int):
            values.append(f"({row_id}, '{vec_str}'::vector)")
        else:
            safe_id = str(row_id).replace("'", "''")
            values.append(f"('{safe_id}', '{vec_str}'::vector)")

    # Detect if IDs are text-based to add proper cast
    first_id = updates[0][0]
    if isinstance(first_id, int):
        id_cast = "::bigint"
    else:
        id_cast = "::text"

    sql = (f"UPDATE {schema_table} AS t SET {embed_col} = v.emb "
           f"FROM (VALUES {','.join(values)}) AS v(id, emb) "
           f"WHERE t.id{id_cast} = v.id{id_cast}")

    r = api_query(sql)
    if r.get('success'):
        return r.get('rowcount', len(updates))
    if r.get('error'):
        print(f'    Update error: {r["error"][:200]}')
    return 0


def rebuild_index(schema_table: str, embed_col: str):
    """Rebuild HNSW index via REST API."""
    schema, table = schema_table.split('.')
    idx_name = f'idx_{table}_{embed_col}'
    sql = (f"CREATE INDEX IF NOT EXISTS {idx_name} ON {schema_table} "
           f"USING hnsw ({embed_col} vector_cosine_ops) "
           f"WITH (m = 16, ef_construction = 64)")
    r = api_query(sql)
    if r.get('error'):
        print(f'    Index rebuild error: {r["error"][:200]}')


def migrate_table(model, schema_table: str, embed_col: str, text_col: str,
                  batch_size: int, dry_run: bool = False,
                  reverse: bool = False) -> int:
    """Re-embed all NULL embeddings in a table using local model."""
    total = get_null_count(schema_table, embed_col)

    if total == 0:
        print(f'  {schema_table}.{embed_col}: all embedded, skipping')
        return 0

    if dry_run:
        print(f'  {schema_table}.{embed_col}: {total} rows would be re-embedded')
        return total

    direction = ' (high IDs first)' if reverse else ''
    print(f'  {schema_table}.{embed_col}: {total} rows via {text_col}{direction}...')

    embedded = 0
    table_start = time.time()
    consecutive_failures = 0

    while embedded < total:
        rows = fetch_batch(schema_table, embed_col, text_col, batch_size,
                           reverse=reverse)
        if not rows:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print(f'    3 consecutive empty fetches, stopping')
                break
            continue
        consecutive_failures = 0

        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]

        embeddings = local_embed(model, texts)

        updates = list(zip(ids, embeddings))
        updated = update_embeddings(schema_table, embed_col, updates)

        if updated == 0:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print(f'    3 consecutive update failures, stopping')
                break
            continue
        consecutive_failures = 0

        embedded += updated
        elapsed = time.time() - table_start
        rate = embedded / max(1, elapsed)
        remaining = (total - embedded) / max(1, rate)
        print(f'    {embedded}/{total} ({100*embedded/total:.1f}%) - '
              f'{rate:.1f}/s - ETA {remaining/60:.1f}m')

    return embedded


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate embeddings to 768-dim')
    parser.add_argument('--table', help='Single table to migrate (schema.table)')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--embed-only', action='store_true',
                        help='Only re-embed (columns already altered)')
    parser.add_argument('--worker',
                        help='Worker name (laptop-01 or laptop-02)')
    parser.add_argument('--reverse', action='store_true',
                        help='Process from highest IDs down (for parallel split)')
    args = parser.parse_args()

    print(f'Loading {MODEL_NAME}...')
    model = SentenceTransformer(MODEL_NAME)
    test = model.encode(['test'])
    assert test.shape[1] == TARGET_DIM, \
        f'Model produces {test.shape[1]} dims, expected {TARGET_DIM}'
    print(f'Model ready: {TARGET_DIM}-dim embeddings')

    tables = TABLES
    if args.table:
        tables = [(t, e, tx) for t, e, tx in TABLES if t == args.table]
        if not tables:
            print(f'Table {args.table} not found in migration list')
            sys.exit(1)
    elif args.worker:
        tables = WORKER_SPLITS.get(args.worker, TABLES)
        print(f'Worker {args.worker}: processing {len(tables)} tables')

    start_time = time.time()
    total_embedded = 0

    for schema_table, embed_col, text_col in tables:
        total_rows = get_total_count(schema_table)
        if total_rows <= 0:
            print(f'  {schema_table}: empty or does not exist, skipping')
            continue

        print(f'\n--- {schema_table} ({total_rows} rows) ---')

        count = migrate_table(model, schema_table, embed_col, text_col,
                              args.batch_size, args.dry_run,
                              reverse=args.reverse)
        total_embedded += count

        if count > 0 and not args.dry_run:
            print(f'  Rebuilding HNSW index...')
            rebuild_index(schema_table, embed_col)
            print(f'  Index rebuilt')

    elapsed = time.time() - start_time
    print(f'\nDone: {total_embedded} embeddings in {elapsed/60:.1f} minutes '
          f'({total_embedded/max(1,elapsed):.1f}/s)')
