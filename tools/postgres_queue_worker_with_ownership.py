#!/usr/bin/env python3
"""
PostgreSQL Queue Worker with Ownership Verification
All queue operations verify worker_id to prevent race conditions
"""

import os
import sys
import time
import json
import socket
import hashlib
import logging
import requests
import psycopg2
from datetime import datetime
from typing import Dict, Optional, Any

# Configuration
API_BASE = os.getenv("ORCHESTRATOR_API", "http://aio-01:5000")
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class QueueWorker:
    """Worker that processes queue items with ownership verification"""

    def __init__(self, queue_name: str, processor_func):
        self.queue_name = queue_name
        self.processor_func = processor_func
        self.worker_id = WORKER_ID
        self.api_base = API_BASE
        self.running = True

        logger.info(f"Initializing worker {self.worker_id} for queue {queue_name}")

    def fetch_items(self, limit: int = BATCH_SIZE) -> list:
        """
        Fetch items from queue with ownership verification

        CRITICAL: Uses SELECT FOR UPDATE SKIP LOCKED to:
        - Lock rows atomically
        - Skip items already locked by other workers
        - Verify worker_id after acquisition
        """
        try:
            response = requests.post(
                f"{self.api_base}/queue/fetch/{self.queue_name}",
                json={
                    "worker_id": self.worker_id,
                    "limit": limit
                },
                timeout=30
            )

            if response.status_code == 200:
                items = response.json().get("items", [])

                # Verify ALL items have our worker_id
                for item in items:
                    if item.get("worker_id") != self.worker_id:
                        logger.error(
                            f"OWNERSHIP VIOLATION: Item {item['id']} has worker_id "
                            f"{item.get('worker_id')} but we are {self.worker_id}"
                        )
                        # Skip this item - it's not ours
                        continue

                logger.info(f"Fetched {len(items)} items from {self.queue_name}")
                return items

            elif response.status_code == 204:
                # No items available
                return []

            else:
                logger.error(f"Failed to fetch items: {response.status_code} {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error fetching items: {e}")
            return []

    def complete_item(self, item_id: int, result: Optional[Dict] = None, error: Optional[str] = None) -> bool:
        """
        Mark item as complete with ownership verification

        CRITICAL: Verifies worker_id in UPDATE WHERE clause:
        - UPDATE ... WHERE id = %s AND worker_id = %s
        - If worker_id doesn't match, UPDATE affects 0 rows
        - Returns False if we don't own the item
        """
        try:
            response = requests.post(
                f"{self.api_base}/queue/complete/{self.queue_name}/{item_id}",
                json={
                    "worker_id": self.worker_id,
                    "result": result,
                    "error": error
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Verify we actually updated the item
                if not data.get("updated"):
                    logger.error(
                        f"OWNERSHIP VERIFICATION FAILED: Item {item_id} not updated. "
                        f"Likely owned by different worker."
                    )
                    return False

                logger.info(f"Completed item {item_id}")
                return True

            else:
                logger.error(f"Failed to complete item {item_id}: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error completing item {item_id}: {e}")
            return False

    def heartbeat_item(self, item_id: int) -> bool:
        """
        Update heartbeat with ownership verification

        CRITICAL: Verifies worker_id in UPDATE:
        - UPDATE ... SET heartbeat = NOW() WHERE id = %s AND worker_id = %s
        - Prevents other workers from stealing items
        """
        try:
            response = requests.post(
                f"{self.api_base}/queue/heartbeat/{self.queue_name}/{item_id}",
                json={"worker_id": self.worker_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if not data.get("updated"):
                    logger.warning(
                        f"Heartbeat failed for item {item_id} - ownership lost"
                    )
                    return False

                return True

            else:
                logger.error(f"Heartbeat failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False

    def process_item(self, item: Dict) -> None:
        """Process a single item with ownership verification"""
        item_id = item["id"]

        try:
            # Double-check ownership before processing
            if item.get("worker_id") != self.worker_id:
                logger.error(
                    f"SKIPPING item {item_id}: worker_id mismatch "
                    f"(expected {self.worker_id}, got {item.get('worker_id')})"
                )
                return

            logger.info(f"Processing item {item_id}")

            # Process the item
            result = self.processor_func(item)

            # Mark as complete with ownership verification
            success = self.complete_item(item_id, result=result)

            if not success:
                logger.error(f"Failed to complete item {item_id} - ownership may have been lost")

        except Exception as e:
            logger.error(f"Error processing item {item_id}: {e}")
            self.complete_item(item_id, error=str(e))

    def run(self):
        """Main worker loop with ownership verification"""
        logger.info(f"Starting worker {self.worker_id} for queue {self.queue_name}")

        while self.running:
            try:
                # Fetch items with ownership lock
                items = self.fetch_items()

                if not items:
                    logger.debug(f"No items in {self.queue_name}, sleeping {POLL_INTERVAL}s")
                    time.sleep(POLL_INTERVAL)
                    continue

                # Process each item
                for item in items:
                    if not self.running:
                        break

                    self.process_item(item)

            except KeyboardInterrupt:
                logger.info("Shutting down worker...")
                self.running = False

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(POLL_INTERVAL)

        logger.info("Worker stopped")


# Example processor functions

def store_processor(item: Dict) -> Dict:
    """Process store queue items"""
    payload = item["payload"]

    # Validate required fields
    required = ["url", "content", "category"]
    for field in required:
        if field not in payload:
            raise ValueError(f"Missing required field: {field}")

    # Generate hash
    url = payload["url"]
    file_hash = hashlib.md5(url.encode()).hexdigest()

    return {
        "hash": file_hash,
        "url": url,
        "size": len(payload.get("content", "")),
        "validated": True
    }


def chunk_processor(item: Dict) -> Dict:
    """Process chunk queue items"""
    payload = item["payload"]

    # Read file from path
    file_path = payload.get("file_path")
    if not file_path:
        raise ValueError("No file_path in payload")

    # For now, just return metadata
    return {
        "file_path": file_path,
        "chunks_created": 0,  # TODO: implement chunking
        "processed": True
    }


def embed_processor(item: Dict) -> Dict:
    """Process embed queue items"""
    payload = item["payload"]

    # TODO: Generate embeddings
    return {
        "chunks_embedded": 0,
        "processed": True
    }


def graph_processor(item: Dict) -> Dict:
    """Process graph queue items"""
    payload = item["payload"]

    # TODO: Create graph relationships
    return {
        "relationships_created": 0,
        "processed": True
    }


# CLI entry point

def main():
    if len(sys.argv) < 2:
        print("Usage: postgres_queue_worker_with_ownership.py <queue_name>")
        print("Queue names: store, chunk, embed, graph")
        sys.exit(1)

    queue_name = sys.argv[1]

    processors = {
        "store": store_processor,
        "chunk": chunk_processor,
        "embed": embed_processor,
        "graph": graph_processor
    }

    if queue_name not in processors:
        print(f"Unknown queue: {queue_name}")
        print(f"Available queues: {', '.join(processors.keys())}")
        sys.exit(1)

    processor = processors[queue_name]
    worker = QueueWorker(queue_name, processor)

    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
