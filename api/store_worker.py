#!/usr/bin/env python3
"""
Store Queue Worker

Processes items from queue.store:
1. Validates raw scraped content
2. Writes to filesystem: /scraped-data/raw/{category}/{hash}.json
3. Deduplicates based on file hash
4. Queues for chunking (next stage)
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, Any
import psycopg2.extras

# Import base worker class
from queue_worker_base import QueueWorkerBase

# Storage configuration
SCRAPED_DATA_BASE = Path('/mnt/aio-01/claude-orchestrator/scraped-data/raw')

class StoreWorker(QueueWorkerBase):
    """Worker that processes queue.store tasks"""

    def __init__(self, worker_id: str):
        super().__init__(queue_name='store', worker_id=worker_id)

        # Ensure base directory exists
        SCRAPED_DATA_BASE.mkdir(parents=True, exist_ok=True)

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a store task

        Expected task.data format:
        {
            "url": "https://...",
            "source": "wikipedia",
            "category": "programming",
            "title": "Python",
            "content": "Python is a high-level...",
            "metadata": { ... }
        }
        """
        task_id = task['id']
        data = task['data']

        # Validate required fields
        required = ['url', 'source', 'content']
        missing = [f for f in required if f not in data]
        if missing:
            self.logger.error(f"Task {task_id}: Missing fields: {missing}")
            return False

        # Extract fields
        url = data['url']
        source = data['source']
        category = data.get('category', 'uncategorized')
        content = data['content']

        # Generate hash from URL (for deduplication)
        file_hash = hashlib.md5(url.encode()).hexdigest()

        # Build file path: {category}/{hash}.json
        category_dir = SCRAPED_DATA_BASE / category
        category_dir.mkdir(parents=True, exist_ok=True)

        file_path = category_dir / f"{file_hash}.json"

        # Check if already exists (idempotency at filesystem level)
        if file_path.exists():
            self.logger.info(f"Task {task_id}: File already exists: {file_path}")
            # Still successful - no need to reprocess
            return True

        # Prepare document
        document = {
            'url': url,
            'source': source,
            'category': category,
            'title': data.get('title', ''),
            'content': content,
            'metadata': data.get('metadata', {}),
            'file_hash': file_hash,
            'scraped_at': data.get('scraped_at'),
            'stored_at': str(task.get('created_at'))
        }

        try:
            # Write to filesystem (atomic write)
            tmp_path = file_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(document, f, indent=2)

            # Atomic rename
            tmp_path.rename(file_path)

            self.logger.info(
                f"Task {task_id}: Stored {file_path.name} "
                f"({len(content)} chars, category: {category})"
            )

            # Queue for chunking (next stage)
            self._queue_for_chunking(file_path, category, file_hash)

            return True

        except Exception as e:
            self.logger.error(f"Task {task_id}: Failed to write file: {e}")

            # Cleanup temp file if exists
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except:
                    pass

            return False

    def _queue_for_chunking(self, file_path: Path, category: str, file_hash: str):
        """Add to chunk queue for next stage processing"""
        try:
            with self.conn.cursor() as cursor:
                # Use file_hash as idempotency key
                cursor.execute("""
                    INSERT INTO queue.chunk (data, idempotency_key, file_path, priority)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                """, (
                    json.dumps({
                        'file_path': str(file_path),
                        'category': category,
                        'file_hash': file_hash
                    }),
                    f"chunk:{file_hash}",
                    str(file_path),
                    5
                ))
                self.conn.commit()

                if cursor.rowcount > 0:
                    self.logger.info(f"Queued for chunking: {file_path.name}")
                else:
                    self.logger.debug(f"Already queued for chunking: {file_path.name}")

        except Exception as e:
            self.logger.warning(f"Failed to queue for chunking: {e}")
            # Don't fail the whole task if queueing fails
            # The file is already stored


def main():
    """Entry point"""
    import socket

    # Worker ID includes hostname for uniqueness
    hostname = socket.gethostname()
    worker_id = f"store-worker-{hostname}-{os.getpid()}"

    worker = StoreWorker(worker_id)
    worker.run_forever(poll_interval=5)


if __name__ == '__main__':
    main()
