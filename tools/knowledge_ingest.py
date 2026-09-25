#!/usr/bin/env python3
"""Ingest knowledge.documents and knowledge.scraped_content into numerical_sequences.

Reads content from knowledge schema tables via REST API, transforms to
numeric features, and stores via /sequences/batch. All access through
aio-01:5000 REST API — workers never touch PostgreSQL directly.

Usage:
    python3 knowledge_ingest.py              # ingest all eligible rows
    python3 knowledge_ingest.py --table documents --batch-size 50
    python3 knowledge_ingest.py --table scraped_content
    python3 knowledge_ingest.py --table scraped_data
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time

import requests

API_BASE = os.environ.get("GA_API_BASE", "http://aio-01:5000")
MAX_SEQUENCE_LENGTH = 5000
WORKER_ID = f"knowledge-ingest-{os.uname().nodename}-{os.getpid()}"

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


def detect_type(category):
    cat = (category or "").lower()
    if cat in CODE_HINTS or any(h in cat for h in ("source", "code", "github")):
        return "sourcecode"
    if cat in PAPER_HINTS or any(h in cat for h in ("arxiv", "paper", "thesis", "research")):
        return "papers"
    return "docs"


# ── Feature extraction (same as pipeline-worker.py) ──────────────────

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


def compute_complexity(lines):
    keywords = re.compile(
        r'\b(if|else|elif|for|while|switch|case|catch|try|except|finally|do)\b'
    )
    count = sum(len(keywords.findall(line)) for line in lines)
    return count / max(1, len(lines))


def extract_features(content, ftype):
    lines = content.split("\n")
    line_lengths = [len(l) for l in lines[:MAX_SEQUENCE_LENGTH]]
    indentation = [len(l) - len(l.lstrip()) for l in lines[:MAX_SEQUENCE_LENGTH]]
    char_freq = compute_char_frequencies(content)
    nesting = compute_nesting(lines)
    complexity = compute_complexity(lines)
    entropy = compute_entropy(char_freq)
    avg_ll = sum(line_lengths) / max(1, len(line_lengths))
    max_indent = max(indentation) if indentation else 0
    return {
        "sequence_length": len(lines),
        "line_lengths": line_lengths,
        "indentation_depths": indentation,
        "char_frequencies": char_freq,
        "nesting_patterns": nesting,
        "complexity_score": complexity,
        "entropy": entropy,
        "avg_line_length": avg_ll,
        "max_indentation": max_indent,
    }


# ── REST API helpers ─────────────────────────────────────────────────

def api_store_batch(sequences):
    for attempt in range(4):
        try:
            resp = requests.post(
                f"{API_BASE}/sequences/batch",
                json={"sequences": sequences},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("stored", 0)
        except requests.RequestException as e:
            if attempt == 3:
                print(f"  [{WORKER_ID}] store failed after 4 attempts: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return 0


def api_query(sql, params=None):
    """Query knowledge tables via the API's /db/query endpoint."""
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{API_BASE}/db/query",
                json={"sql": sql, "params": params or []},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("rows", [])
        except requests.RequestException as e:
            if attempt == 2:
                print(f"  [{WORKER_ID}] query failed: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return []


def fetch_documents(offset, limit):
    """Fetch documents content via REST API."""
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{API_BASE}/knowledge/documents",
                params={"offset": offset, "limit": limit, "min_length": 50},
                timeout=120,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("documents", resp.json().get("rows", []))
        except requests.RequestException as e:
            if attempt == 2:
                print(f"  [{WORKER_ID}] fetch docs failed: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return []


def fetch_via_sql(table, offset, limit):
    """Fetch rows using /db/query endpoint as fallback."""
    if table == "documents":
        sql = (
            "SELECT id, content, category, url, title "
            "FROM knowledge.documents "
            "WHERE content IS NOT NULL AND length(content) > 50 "
            "ORDER BY id LIMIT %s OFFSET %s"
        )
    elif table == "scraped_content":
        sql = (
            "SELECT id, content, category, source_path as url, '' as title "
            "FROM knowledge.scraped_content "
            "WHERE content IS NOT NULL AND length(content) > 50 "
            "ORDER BY id LIMIT %s OFFSET %s"
        )
    elif table == "scraped_data":
        sql = (
            "SELECT id, chunk_text as content, category, source_file as url, '' as title "
            "FROM knowledge.scraped_data "
            "WHERE chunk_text IS NOT NULL AND length(chunk_text) > 50 "
            "ORDER BY id LIMIT %s OFFSET %s"
        )
    else:
        return []

    return api_query(sql, [limit, offset])


# ── Main ingestion ───────────────────────────────────────────────────

def ingest_table(table, batch_size=50):
    offset = 0
    total_stored = 0
    total_skipped = 0
    total_errors = 0
    batch = []

    print(f"[{WORKER_ID}] Ingesting knowledge.{table} → numerical_sequences "
          f"(batch_size={batch_size})")

    while True:
        if table == "documents":
            rows = fetch_documents(offset, batch_size)
            if rows is None:
                rows = fetch_via_sql(table, offset, batch_size)
        else:
            rows = fetch_via_sql(table, offset, batch_size)

        if not rows:
            if batch:
                total_stored += api_store_batch(batch)
                batch = []
            print(f"  [{time.strftime('%H:%M:%S')}] Done with {table} at offset {offset}. "
                  f"stored={total_stored} skipped={total_skipped} errors={total_errors}")
            break

        for row in rows:
            content = row.get("content", row.get("chunk_text", ""))
            if not content or len(str(content).strip()) < 50:
                total_skipped += 1
                continue

            content = str(content)
            category = row.get("category", table) or table
            url = row.get("url", row.get("source_path", "")) or ""
            title = row.get("title", "") or ""

            ftype = detect_type(category)

            try:
                features = extract_features(content, ftype)
            except Exception as e:
                total_errors += 1
                continue

            file_id = f"k-{table[:3]}-{hashlib.md5((url + str(row.get('id',''))).encode()).hexdigest()[:16]}"

            batch.append({
                "file_id": file_id,
                "file_type": ftype,
                "subdir": f"k-{category}",
                **features,
                "metadata": {
                    "url": url[:500],
                    "title": title[:500],
                    "original_size": len(content),
                    "source_table": f"knowledge.{table}",
                },
            })

            if len(batch) >= batch_size:
                n = api_store_batch(batch)
                total_stored += n
                batch = []
                if total_stored % 500 == 0 and total_stored > 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] {table}: "
                          f"stored={total_stored} offset={offset} "
                          f"skipped={total_skipped} errors={total_errors}")

        offset += len(rows)
        time.sleep(0.1)

    return total_stored


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge tables into numerical_sequences")
    parser.add_argument("--table", choices=["documents", "scraped_content", "scraped_data", "all"],
                        default="all")
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()

    print(f"Knowledge ingestion starting — api={API_BASE} worker={WORKER_ID}")

    tables = ["documents", "scraped_content", "scraped_data"] if args.table == "all" else [args.table]
    grand_total = 0

    for table in tables:
        n = ingest_table(table, args.batch_size)
        grand_total += n
        print(f"  {table}: {n} sequences stored")

    print(f"\nTotal ingested: {grand_total} sequences")


if __name__ == "__main__":
    main()
