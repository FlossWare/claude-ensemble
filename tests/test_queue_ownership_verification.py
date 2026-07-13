#!/usr/bin/env python3
"""
Test Queue Ownership Verification

Verifies that:
1. Workers can only fetch items that get assigned to them
2. Workers can only complete items they own
3. Workers can only heartbeat items they own
4. Race conditions are prevented by SELECT FOR UPDATE SKIP LOCKED
"""

import requests
import time
import threading
import json
from typing import List, Dict

API_BASE = "http://aio-01:5000"


def test_basic_ownership():
    """Test basic ownership flow"""
    print("\n=== Test 1: Basic Ownership Flow ===")

    # Add item to queue
    response = requests.post(
        f"{API_BASE}/queue/add",
        json={
            "queue": "store",
            "payload": {"url": "https://test.com", "content": "test"},
            "priority": 5
        }
    )
    assert response.status_code == 202
    item_id = response.json()["item_id"]
    print(f"✓ Added item {item_id} to queue")

    # Fetch as worker-1
    response = requests.post(
        f"{API_BASE}/queue/fetch/store",
        json={"worker_id": "worker-1", "limit": 1}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["worker_id"] == "worker-1"
    assert items[0]["id"] == item_id
    print(f"✓ Worker-1 fetched item {item_id}")

    # Try to complete as worker-2 (should fail)
    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item_id}",
        json={"worker_id": "worker-2", "result": {"done": True}}
    )
    assert response.status_code == 200
    assert response.json()["updated"] == False
    print(f"✓ Worker-2 CANNOT complete item {item_id} (ownership verification)")

    # Complete as worker-1 (should succeed)
    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item_id}",
        json={"worker_id": "worker-1", "result": {"done": True}}
    )
    assert response.status_code == 200
    assert response.json()["updated"] == True
    print(f"✓ Worker-1 CAN complete item {item_id}")

    print("✅ Test 1 PASSED\n")


def test_heartbeat_ownership():
    """Test heartbeat ownership verification"""
    print("\n=== Test 2: Heartbeat Ownership ===")

    # Add item
    response = requests.post(
        f"{API_BASE}/queue/add",
        json={
            "queue": "store",
            "payload": {"url": "https://test2.com", "content": "test"},
        }
    )
    item_id = response.json()["item_id"]
    print(f"✓ Added item {item_id}")

    # Fetch as worker-1
    response = requests.post(
        f"{API_BASE}/queue/fetch/store",
        json={"worker_id": "worker-1", "limit": 1}
    )
    assert response.status_code == 200
    print(f"✓ Worker-1 fetched item {item_id}")

    # Heartbeat as worker-1 (should succeed)
    response = requests.post(
        f"{API_BASE}/queue/heartbeat/store/{item_id}",
        json={"worker_id": "worker-1"}
    )
    assert response.status_code == 200
    assert response.json()["updated"] == True
    print(f"✓ Worker-1 CAN heartbeat item {item_id}")

    # Heartbeat as worker-2 (should fail)
    response = requests.post(
        f"{API_BASE}/queue/heartbeat/store/{item_id}",
        json={"worker_id": "worker-2"}
    )
    assert response.status_code == 200
    assert response.json()["updated"] == False
    print(f"✓ Worker-2 CANNOT heartbeat item {item_id} (ownership verification)")

    # Clean up
    requests.post(
        f"{API_BASE}/queue/complete/store/{item_id}",
        json={"worker_id": "worker-1", "result": {"done": True}}
    )

    print("✅ Test 2 PASSED\n")


