#!/usr/bin/env python3
"""Stage 2: Transformer — fetches queued files via REST API, extracts numerical
features, stores results back via REST API.

Workers never touch Redis or PostgreSQL directly — everything goes through
the REST API on aio-01:5000.

Usage:
    python3 pipeline_transformer.py [--api-base http://aio-01:5000] [--batch-size 50]
"""

import argparse
import json
import math
import os
import re
import sys
import time

import requests

API_BASE = "http://aio-01:5000"
MAX_SEQUENCE_LENGTH = 5000
MAX_FILE_SIZE = 1_000_000

QUEUES = ["raw_sourcecode", "raw_papers", "raw_docs"]


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
        "indentation_depths": para_lengths,
        "char_frequencies": char_freq,
        "nesting_patterns": word_lengths,
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


def fetch_items(api_base, queue_name, count=10):
    """Fetch items from queue via REST API."""
    try:
        resp = requests.post(
            f"{api_base}/queue/fetch/{queue_name}",
            json={"limit": count, "worker_id": WORKER_ID},
            timeout=120,
        )
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        result = resp.json()
        items = result.get("items", [])
        if items:
            print(f"  Fetched {len(items)} from {queue_name}")
        return items
    except requests.RequestException as e:
        print(f"  Queue fetch error ({queue_name}): {e}", file=sys.stderr)
        return []


WORKER_ID = f"transformer-{os.getpid()}"


def complete_item(api_base, item_id):
    """Mark queue item as completed via REST API."""
    try:
        requests.post(
            f"{api_base}/queue/complete",
            json={"item_id": item_id, "worker_id": WORKER_ID},
            timeout=10,
        )
    except requests.RequestException:
        pass


def fail_item(api_base, item_id, reason=""):
    """Mark queue item as failed via REST API."""
    try:
        requests.post(
            f"{api_base}/queue/fail",
            json={"item_id": item_id, "worker_id": WORKER_ID, "reason": reason},
            timeout=10,
        )
    except requests.RequestException:
        pass


def enqueue_transformed(api_base, sequences):
    """Enqueue transformed sequences to Redis for later storage."""
    items = [
        {
            "queue": "transformed_sequences",
            "data": seq,
            "priority": 5,
            "idempotency_key": "xf-" + seq.get("file_id", ""),
        }
        for seq in sequences
    ]
    for attempt in range(4):
        try:
            resp = requests.post(
                f"{api_base}/queue/enqueue",
                json={"items": items},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("total_enqueued", 0)
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  Enqueue error (attempt {attempt+1}/4, retry in {wait}s): {e}", file=sys.stderr)
            time.sleep(wait)
    return 0


def process_item(item):
    """Read the file and extract numerical features."""
    data = item.get("data", {})
    fpath = data.get("path", "")
    ftype = data.get("type", "sourcecode")
    subdir = data.get("subdir", "")
    file_id = data.get("file_id", "")

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
        "metadata": {"path": fpath, "original_size": data.get("size", 0)},
    }, None


def run_transformer(api_base, batch_size=10):
    processed = 0
    errors = 0
    enqueue_buffer = []
    queue_idx = 0

    while True:
        queue_name = QUEUES[queue_idx % len(QUEUES)]
        queue_idx += 1

        items = fetch_items(api_base, queue_name, count=batch_size)

        if not items:
            if enqueue_buffer:
                enqueued = enqueue_transformed(api_base, enqueue_buffer)
                processed += enqueued
                enqueue_buffer = []

            if queue_idx % len(QUEUES) == 0:
                print(f"  [{time.strftime('%H:%M:%S')}] All queues empty, waiting... "
                      f"(processed={processed}, errors={errors})")
                time.sleep(5)
            continue

        for item in items:
            item_id = item.get("id", item.get("item_id", ""))
            row, err = process_item(item)

            if err:
                errors += 1
                fail_item(api_base, item_id, err)
                if errors % 100 == 0:
                    print(f"  Errors so far: {errors} (latest: {err})")
                continue

            enqueue_buffer.append(row)
            complete_item(api_base, item_id)

            if len(enqueue_buffer) >= batch_size:
                enqueued = enqueue_transformed(api_base, enqueue_buffer)
                processed += enqueued
                enqueue_buffer = []

                if processed % 500 == 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] Processed: {processed}, Errors: {errors}")


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Transform raw files to numerical sequences via REST API")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--batch-size", type=int, default=10, help="Items to fetch per queue poll")
    args = parser.parse_args()

    print(f"Transformer starting — api={args.api_base} queues={QUEUES}")
    print(f"  Batch fetch size: {args.batch_size}, enqueuing transforms to Redis")
    run_transformer(args.api_base, args.batch_size)


if __name__ == "__main__":
    main()
