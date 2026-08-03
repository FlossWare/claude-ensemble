#!/usr/bin/env python3
"""Stage 2: Transformer — pulls raw files from Redis, extracts numerical sequences,
stores results to PostgreSQL learning.numerical_sequences.

Extracts per file type:
  - Source code: line lengths, indentation depths, char frequencies (256), nesting patterns,
                 entropy, complexity score
  - Papers:      paragraph lengths, word lengths, sentence count pattern, char frequencies
  - Docs:        heading depths, list item depths, line lengths, char frequencies

Usage:
    python3 pipeline_transformer.py [--redis-host aio-01] [--pg-host aio-01] [--batch-commit 100]
"""

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter

import psycopg2
import psycopg2.extras
import redis

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS learning.numerical_sequences (
    id SERIAL PRIMARY KEY,
    file_id TEXT NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    subdir VARCHAR(100),
    sequence_length INT NOT NULL,
    line_lengths INT[],
    indentation_depths INT[],
    char_frequencies FLOAT[],
    nesting_patterns INT[],
    complexity_score FLOAT,
    entropy FLOAT,
    avg_line_length FLOAT,
    max_indentation INT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_numseq_file_type
    ON learning.numerical_sequences(file_type);
CREATE INDEX IF NOT EXISTS idx_numseq_complexity
    ON learning.numerical_sequences(complexity_score);
CREATE INDEX IF NOT EXISTS idx_numseq_file_id
    ON learning.numerical_sequences(file_id);
"""

INSERT_SQL = """
INSERT INTO learning.numerical_sequences
    (file_id, file_type, subdir, sequence_length, line_lengths, indentation_depths,
     char_frequencies, nesting_patterns, complexity_score, entropy,
     avg_line_length, max_indentation, metadata)
VALUES
    (%(file_id)s, %(file_type)s, %(subdir)s, %(sequence_length)s, %(line_lengths)s,
     %(indentation_depths)s, %(char_frequencies)s, %(nesting_patterns)s,
     %(complexity_score)s, %(entropy)s, %(avg_line_length)s, %(max_indentation)s,
     %(metadata)s)
ON CONFLICT (file_id) DO NOTHING
"""

# After table creation, add unique constraint for dedup
ADD_UNIQUE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_numseq_file_id'
    ) THEN
        ALTER TABLE learning.numerical_sequences
            ADD CONSTRAINT uq_numseq_file_id UNIQUE (file_id);
    END IF;
END $$;
"""

MAX_SEQUENCE_LENGTH = 5000  # truncate very long files to first N lines


def get_redis(password, host="aio-01", port=6379):
    return redis.Redis(host=host, port=port, password=password, decode_responses=True)


def get_pg(host="aio-01", port=5433, dbname="learning", user="sfloess"):
    return psycopg2.connect(host=host, port=port, dbname=dbname, user=user)


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
    keywords = re.compile(r'\b(if|else|elif|for|while|switch|case|catch|try|except|finally|do)\b')
    count = sum(len(keywords.findall(line)) for line in lines)
    return count / max(1, len(lines))


def extract_sourcecode(content, lines):
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


def extract_papers(content, lines):
    paragraphs = re.split(r'\n\s*\n', content)
    para_lengths = [len(p.split()) for p in paragraphs[:MAX_SEQUENCE_LENGTH]]
    word_lengths = [len(w) for w in content.split()[:MAX_SEQUENCE_LENGTH]]
    char_freq = compute_char_frequencies(content)
    entropy = compute_entropy(char_freq)
    line_lengths = [len(l) for l in lines[:MAX_SEQUENCE_LENGTH]]
    avg_ll = sum(line_lengths) / max(1, len(line_lengths))

    return {
        "sequence_length": len(lines),
        "line_lengths": line_lengths,
        "indentation_depths": para_lengths,  # reuse as paragraph lengths
        "char_frequencies": char_freq,
        "nesting_patterns": word_lengths,    # reuse as word length pattern
        "complexity_score": len(paragraphs) / max(1, len(lines)),
        "entropy": entropy,
        "avg_line_length": avg_ll,
        "max_indentation": max(para_lengths) if para_lengths else 0,
    }


def extract_docs(content, lines):
    line_lengths = [len(l) for l in lines[:MAX_SEQUENCE_LENGTH]]
    indentation = [len(l) - len(l.lstrip()) for l in lines[:MAX_SEQUENCE_LENGTH]]

    heading_pattern = []
    for l in lines[:MAX_SEQUENCE_LENGTH]:
        stripped = l.lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_pattern.append(min(level, 6))
        else:
            heading_pattern.append(0)

    char_freq = compute_char_frequencies(content)
    entropy = compute_entropy(char_freq)
    avg_ll = sum(line_lengths) / max(1, len(line_lengths))
    max_indent = max(indentation) if indentation else 0

    return {
        "sequence_length": len(lines),
        "line_lengths": line_lengths,
        "indentation_depths": indentation,
        "char_frequencies": char_freq,
        "nesting_patterns": heading_pattern,
        "complexity_score": sum(1 for h in heading_pattern if h > 0) / max(1, len(lines)),
        "entropy": entropy,
        "avg_line_length": avg_ll,
        "max_indentation": max_indent,
    }


EXTRACTORS = {
    "sourcecode": extract_sourcecode,
    "papers": extract_papers,
    "docs": extract_docs,
}

QUEUES = ["raw:sourcecode", "raw:papers", "raw:docs"]


def process_item(item_json):
    item = json.loads(item_json)
    fpath = item["path"]
    ftype = item["type"]
    subdir = item.get("subdir", "")
    file_id = item["file_id"]

    try:
        with open(fpath, "r", errors="replace") as f:
            content = f.read(MAX_FILE_SIZE)
    except (OSError, IOError) as e:
        return None, f"read error: {e}"

    lines = content.split("\n")
    extractor = EXTRACTORS.get(ftype, extract_sourcecode)
    features = extractor(content, lines)

    return {
        "file_id": file_id,
        "file_type": ftype,
        "subdir": subdir,
        **features,
        "metadata": json.dumps({"path": fpath, "original_size": item.get("size", 0)}),
    }, None


MAX_FILE_SIZE = 1_000_000


def run_transformer(r, pg, batch_commit=100):
    cur = pg.cursor()
    processed = 0
    errors = 0
    batch = []

    while True:
        try:
            result = r.brpop(QUEUES, timeout=5)
        except redis.ConnectionError:
            print(f"  [{time.strftime('%H:%M:%S')}] Redis connection lost, reconnecting...", file=sys.stderr)
            time.sleep(2)
            try:
                r.ping()
            except Exception:
                pass
            continue

        if result is None:
            if batch:
                _flush_batch(cur, pg, batch)
                processed += len(batch)
                batch = []
            print(f"  [{time.strftime('%H:%M:%S')}] Queue empty, waiting... (processed={processed}, errors={errors})")
            continue

        queue_name, item_json = result
        row, err = process_item(item_json)
        if err:
            errors += 1
            if errors % 100 == 0:
                print(f"  Errors so far: {errors} (latest: {err})")
            continue

        batch.append(row)

        if len(batch) >= batch_commit:
            try:
                _flush_batch(cur, pg, batch)
                processed += len(batch)
            except psycopg2.OperationalError as e:
                print(f"  PG connection lost, reconnecting: {e}", file=sys.stderr)
                try:
                    pg = psycopg2.connect(host=pg.info.host, port=pg.info.port,
                                          dbname=pg.info.dbname, user=pg.info.user)
                    cur = pg.cursor()
                except Exception:
                    time.sleep(2)
                errors += len(batch)
            except Exception as e:
                pg.rollback()
                print(f"  DB error: {e}", file=sys.stderr)
                errors += len(batch)
            batch = []

            if processed % 1000 == 0:
                qlens = {q: r.llen(q) for q in QUEUES}
                print(f"  [{time.strftime('%H:%M:%S')}] Processed: {processed}, Errors: {errors}, Queues: {qlens}")


def _flush_batch(cur, pg, batch):
    psycopg2.extras.execute_batch(cur, INSERT_SQL, batch)
    pg.commit()


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Transform raw files to numerical sequences")
    parser.add_argument("--redis-host", default="aio-01")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-password", default=None)
    parser.add_argument("--pg-host", default="aio-01")
    parser.add_argument("--pg-port", type=int, default=5433)
    parser.add_argument("--pg-db", default="learning")
    parser.add_argument("--pg-user", default="sfloess")
    parser.add_argument("--batch-commit", type=int, default=100)
    args = parser.parse_args()

    redis_pw = args.redis_password or os.environ.get("REDIS_PASSWORD", "")
    if not redis_pw:
        print("ERROR: Redis password required", file=sys.stderr)
        sys.exit(1)

    r = get_redis(redis_pw, args.redis_host, args.redis_port)
    r.ping()
    print(f"Connected to Redis at {args.redis_host}:{args.redis_port}")

    pg = get_pg(args.pg_host, args.pg_port, args.pg_db, args.pg_user)
    print(f"Connected to PostgreSQL at {args.pg_host}:{args.pg_port}/{args.pg_db}")

    cur = pg.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute(ADD_UNIQUE_SQL)
    pg.commit()
    print("Table learning.numerical_sequences ready")

    qlens = {q: r.llen(q) for q in QUEUES}
    print(f"Queue lengths: {qlens}")

    run_transformer(r, pg, args.batch_commit)


if __name__ == "__main__":
    main()
