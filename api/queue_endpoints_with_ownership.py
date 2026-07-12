"""
Queue API Endpoints with Ownership Verification
All operations verify worker_id to prevent race conditions
"""

from flask import Blueprint, request, jsonify
import psycopg2
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

queue_bp = Blueprint('queue', __name__)


def get_db_connection():
    """Get PostgreSQL connection - implement based on your setup"""
    # TODO: Import from your db adapter
    import os
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "aio-01"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        database=os.getenv("POSTGRES_DB", "learning"),
        user=os.getenv("POSTGRES_USER", "sfloess"),
        password=os.getenv("POSTGRES_PASSWORD", "")
    )


@queue_bp.route("/queue/add", methods=["POST"])
def add_to_queue():
    """
    Add item to queue

    Body: {
        "queue": "store|chunk|embed|graph",
        "payload": { ... },
        "priority": 5 (optional, 1-10)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON body"}), 400

        queue_name = data.get("queue")
        payload = data.get("payload")
        priority = data.get("priority", 5)

        if not queue_name:
            return jsonify({"error": "Missing queue name"}), 400

        if queue_name not in ["store", "chunk", "embed", "graph"]:
            return jsonify({"error": f"Invalid queue: {queue_name}"}), 400

        if not payload:
            return jsonify({"error": "Missing payload"}), 400

        # Insert into queue
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO queue.{queue_name}
            (payload, priority, status, created_at)
            VALUES (%s, %s, 'pending', NOW())
            RETURNING id
        """, (
            psycopg2.extras.Json(payload),
            priority
        ))

        item_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Added item {item_id} to queue {queue_name}")

        return jsonify({
            "queued": True,
            "queue": queue_name,
            "item_id": item_id
        }), 202

    except Exception as e:
        logger.error(f"Error adding to queue: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/queue/fetch/<queue_name>", methods=["POST"])
