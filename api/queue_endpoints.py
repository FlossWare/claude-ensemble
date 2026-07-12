"""
Queue Management Endpoints for Flask API

Add these routes to application.py:
- POST /queue/add - Add item to queue
- GET /queue/fetch/<queue_name> - Fetch next pending task
- POST /queue/complete/<queue_name>/<task_id> - Mark task complete
- GET /queue/stats - Queue statistics

All routes include idempotency key support.
"""

from flask import Blueprint, request, jsonify
import json
import hashlib
from datetime import datetime

queue_bp = Blueprint('queue', __name__, url_prefix='/queue')

def get_db_connection():
    """Import from parent application.py"""
    from application import get_db
    return get_db()


@queue_bp.route('/add', methods=['POST'])
def queue_add():
    """
    Add item to queue

    POST body:
    {
        "queue": "store",  # or "chunk", "embed", "graph"
        "data": { ... },   # Task-specific data
        "priority": 5,     # Optional, default 5 (higher = more urgent)
        "idempotency_key": "optional-unique-key"
    }

    Returns:
    {
        "queued": true,
        "task_id": 123,
        "queue": "store",
        "idempotency_key": "..."
    }
    """
    try:
        body = request.get_json()

        if not body or 'queue' not in body or 'data' not in body:
            return jsonify({
                'error': 'Missing required fields: queue, data'
            }), 400

        queue_name = body['queue']
        data = body['data']
        priority = body.get('priority', 5)
        idempotency_key = body.get('idempotency_key')

        # Validate queue name
        valid_queues = ['store', 'chunk', 'embed', 'graph']
        if queue_name not in valid_queues:
            return jsonify({
                'error': f'Invalid queue: {queue_name}. Must be one of {valid_queues}'
            }), 400

        # Auto-generate idempotency key if not provided
        if not idempotency_key:
            # Hash based on data content
            data_str = json.dumps(data, sort_keys=True)
            idempotency_key = f"{queue_name}:{hashlib.md5(data_str.encode()).hexdigest()}"

        # Extract file_path if present (for tracking)
        file_path = data.get('file_path')

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if already exists
            cursor.execute(f"""
                SELECT id, status
                FROM queue.{queue_name}
                WHERE idempotency_key = %s
            """, (idempotency_key,))

            existing = cursor.fetchone()

            if existing:
                return jsonify({
                    'queued': False,
                    'task_id': existing['id'],
                    'status': existing['status'],
                    'message': 'Task already exists with this idempotency key',
                    'idempotency_key': idempotency_key
                }), 200

            # Insert new task
            cursor.execute(f"""
                INSERT INTO queue.{queue_name}
                (data, priority, idempotency_key, file_path)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                json.dumps(data),
                priority,
                idempotency_key,
                file_path
            ))

            task_id = cursor.fetchone()['id']
            conn.commit()

            return jsonify({
                'queued': True,
                'task_id': task_id,
                'queue': queue_name,
                'idempotency_key': idempotency_key
            }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@queue_bp.route('/fetch/<queue_name>', methods=['GET'])
def queue_fetch(queue_name: str):
    """
    Fetch next pending task from queue

    Query params:
    - worker_id: Unique worker identifier (required)

    Returns next task or 404 if queue empty
    """
    valid_queues = ['store', 'chunk', 'embed', 'graph']
    if queue_name not in valid_queues:
        return jsonify({'error': f'Invalid queue: {queue_name}'}), 400

    worker_id = request.args.get('worker_id')
    if not worker_id:
        return jsonify({'error': 'Missing worker_id parameter'}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Fetch next task with idempotency check
            cursor.execute(f"""
                WITH next_task AS (
                    SELECT id, data, idempotency_key, file_path, priority
                    FROM queue.{queue_name}
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                SELECT *
                FROM next_task
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM queue.{queue_name}
                    WHERE idempotency_key = next_task.idempotency_key
                      AND idempotency_key IS NOT NULL
                      AND status = 'completed'
                )
            """)

            task = cursor.fetchone()

            if not task:
                return jsonify({'message': 'No tasks available'}), 404

            # Claim the task
            cursor.execute(f"""
                UPDATE queue.{queue_name}
                SET status = 'processing',
                    started_at = NOW(),
                    worker_id = %s
                WHERE id = %s
            """, (worker_id, task['id']))

            conn.commit()

            return jsonify({
                'task_id': task['id'],
                'data': task['data'],
                'idempotency_key': task['idempotency_key'],
                'file_path': task['file_path'],
                'priority': task['priority']
            }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@queue_bp.route('/complete/<queue_name>/<int:task_id>', methods=['POST'])
def queue_complete(queue_name: str, task_id: int):
    """
    Mark task as completed

    POST body (optional):
    {
        "result": { ... }  # Optional result data
    }
    """
    valid_queues = ['store', 'chunk', 'embed', 'graph']
    if queue_name not in valid_queues:
        return jsonify({'error': f'Invalid queue: {queue_name}'}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE queue.{queue_name}
                SET status = 'completed',
                    completed_at = NOW(),
                    error = NULL
                WHERE id = %s
                RETURNING id, idempotency_key
            """, (task_id,))

            result = cursor.fetchone()

            if not result:
                return jsonify({'error': 'Task not found'}), 404

            conn.commit()

            return jsonify({
                'completed': True,
                'task_id': result['id'],
                'idempotency_key': result['idempotency_key']
            }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@queue_bp.route('/fail/<queue_name>/<int:task_id>', methods=['POST'])
def queue_fail(queue_name: str, task_id: int):
    """
    Mark task as failed

    POST body:
    {
        "error": "Error message",
        "max_retries": 3  # Optional, default 3
    }
    """
    valid_queues = ['store', 'chunk', 'embed', 'graph']
    if queue_name not in valid_queues:
        return jsonify({'error': f'Invalid queue: {queue_name}'}), 400

    try:
        body = request.get_json() or {}
        error_msg = body.get('error', 'Unknown error')
        max_retries = body.get('max_retries', 3)

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE queue.{queue_name}
                SET retries = retries + 1,
                    error = %s,
                    status = CASE
                        WHEN retries + 1 >= %s THEN 'failed'
                        ELSE 'pending'
                    END,
                    started_at = NULL,
                    worker_id = NULL
                WHERE id = %s
                RETURNING id, retries, status
            """, (error_msg, max_retries, task_id))

            result = cursor.fetchone()

            if not result:
                return jsonify({'error': 'Task not found'}), 404

            conn.commit()

            return jsonify({
                'task_id': result['id'],
                'retries': result['retries'],
                'status': result['status'],
                'will_retry': result['status'] == 'pending'
            }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@queue_bp.route('/stats', methods=['GET'])
def queue_stats():
    """
    Get statistics for all queues

    Returns counts by status for each queue
    """
    try:
        valid_queues = ['store', 'chunk', 'embed', 'graph']
        stats = {}

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for queue_name in valid_queues:
                cursor.execute(f"""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'pending') as pending,
                        COUNT(*) FILTER (WHERE status = 'processing') as processing,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        COUNT(*) as total,
                        MAX(created_at) as last_added,
                        MAX(completed_at) as last_completed
                    FROM queue.{queue_name}
                """)

                result = cursor.fetchone()
                stats[queue_name] = dict(result) if result else {}

        return jsonify(stats), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Instructions for adding to application.py:
"""
Add this to application.py after other route definitions:

    # Queue management endpoints
    from queue_endpoints import queue_bp
    app.register_blueprint(queue_bp)
"""
