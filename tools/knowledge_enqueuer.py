#!/usr/bin/env python3
"""Enqueue knowledge.documents/scraped_content/scraped_data into the store queue.

Runs on aio-01 only (reads PostgreSQL directly). Feeds data into the same
Redis store queue that scrapers use, so existing pipeline workers on all
fleet nodes can transform and store the numerical sequences.

Usage:
    python3 knowledge_enqueuer.py                    # all tables
    python3 knowledge_enqueuer.py --table documents   # just documents
    python3 knowledge_enqueuer.py --batch-size 100
"""

import argparse
import json
import os
import sys
import time
import uuid

BATCH_SIZE_DEFAULT = 100

TABLES = {
    "documents": {
        "sql": (
            "SELECT id, content, COALESCE(category, 'docs') as category, "
            "COALESCE(url, '') as url, COALESCE(title, '') as title "
            "FROM knowledge.documents "
            "WHERE content IS NOT NULL AND id > %s "
            "ORDER BY id LIMIT %s"
        ),
        "content_col": "content",
    },
    "scraped_content": {
        "sql": (
            "SELECT id, content, COALESCE(category, 'scraped') as category, "
            "COALESCE(source_path, '') as url, '' as title "
            "FROM knowledge.scraped_content "
            "WHERE content IS NOT NULL AND id > %s "
            "ORDER BY id LIMIT %s"
        ),
        "content_col": "content",
    },
    "scraped_data": {
        "sql": (
            "SELECT id, chunk_text as content, COALESCE(category, 'scraped') as category, "
            "COALESCE(source_file, '') as url, '' as title "
            "FROM knowledge.scraped_data "
            "WHERE chunk_text IS NOT NULL AND id > %s "
            "ORDER BY id LIMIT %s"
        ),
        "content_col": "content",
    },
}


def get_db():
    import psycopg2
    return psycopg2.connect(
        host='localhost', port=5433,
        dbname='learning', user='postgres'
    )


def get_redis():
    import redis
    return redis.Redis(host='localhost', port=6379, decode_responses=True)


def enqueue_batch(items):
    """Push items directly to Redis store queue (runs on aio-01 only)."""
    r = get_redis()
    enqueued = 0
    pipe = r.pipeline()
    for item in items:
        queue = item.get("queue", "store")
        idem_key = item.get("idempotency_key", "")
        if idem_key:
            exists_key = f"idem:{queue}:{idem_key}"
            if r.exists(exists_key):
                continue
        entry = json.dumps({
            "id": str(uuid.uuid4()),
            "queue": queue,
            "data": item["data"],
            "priority": item.get("priority", 5),
            "status": "pending",
            "created_at": time.time(),
        })
        pipe.rpush(f"queue:{queue}", entry)
        if idem_key:
            pipe.setex(f"idem:{queue}:{idem_key}", 86400, "1")
        enqueued += 1
    pipe.execute()
    return enqueued


def enqueue_table(table_name, batch_size):
    cfg = TABLES[table_name]
    conn = get_db()
    cursor = conn.cursor()

    last_id = 0
    total_enqueued = 0
    total_skipped = 0
    batch = []

    print(f"[enqueuer] Starting knowledge.{table_name} → store queue (batch_size={batch_size})")

    while True:
        cursor.execute(cfg["sql"], (last_id, batch_size))
        rows = cursor.fetchall()

        if not rows:
            if batch:
                total_enqueued += enqueue_batch(batch)
                batch = []
            print(f"  [{time.strftime('%H:%M:%S')}] {table_name}: done after id={last_id}, "
                  f"enqueued={total_enqueued} skipped={total_skipped}")
            break

        for row in rows:
            row_id, content, category, url, title = row
            last_id = row_id

            if not content or len(str(content).strip()) < 50:
                total_skipped += 1
                continue

            content = str(content)[:50000]

            batch.append({
                "queue": "store",
                "data": {
                    "content": content,
                    "url": url[:500] if url else "",
                    "title": title[:500] if title else "",
                    "category": f"k-{category}",
                },
                "priority": 5,
                "idempotency_key": f"k-{table_name[:3]}-{row_id}",
            })

            if len(batch) >= batch_size:
                n = enqueue_batch(batch)
                total_enqueued += n
                batch = []

                if total_enqueued % 1000 == 0 and total_enqueued > 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] {table_name}: "
                          f"enqueued={total_enqueued} last_id={last_id}")

        time.sleep(0.05)

    cursor.close()
    conn.close()
    return total_enqueued


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", choices=list(TABLES.keys()) + ["all"], default="all")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    args = parser.parse_args()

    tables = list(TABLES.keys()) if args.table == "all" else [args.table]
    grand_total = 0

    for t in tables:
        n = enqueue_table(t, args.batch_size)
        grand_total += n
        print(f"  {t}: {n} enqueued")

    print(f"\nTotal enqueued: {grand_total}")


if __name__ == "__main__":
    main()