def fetch_from_queue(queue_name):
    """
    Fetch items from queue with ownership verification

    CRITICAL: Uses SELECT FOR UPDATE SKIP LOCKED to:
    - Lock rows atomically
    - Skip items already locked by other workers
    - Set worker_id to claim ownership

    Body: {
        "worker_id": "server-01-12345",
        "limit": 10
    }

    Returns: {
        "items": [
            {
                "id": 123,
                "payload": {...},
                "worker_id": "server-01-12345",  # Ownership verified
                "created_at": "2026-07-11T...",
                "priority": 5
            }
        ]
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON body"}), 400

        worker_id = data.get("worker_id")
        limit = data.get("limit", 10)

        if not worker_id:
            return jsonify({"error": "Missing worker_id"}), 400

        if queue_name not in ["store", "chunk", "embed", "graph"]:
            return jsonify({"error": f"Invalid queue: {queue_name}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # CRITICAL: SELECT FOR UPDATE SKIP LOCKED
        # - Locks rows atomically
        # - Skips rows already locked by other transactions
        # - Prevents race conditions
        cursor.execute(f"""
            UPDATE queue.{queue_name}
            SET
                status = 'processing',
                worker_id = %s,
                started_at = NOW(),
                heartbeat = NOW()
            WHERE id IN (
                SELECT id
                FROM queue.{queue_name}
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, payload, worker_id, created_at, priority, started_at
        """, (worker_id, limit))

        rows = cursor.fetchall()

        conn.commit()
        cursor.close()
        conn.close()

        if not rows:
            # No items available
            return jsonify({"items": []}), 204

        items = []
        for row in rows:
            item = {
                "id": row[0],
                "payload": row[1],
                "worker_id": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "priority": row[4],
                "started_at": row[5].isoformat() if row[5] else None
            }

            # VERIFY: All items must have our worker_id
            if item["worker_id"] != worker_id:
                logger.error(
                    f"OWNERSHIP VIOLATION: Item {item['id']} has worker_id "
                    f"{item['worker_id']} but we requested {worker_id}"
                )
                # This should never happen due to FOR UPDATE SKIP LOCKED
                # but we check anyway
                continue

            items.append(item)

        logger.info(f"Worker {worker_id} fetched {len(items)} items from {queue_name}")

        return jsonify({"items": items}), 200

    except Exception as e:
        logger.error(f"Error fetching from queue: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/queue/complete/<queue_name>/<int:item_id>", methods=["POST"])
def complete_queue_item(queue_name, item_id):
    """
    Mark queue item as complete with ownership verification

    CRITICAL: Verifies worker_id in UPDATE WHERE clause:
    - UPDATE ... WHERE id = %s AND worker_id = %s
    - If worker_id doesn't match, UPDATE affects 0 rows
    - Returns updated=False if we don't own the item

    Body: {
        "worker_id": "server-01-12345",
        "result": {...},        # optional
        "error": "error msg"    # optional
    }

    Returns: {
        "updated": true,  # False if ownership verification failed
        "item_id": 123
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON body"}), 400

        worker_id = data.get("worker_id")
        result = data.get("result")
        error = data.get("error")

        if not worker_id:
            return jsonify({"error": "Missing worker_id"}), 400

        if queue_name not in ["store", "chunk", "embed", "graph"]:
            return jsonify({"error": f"Invalid queue: {queue_name}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        status = "failed" if error else "completed"

        # CRITICAL: Ownership verification in WHERE clause
        # - AND worker_id = %s ensures we only update items WE own
        # - If another worker owns it, UPDATE affects 0 rows
        cursor.execute(f"""
            UPDATE queue.{queue_name}
            SET
                status = %s,
                completed_at = NOW(),
                result = %s,
                error = %s
            WHERE id = %s AND worker_id = %s
        """, (
            status,
            psycopg2.extras.Json(result) if result else None,
            error,
            item_id,
            worker_id
        ))

        rows_affected = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if rows_affected == 0:
            # Ownership verification failed
            logger.warning(
                f"Worker {worker_id} attempted to complete item {item_id} "
                f"in queue {queue_name} but ownership verification failed"
            )
            return jsonify({
                "updated": False,
                "item_id": item_id,
                "error": "Ownership verification failed"
            }), 200

        logger.info(f"Worker {worker_id} completed item {item_id} in {queue_name}")

        return jsonify({
            "updated": True,
            "item_id": item_id
        }), 200

    except Exception as e:
        logger.error(f"Error completing queue item: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/queue/heartbeat/<queue_name>/<int:item_id>", methods=["POST"])
def heartbeat_queue_item(queue_name, item_id):
    """
    Update heartbeat with ownership verification

    CRITICAL: Verifies worker_id in UPDATE:
    - UPDATE ... SET heartbeat = NOW() WHERE id = %s AND worker_id = %s
    - Prevents other workers from stealing items

    Body: {
        "worker_id": "server-01-12345"
    }

    Returns: {
        "updated": true  # False if ownership lost
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON body"}), 400

        worker_id = data.get("worker_id")

        if not worker_id:
            return jsonify({"error": "Missing worker_id"}), 400

        if queue_name not in ["store", "chunk", "embed", "graph"]:
            return jsonify({"error": f"Invalid queue: {queue_name}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # CRITICAL: Ownership verification in WHERE clause
        cursor.execute(f"""
            UPDATE queue.{queue_name}
            SET heartbeat = NOW()
            WHERE id = %s AND worker_id = %s AND status = 'processing'
        """, (item_id, worker_id))

        rows_affected = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if rows_affected == 0:
            logger.warning(
                f"Heartbeat failed for item {item_id} by worker {worker_id} "
                f"- ownership may have been lost or item completed"
            )
            return jsonify({"updated": False}), 200

        return jsonify({"updated": True}), 200

    except Exception as e:
        logger.error(f"Error updating heartbeat: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/queue/stats/<queue_name>", methods=["GET"])
def queue_stats(queue_name):
    """
    Get queue statistics

    Returns: {
        "queue": "store",
        "pending": 100,
        "processing": 5,
        "completed": 1000,
        "failed": 10,
        "workers": {
            "server-01-12345": 2,
            "server-02-67890": 3
        }
    }
    """
    try:
        if queue_name not in ["store", "chunk", "embed", "graph"]:
            return jsonify({"error": f"Invalid queue: {queue_name}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get status counts
        cursor.execute(f"""
            SELECT status, COUNT(*)
            FROM queue.{queue_name}
            GROUP BY status
        """)

        status_counts = dict(cursor.fetchall())

        # Get worker counts
        cursor.execute(f"""
            SELECT worker_id, COUNT(*)
            FROM queue.{queue_name}
            WHERE status = 'processing' AND worker_id IS NOT NULL
            GROUP BY worker_id
        """)

        worker_counts = dict(cursor.fetchall())

        cursor.close()
        conn.close()

        return jsonify({
            "queue": queue_name,
            "pending": status_counts.get("pending", 0),
            "processing": status_counts.get("processing", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "workers": worker_counts
        }), 200

    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return jsonify({"error": str(e)}), 500