def test_race_condition_prevention():
    """Test that SELECT FOR UPDATE SKIP LOCKED prevents race conditions"""
    print("\n=== Test 3: Race Condition Prevention ===")

    # Add 10 items
    item_ids = []
    for i in range(10):
        response = requests.post(
            f"{API_BASE}/queue/add",
            json={
                "queue": "store",
                "payload": {"url": f"https://test{i}.com", "content": "test"},
            }
        )
        item_ids.append(response.json()["item_id"])

    print(f"✓ Added {len(item_ids)} items")

    # Simulate 3 workers fetching simultaneously
    results = []

    def worker_fetch(worker_id: str):
        response = requests.post(
            f"{API_BASE}/queue/fetch/store",
            json={"worker_id": worker_id, "limit": 5}
        )
        if response.status_code == 200:
            items = response.json()["items"]
            results.append({
                "worker_id": worker_id,
                "items": [item["id"] for item in items]
            })

    # Start 3 workers simultaneously
    threads = []
    for i in range(3):
        worker_id = f"worker-{i+1}"
        thread = threading.Thread(target=worker_fetch, args=(worker_id,))
        threads.append(thread)
        thread.start()

    # Wait for all workers
    for thread in threads:
        thread.join()

    # Verify NO overlapping items
    all_fetched_items = []
    for result in results:
        print(f"  {result['worker_id']}: {len(result['items'])} items")
        for item_id in result["items"]:
            assert item_id not in all_fetched_items, f"Item {item_id} fetched by multiple workers!"
            all_fetched_items.append(item_id)

    print(f"✓ {len(all_fetched_items)} items fetched total")
    print(f"✓ NO overlapping items (race condition prevented)")

    # Clean up
    for result in results:
        for item_id in result["items"]:
            requests.post(
                f"{API_BASE}/queue/complete/store/{item_id}",
                json={"worker_id": result["worker_id"], "result": {"done": True}}
            )

    print("✅ Test 3 PASSED\n")


def test_worker_isolation():
    """Test that workers are completely isolated"""
    print("\n=== Test 4: Worker Isolation ===")

    # Add 2 items
    response1 = requests.post(
        f"{API_BASE}/queue/add",
        json={"queue": "store", "payload": {"url": "https://test1.com", "content": "test"}}
    )
    item1_id = response1.json()["item_id"]

    response2 = requests.post(
        f"{API_BASE}/queue/add",
        json={"queue": "store", "payload": {"url": "https://test2.com", "content": "test"}}
    )
    item2_id = response2.json()["item_id"]

    print(f"✓ Added items {item1_id} and {item2_id}")

    # Worker-1 fetches item1
    response = requests.post(
        f"{API_BASE}/queue/fetch/store",
        json={"worker_id": "worker-1", "limit": 1}
    )
    assert response.json()["items"][0]["id"] == item1_id
    print(f"✓ Worker-1 fetched item {item1_id}")

    # Worker-2 fetches item2
    response = requests.post(
        f"{API_BASE}/queue/fetch/store",
        json={"worker_id": "worker-2", "limit": 1}
    )
    assert response.json()["items"][0]["id"] == item2_id
    print(f"✓ Worker-2 fetched item {item2_id}")

    # Worker-1 tries to complete worker-2's item (should fail)
    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item2_id}",
        json={"worker_id": "worker-1", "result": {"done": True}}
    )
    assert response.json()["updated"] == False
    print(f"✓ Worker-1 CANNOT complete worker-2's item {item2_id}")

    # Worker-2 tries to complete worker-1's item (should fail)
    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item1_id}",
        json={"worker_id": "worker-2", "result": {"done": True}}
    )
    assert response.json()["updated"] == False
    print(f"✓ Worker-2 CANNOT complete worker-1's item {item1_id}")

    # Each worker completes their own item
    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item1_id}",
        json={"worker_id": "worker-1", "result": {"done": True}}
    )
    assert response.json()["updated"] == True

    response = requests.post(
        f"{API_BASE}/queue/complete/store/{item2_id}",
        json={"worker_id": "worker-2", "result": {"done": True}}
    )
    assert response.json()["updated"] == True

    print(f"✓ Each worker CAN complete their own items")

    print("✅ Test 4 PASSED\n")


def test_stats():
    """Test queue stats"""
    print("\n=== Test 5: Queue Stats ===")

    # Get stats
    response = requests.get(f"{API_BASE}/queue/stats/store")
    assert response.status_code == 200

    stats = response.json()
    print(f"Queue: {stats['queue']}")
    print(f"  Pending: {stats['pending']}")
    print(f"  Processing: {stats['processing']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Workers: {stats['workers']}")

    print("✅ Test 5 PASSED\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Queue Ownership Verification Tests")
    print("=" * 60)

    try:
        test_basic_ownership()
        test_heartbeat_ownership()
        test_race_condition_prevention()
        test_worker_isolation()
        test_stats()

        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
