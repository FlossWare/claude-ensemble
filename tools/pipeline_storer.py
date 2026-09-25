#!/usr/bin/env python3
"""Stage 2b: Storer — dequeues transformed sequences from Redis, stores in PostgreSQL.

Runs as a separate process from the transformer so transforms aren't blocked
by PostgreSQL write latency.

Workers never touch Redis or PostgreSQL directly — everything goes through
the REST API on aio-01:5000.

Usage:
    python3 pipeline_storer.py [--api-base http://aio-01:5000] [--batch-size 20]
"""

import argparse
import os
import sys
import time

import requests

API_BASE = "http://aio-01:5000"
QUEUE_NAME = "transformed_sequences"
WORKER_ID = f"storer-{os.getpid()}"


def fetch_items(api_base, count=20):
    try:
        resp = requests.post(
            f"{api_base}/queue/fetch/{QUEUE_NAME}",
            json={"limit": count, "worker_id": WORKER_ID},
            timeout=120,
        )
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        result = resp.json()
        return result.get("items", [])
    except requests.RequestException as e:
        print(f"  Fetch error: {e}", file=sys.stderr)
        return []


def complete_item(api_base, item_id):
    try:
        requests.post(
            f"{api_base}/queue/complete",
            json={"item_id": item_id, "worker_id": WORKER_ID},
            timeout=10,
        )
    except requests.RequestException:
        pass


def fail_item(api_base, item_id, reason=""):
    try:
        requests.post(
            f"{api_base}/queue/fail",
            json={"item_id": item_id, "worker_id": WORKER_ID, "reason": reason},
            timeout=10,
        )
    except requests.RequestException:
        pass


def store_batch(api_base, sequences):
    for attempt in range(4):
        try:
            resp = requests.post(
                f"{api_base}/sequences/batch",
                json={"sequences": sequences},
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("stored", 0)
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  Store error (attempt {attempt+1}/4, retry in {wait}s): {e}", file=sys.stderr)
            time.sleep(wait)
    return 0


def run_storer(api_base, batch_size=20):
    stored = 0
    errors = 0

    while True:
        items = fetch_items(api_base, count=batch_size)

        if not items:
            print(f"  [{time.strftime('%H:%M:%S')}] Queue empty, waiting... "
                  f"(stored={stored}, errors={errors})")
            time.sleep(3)
            continue

        sequences = []
        item_ids = []

        for item in items:
            item_id = item.get("id", item.get("item_id", ""))
            data = item.get("data", {})

            if not data.get("file_id"):
                errors += 1
                fail_item(api_base, item_id, "missing file_id")
                continue

            sequences.append(data)
            item_ids.append(item_id)

        if sequences:
            count = store_batch(api_base, sequences)
            stored += count

            for iid in item_ids:
                complete_item(api_base, iid)

            if stored % 500 == 0 or stored < 50:
                print(f"  [{time.strftime('%H:%M:%S')}] Stored: {stored}, Errors: {errors}")


def main():
    parser = argparse.ArgumentParser(description="Stage 2b: Store transformed sequences in PostgreSQL via REST API")
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--batch-size", type=int, default=20, help="Items to fetch per poll")
    args = parser.parse_args()

    print(f"Storer starting — api={args.api_base} queue={QUEUE_NAME}")
    print(f"  Batch size: {args.batch_size}")
    run_storer(args.api_base, args.batch_size)


if __name__ == "__main__":
    main()
