#!/usr/bin/env python3
"""Unified pipeline worker — dispatched by orchestrator across fleet.

Combines transformer + storer stages into a single script that the
orchestrator's /scraping/pipeline/launch endpoint can deploy.

All data access goes through REST API (aio-01:5000) — workers never
touch Redis or PostgreSQL directly.

Usage:
    python3 pipeline-worker.py store          # run storer only
    python3 pipeline-worker.py transform      # run transformer only
    python3 pipeline-worker.py all            # run both (default)
"""

import argparse
import json
import math
import os
import re
import sys
import time

import requests

API_BASE = os.environ.get("GA_API_BASE", "http://aio-01:5000")
MAX_SEQUENCE_LENGTH = 5000
MAX_FILE_SIZE = 1_000_000
WORKER_ID = f"pipeline-{os.uname().nodename}-{os.getpid()}"

SOURCE_QUEUE = "store"
TRANSFORMED_QUEUE = "transformed_sequences"
CODE_CATEGORIES = {"github", "gitlab", "sourcecode", "code", "stackoverflow", "npm", "pypi", "crates"}
PAPER_CATEGORIES = {"arxiv", "papers", "research", "semanticscholar", "ieee", "acm"}



# ── Feature extraction ──────────────────────────────────────────────

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


# ── REST API helpers ─────────────────────────────────────────────────

def api_fetch(queue_name, count=10):
    try:
        resp = requests.post(
            f"{API_BASE}/queue/fetch/{queue_name}",
            json={"limit": count, "worker_id": WORKER_ID},
            timeout=120,
        )
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        return resp.json().get("items", [])
    except requests.RequestException as e:
        print(f"  [{WORKER_ID}] fetch error ({queue_name}): {e}", file=sys.stderr)
        return []


def api_complete(item_id):
    try:
        requests.post(
            f"{API_BASE}/queue/complete",
            json={"item_id": item_id, "worker_id": WORKER_ID},
            timeout=10,
        )
    except requests.RequestException:
        pass


def api_fail(item_id, reason=""):
    try:
        requests.post(
            f"{API_BASE}/queue/fail",
            json={"item_id": item_id, "worker_id": WORKER_ID, "reason": reason},
            timeout=10,
        )
    except requests.RequestException:
        pass


def api_enqueue(sequences):
    items = [
        {
            "queue": TRANSFORMED_QUEUE,
            "data": seq,
            "priority": 5,
            "idempotency_key": "xf-" + seq.get("file_id", ""),
        }
        for seq in sequences
    ]
    for attempt in range(4):
        try:
            resp = requests.post(
                f"{API_BASE}/queue/enqueue",
                json={"items": items},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("total_enqueued", 0)
        except requests.RequestException as e:
            time.sleep(2 ** attempt)
    return 0


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
            time.sleep(2 ** attempt)
    return 0


# ── Transform stage ──────────────────────────────────────────────────

def _detect_type(category):
    cat = (category or "").lower()
    if cat in CODE_CATEGORIES:
        return "sourcecode"
    if cat in PAPER_CATEGORIES:
        return "papers"
    return "docs"


def run_transform(batch_size=10):
    processed = 0
    errors = 0
    buffer = []

    print(f"[{WORKER_ID}] Transform stage — queue={SOURCE_QUEUE}")

    while True:
        items = api_fetch(SOURCE_QUEUE, count=batch_size)

        if not items:
            if buffer:
                processed += api_enqueue(buffer)
                buffer = []
            print(f"  [{time.strftime('%H:%M:%S')}] queue empty, waiting "
                  f"(processed={processed} errors={errors})")
            time.sleep(5)
            continue

        for item in items:
            item_id = item.get("id", item.get("item_id", ""))
            data = item.get("data", {})
            content = data.get("content", data.get("text", ""))
            if not content or len(content.strip()) < 50:
                errors += 1
                api_fail(item_id, "content too short or missing")
                continue

            category = data.get("category", "docs")
            ftype = _detect_type(category)
            lines = content.split("\n")
            extractor = EXTRACTORS.get(ftype, extract_docs)
            features = extractor(content, lines)

            url = data.get("url", "")
            title = data.get("title", "")
            file_id = f"{category}-{hash(url) & 0xFFFFFFFF:08x}"

            buffer.append({
                "file_id": file_id,
                "file_type": ftype,
                "subdir": category,
                **features,
                "metadata": {"url": url, "title": title, "original_size": len(content)},
            })
            api_complete(item_id)

            if len(buffer) >= batch_size:
                processed += api_enqueue(buffer)
                buffer = []
                if processed % 500 == 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] transformed: {processed} errors: {errors}")


# ── Store stage ──────────────────────────────────────────────────────

def run_store(batch_size=20):
    stored = 0
    errors = 0

    print(f"[{WORKER_ID}] Store stage — queue={TRANSFORMED_QUEUE}")

    while True:
        items = api_fetch(TRANSFORMED_QUEUE, count=batch_size)

        if not items:
            print(f"  [{time.strftime('%H:%M:%S')}] queue empty, waiting "
                  f"(stored={stored} errors={errors})")
            time.sleep(5)
            continue

        sequences = []
        for item in items:
            item_id = item.get("id", item.get("item_id", ""))
            data = item.get("data", {})
            if data and data.get("line_lengths"):
                sequences.append(data)
                api_complete(item_id)
            else:
                errors += 1
                api_fail(item_id, "missing line_lengths")

        if sequences:
            n = api_store_batch(sequences)
            stored += n
            if stored % 500 == 0:
                print(f"  [{time.strftime('%H:%M:%S')}] stored: {stored} errors: {errors}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pipeline worker (dispatched by orchestrator)")
    parser.add_argument("stage", nargs="?", default="all",
                        choices=["transform", "store", "all"],
                        help="Which stage to run (default: all)")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    print(f"Pipeline worker starting — stage={args.stage} api={API_BASE} worker={WORKER_ID}")

    if args.stage == "transform":
        run_transform(args.batch_size)
    elif args.stage == "store":
        run_store(args.batch_size)
    elif args.stage == "all":
        import threading
        t = threading.Thread(target=run_store, args=(20,), daemon=True)
        t.start()
        run_transform(args.batch_size)


if __name__ == "__main__":
    main()
