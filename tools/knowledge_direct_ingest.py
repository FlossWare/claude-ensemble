#!/usr/bin/env python3
"""Direct DB-to-DB ingestion: knowledge.* → learning.numerical_sequences.

Runs on aio-01 ONLY. Reads directly from PostgreSQL, transforms content to
numeric features, writes directly to numerical_sequences. No Redis, no API,
no queue — just fast batch INSERT.

Usage:
    python3 knowledge_direct_ingest.py
    python3 knowledge_direct_ingest.py --table documents --batch-size 200
"""

import argparse
import hashlib
import math
import re
import sys
import time

import psycopg2
import psycopg2.extras

MAX_SEQUENCE_LENGTH = 5000

CODE_HINTS = {
    "github", "gitlab", "sourcecode", "code", "npm", "pypi", "crates",
    "raw-db-languages", "raw-firmware-code", "os_code_docs_scraper",
    "apache-source", "cloud-native-source", "system-core-source",
    "linux-distro-source", "compilers-dev-source", "databases-source",
    "languages-source", "servers-libs-source", "desktop-wm-source",
    "kde-source", "desktop-media-source", "cloud-virt-platform-source",
    "virt-security-source", "headroom-source", "non-github-source",
}
PAPER_HINTS = {
    "arxiv", "papers", "research", "semanticscholar", "ieee", "acm",
    "thesis-hal", "medrxiv", "biorxiv", "dblp", "pubmed",
}

TABLES = {
    "documents": (
        "SELECT id, content, COALESCE(category, 'docs'), "
        "COALESCE(url, ''), COALESCE(title, '') "
        "FROM knowledge.documents "
        "WHERE content IS NOT NULL AND id > %s ORDER BY id LIMIT %s"
    ),
    "scraped_content": (
        "SELECT id, content, COALESCE(category, 'scraped'), "
        "COALESCE(source_path, ''), '' "
        "FROM knowledge.scraped_content "
        "WHERE content IS NOT NULL AND id > %s ORDER BY id LIMIT %s"
    ),
    "scraped_data": (
        "SELECT id, chunk_text, COALESCE(category, 'scraped'), "
        "COALESCE(source_file, ''), '' "
        "FROM knowledge.scraped_data "
        "WHERE chunk_text IS NOT NULL AND id > %s ORDER BY id LIMIT %s"
    ),
}

INSERT_SQL = """
INSERT INTO learning.numerical_sequences
    (file_id, file_type, subdir, sequence_length, line_lengths, indentation_depths,
     char_frequencies, nesting_patterns, complexity_score, entropy, avg_line_length,
     max_indentation, metadata)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (file_id) DO NOTHING
"""


def detect_type(category):
    cat = (category or "").lower()
    if cat in CODE_HINTS or any(h in cat for h in ("source", "code", "github")):
        return "sourcecode"
    if cat in PAPER_HINTS or any(h in cat for h in ("arxiv", "paper", "thesis", "research")):
        return "papers"
    return "docs"


def compute_char_frequencies(content):
    freq = [0.0] * 256
    total = len(content)
    if total == 0:
        return freq
    for ch in content:
        o = ord(ch)
        if o < 256:
            freq[o] += 1
    for i in range(256):
        freq[i] /= total
    return freq


def compute_entropy(freq):
    return -sum(p * math.log2(p) for p in freq if p > 0)


def compute_nesting(lines):
    depth = 0
    pattern = []
    openers = {"(", "[", "{"}
    closers = {")", "]", "}"}
    for line in lines:
        for ch in line:
            if ch in openers:
                depth += 1
                pattern.append(depth)
            elif ch in closers:
                pattern.append(depth)
                depth = max(0, depth - 1)
    return pattern[:MAX_SEQUENCE_LENGTH]


_kw = re.compile(r'\b(if|else|elif|for|while|switch|case|catch|try|except|finally|do)\b')

def compute_complexity(lines):
    count = sum(len(_kw.findall(line)) for line in lines)
    return count / max(1, len(lines))


def transform(content):
    lines = content.split("\n")
    ll = [len(l) for l in lines[:MAX_SEQUENCE_LENGTH]]
    indent = [len(l) - len(l.lstrip()) for l in lines[:MAX_SEQUENCE_LENGTH]]
    cf = compute_char_frequencies(content)
    nest = compute_nesting(lines)
    cplx = compute_complexity(lines)
    ent = compute_entropy(cf)
    avg_ll = sum(ll) / max(1, len(ll))
    max_ind = max(indent) if indent else 0
    return len(lines), ll, indent, cf, nest, cplx, ent, avg_ll, max_ind


def ingest_table(table_name, batch_size, conn):
    sql = TABLES[table_name]
    read_cur = conn.cursor()
    write_cur = conn.cursor()

    last_id = 0
    total_stored = 0
    total_skipped = 0
    total_dupes = 0
    batch = []

    print(f"[ingest] knowledge.{table_name} → numerical_sequences (batch={batch_size})")

    while True:
        read_cur.execute(sql, (last_id, batch_size))
        rows = read_cur.fetchall()

        if not rows:
            if batch:
                psycopg2.extras.execute_batch(write_cur, INSERT_SQL, batch, page_size=100)
                conn.commit()
                total_stored += len(batch)
                batch = []
            print(f"  [{time.strftime('%H:%M:%S')}] {table_name}: DONE "
                  f"stored={total_stored} skipped={total_skipped} dupes={total_dupes}")
            break

        for row_id, content, category, url, title in rows:
            last_id = row_id

            if not content or len(str(content).strip()) < 50:
                total_skipped += 1
                continue

            content = str(content)[:50000]
            ftype = detect_type(category)
            file_id = f"k-{table_name[:3]}-{hashlib.md5((str(url) + str(row_id)).encode()).hexdigest()[:16]}"

            try:
                seq_len, ll, indent, cf, nest, cplx, ent, avg_ll, max_ind = transform(content)
            except Exception:
                total_skipped += 1
                continue

            import json
            meta = json.dumps({
                "url": (url or "")[:500],
                "title": (title or "")[:500],
                "original_size": len(content),
                "source_table": f"knowledge.{table_name}",
            })

            batch.append((
                file_id, ftype, f"k-{category}", seq_len,
                ll, indent, cf, nest, cplx, ent, avg_ll, max_ind, meta
            ))

            if len(batch) >= batch_size:
                try:
                    psycopg2.extras.execute_batch(write_cur, INSERT_SQL, batch, page_size=100)
                    conn.commit()
                    total_stored += len(batch)
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    for item in batch:
                        try:
                            write_cur.execute(INSERT_SQL, item)
                            conn.commit()
                            total_stored += 1
                        except psycopg2.errors.UniqueViolation:
                            conn.rollback()
                            total_dupes += 1
                except Exception as e:
                    conn.rollback()
                    print(f"  BATCH ERROR: {e}", file=sys.stderr)
                batch = []

                if total_stored % 5000 == 0 and total_stored > 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] {table_name}: "
                          f"stored={total_stored} last_id={last_id} "
                          f"skipped={total_skipped} dupes={total_dupes}")

    read_cur.close()
    write_cur.close()
    return total_stored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", choices=list(TABLES.keys()) + ["all"], default="all")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()

    conn = psycopg2.connect(
        host='localhost', port=5433,
        dbname='learning', user='postgres'
    )

    tables = list(TABLES.keys()) if args.table == "all" else [args.table]
    grand_total = 0

    for t in tables:
        n = ingest_table(t, args.batch_size, conn)
        grand_total += n

    conn.close()
    print(f"\nTotal ingested: {grand_total} sequences")


if __name__ == "__main__":
    main()
