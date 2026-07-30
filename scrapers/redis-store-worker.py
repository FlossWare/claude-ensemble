#!/usr/bin/env python3
"""Redis queue store worker — fetches from Redis store queue, stores to knowledge DB via REST API."""

import json
import time
import urllib.request
import urllib.error
import sys
import os

API_BASE = "http://aio-01:5000"
BATCH_SIZE = 5
SLEEP_EMPTY = 2
SLEEP_ERROR = 5


def fetch_items(count=BATCH_SIZE):
    req = urllib.request.Request(
        f"{API_BASE}/queue/fetch/store",
        data=json.dumps({"count": count}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("items", [])


def store_document(data):
    source = data.get("category", data.get("source", "unknown"))
    payload = {
        "content": data.get("content", ""),
        "title": data.get("title", "Untitled"),
        "url": data.get("url", ""),
        "source": source,
        "category": source,
    }
    req = urllib.request.Request(
        f"{API_BASE}/store",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def complete_item(item_id):
    req = urllib.request.Request(
        f"{API_BASE}/queue/complete",
        data=json.dumps({"item_id": item_id}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def fail_item(item_id, error_msg):
    req = urllib.request.Request(
        f"{API_BASE}/queue/fail",
        data=json.dumps({"item_id": item_id, "error": error_msg[:500]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main():
    worker_id = sys.argv[1] if len(sys.argv) > 1 else f"store-worker-{os.getpid()}"
    print(f"[{worker_id}] Starting Redis store queue worker", flush=True)

    processed = 0
    errors = 0

    while True:
        try:
            items = fetch_items()
            if not items:
                time.sleep(SLEEP_EMPTY)
                continue

            for item in items:
                item_id = item.get("id", "")
                data = item.get("data", {})
                try:
                    store_document(data)
                    complete_item(item_id)
                    processed += 1
                    if processed % 50 == 0:
                        print(f"[{worker_id}] Processed {processed} (errors: {errors})", flush=True)
                except Exception as e:
                    errors += 1
                    try:
                        fail_item(item_id, str(e))
                    except Exception:
                        pass
                    print(f"[{worker_id}] Error storing {item_id}: {e}", flush=True)

        except KeyboardInterrupt:
            print(f"[{worker_id}] Shutting down. Processed: {processed}, Errors: {errors}", flush=True)
            break
        except Exception as e:
            print(f"[{worker_id}] Fetch error: {e}", flush=True)
            time.sleep(SLEEP_ERROR)


if __name__ == "__main__":
    main()
