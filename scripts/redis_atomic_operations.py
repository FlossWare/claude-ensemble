#!/usr/bin/env python3
"""
Redis Atomic Operations via Lua Scripts

Provides race-condition-free queue operations:
- claim_task: Atomically pop from queue and add to processing set
- complete_task: Atomically remove from processing, mark complete, push to next queue
- fail_task: Atomically requeue or move to DLQ based on retry count
- batch_claim: Claim multiple tasks in one atomic operation
- update_heartbeat: Update worker heartbeat
- recover_stuck_tasks: Find and requeue tasks with expired heartbeats

Usage:
    from redis_atomic_operations import RedisAtomicOps

    ops = RedisAtomicOps(host='aio-01', port=6379)

    # Claim a task
    task = ops.claim_task('redis:queue:store:high', 'worker-1')

    # Complete task
    ops.complete_task(task['id'], 'worker-1', result_json, next_queue='redis:queue:chunk')

    # Fail task (auto-requeue or DLQ)
    ops.fail_task(task['id'], 'worker-1', 'Processing error', max_retries=3)
"""

import redis
import json
import time
from typing import Optional, List, Dict

class RedisAtomicOps:
    # Lua script SHA-1 hashes (loaded once per instance)
    SCRIPTS = {}

    # Lua script sources
    LUA_CLAIM_TASK = """
        -- HYBRID mode: Support both ZSET (priority) and LIST (FIFO) queues
        -- ARGV[4] = queue_mode ('zset' or 'list', default='zset')
        local queue_mode = ARGV[4] or 'zset'
        local task_json

        if queue_mode == 'zset' then
            -- Priority queue: ZPOPMIN (lower score = higher priority)
            local result = redis.call('ZPOPMIN', KEYS[1])
            if not result or #result == 0 then
                return nil
            end
            task_json = result[1]  -- ZPOPMIN returns {member, score}
        else
            -- FIFO queue: RPOP
            task_json = redis.call('RPOP', KEYS[1])
            if not task_json then
                return nil
            end
        end

        local task = cjson.decode(task_json)
        local task_id = tostring(task['id'])

        -- Store FULL task data in processing hash
        redis.call('HSET', KEYS[2], task_id, task_json)

        -- Store worker metadata in separate hash
        local metadata = cjson.encode({
            worker_id = ARGV[1],
            claimed_at = ARGV[2],
            heartbeat_expires_at = tonumber(ARGV[2]) + tonumber(ARGV[3])
        })
        redis.call('HSET', KEYS[2] .. ':metadata', task_id, metadata)

        redis.call('HSET', KEYS[3], task_id, ARGV[1] .. ':' .. ARGV[2])
        redis.call('EXPIRE', KEYS[3], math.ceil(tonumber(ARGV[3]) / 1000))

        task['worker_id'] = ARGV[1]
        task['claimed_at'] = ARGV[2]

        return cjson.encode(task)
    """

    LUA_COMPLETE_TASK = """
        local task_id = ARGV[1]
        local worker_id = ARGV[2]
        local next_queue_mode = ARGV[6] or 'list'  -- HYBRID mode: 'list' or 'zset', default 'list'

        -- O(1) lookup in processing hash
        local task_json = redis.call('HGET', KEYS[1], task_id)
        if not task_json then
            return 'ERROR: Task not found in processing hash'
        end

        -- Verify worker ownership
        local metadata_json = redis.call('HGET', KEYS[1] .. ':metadata', task_id)
        if not metadata_json then
            return 'ERROR: Task metadata not found'
        end

        local metadata = cjson.decode(metadata_json)
        if metadata['worker_id'] ~= worker_id then
            return 'ERROR: Task owned by different worker (' .. metadata['worker_id'] .. ')'
        end

        -- Remove from processing (both hash and metadata)
        redis.call('HDEL', KEYS[1], task_id)
        redis.call('HDEL', KEYS[1] .. ':metadata', task_id)
        redis.call('HDEL', KEYS[3], task_id)

        local completion_record = cjson.encode({
            id = task_id,
            worker_id = worker_id,
            completed_at = ARGV[4],
            result = ARGV[3]
        })
        redis.call('HSET', KEYS[2], task_id, completion_record)
        redis.call('EXPIRE', KEYS[2], tonumber(ARGV[5]))

        -- FIX BUG #3: Merge result into original task before pushing to next queue
        if KEYS[4] and KEYS[4] ~= '' then
            local task = cjson.decode(task_json)
            local result = cjson.decode(ARGV[3])

            -- Merge result into task (preserve original fields)
            for key, value in pairs(result) do
                task[key] = value
            end

            -- Add completion metadata
            task['previous_worker'] = worker_id
            task['previous_stage_completed_at'] = ARGV[4]

            local merged_task_json = cjson.encode(task)

            -- HYBRID mode: Push to next queue based on queue type
            if next_queue_mode == 'zset' then
                -- Priority queue: Calculate score based on priority and timestamp
                local priority = tonumber(task['priority']) or 5
                local timestamp_ms = tonumber(ARGV[4])
                local score = (10 - priority) * 1e13 + timestamp_ms  -- Higher priority = lower score
                redis.call('ZADD', KEYS[4], score, merged_task_json)
            else
                -- FIFO queue: Use LPUSH for list
                redis.call('LPUSH', KEYS[4], merged_task_json)
            end
        end

        return 'OK'
    """

    LUA_FAIL_TASK = """
        local task_id = ARGV[1]
        local worker_id = ARGV[2]
        local error_msg = ARGV[3]
        local max_retries = tonumber(ARGV[5])

        -- O(1) lookup in processing hash
        local task_json = redis.call('HGET', KEYS[1], task_id)
        if not task_json then
            return 'ERROR: Task not found in processing hash'
        end

        -- Verify worker ownership
        local metadata_json = redis.call('HGET', KEYS[1] .. ':metadata', task_id)
        if not metadata_json then
            return 'ERROR: Task metadata not found'
        end

        local metadata = cjson.decode(metadata_json)
        if metadata['worker_id'] ~= worker_id then
            return 'ERROR: Task owned by different worker (' .. metadata['worker_id'] .. ')'
        end

        -- Remove from processing (both hash and metadata)
        redis.call('HDEL', KEYS[1], task_id)
        redis.call('HDEL', KEYS[1] .. ':metadata', task_id)
        redis.call('HDEL', KEYS[4], task_id)

        local task = cjson.decode(task_json)
        local retries = tonumber(task['retries']) or 0

        task['retries'] = retries + 1
        task['last_error'] = error_msg
        task['last_failed_at'] = ARGV[4]
        task['worker_id'] = cjson.null

        if task['retries'] <= max_retries then
            -- Requeue to sorted set with score based on priority and timestamp
            local priority = tonumber(task['priority']) or 5
            local timestamp_ms = tonumber(ARGV[4])
            local score = (10 - priority) * 1e13 + timestamp_ms  -- FIX BUG #1: Inverted priority, higher priority = lower score
            redis.call('ZADD', KEYS[2], score, cjson.encode(task))
            return 'REQUEUED'
        else
            task['dead_letter_at'] = ARGV[4]
            redis.call('LPUSH', KEYS[3], cjson.encode(task))
            return 'DEAD_LETTER'
        end
    """

    LUA_BATCH_CLAIM = """
        local worker_id = ARGV[1]
        local current_time = ARGV[2]
        local heartbeat_ttl = tonumber(ARGV[3])
        local batch_size = tonumber(ARGV[4])
        local queue_mode = ARGV[5] or 'zset'  -- HYBRID mode support

        local tasks = {}

        for i = 1, batch_size do
            local task_json

            if queue_mode == 'zset' then
                -- Priority queue: ZPOPMIN
                local result = redis.call('ZPOPMIN', KEYS[1])
                if not result or #result == 0 then
                    break
                end
                task_json = result[1]  -- ZPOPMIN returns {member, score}
            else
                -- FIFO queue: RPOP
                task_json = redis.call('RPOP', KEYS[1])
                if not task_json then
                    break
                end
            end

            local task = cjson.decode(task_json)
            local task_id = tostring(task['id'])

            -- Store FULL task data in processing hash
            redis.call('HSET', KEYS[2], task_id, task_json)

            -- Store worker metadata in separate hash
            local metadata = cjson.encode({
                worker_id = worker_id,
                claimed_at = current_time,
                heartbeat_expires_at = tonumber(current_time) + heartbeat_ttl
            })
            redis.call('HSET', KEYS[2] .. ':metadata', task_id, metadata)

            redis.call('HSET', KEYS[3], task_id, worker_id .. ':' .. current_time)

            task['worker_id'] = worker_id
            task['claimed_at'] = current_time

            table.insert(tasks, task)
        end

        if #tasks > 0 then
            redis.call('EXPIRE', KEYS[3], math.ceil(heartbeat_ttl / 1000))
        end

        return cjson.encode(tasks)
    """

    LUA_UPDATE_HEARTBEAT = """
        local task_id = ARGV[1]
        local worker_id = ARGV[2]
        local current_time = ARGV[3]
        local ttl_sec = tonumber(ARGV[4])
        local ttl_ms = tonumber(ARGV[5])

        local current = redis.call('HGET', KEYS[1], task_id)
        if not current then
            return 'ERROR: Task not in heartbeat registry'
        end

        local parts = {}
        for part in string.gmatch(current, "[^:]+") do
            table.insert(parts, part)
        end

        if parts[1] ~= worker_id then
            return 'ERROR: Task owned by different worker (' .. parts[1] .. ')'
        end

        -- Update heartbeat hash
        redis.call('HSET', KEYS[1], task_id, worker_id .. ':' .. current_time)
        redis.call('EXPIRE', KEYS[1], ttl_sec)

        -- CRITICAL: Also update processing metadata hash
        local metadata_json = redis.call('HGET', KEYS[2], task_id)
        if metadata_json then
            local metadata = cjson.decode(metadata_json)
            metadata['heartbeat_expires_at'] = tonumber(current_time) + ttl_ms
            redis.call('HSET', KEYS[2], task_id, cjson.encode(metadata))
        end

        return 'OK'
    """

    LUA_RECOVER_STUCK = """
        local current_time = tonumber(ARGV[1])
        local stuck_threshold = tonumber(ARGV[2])
        local recovered = 0

        -- Get all task IDs from processing metadata hash
        local metadata_hash = KEYS[1] .. ':metadata'
        local task_ids = redis.call('HKEYS', metadata_hash)

        for _, task_id in ipairs(task_ids) do
            -- Get metadata
            local metadata_json = redis.call('HGET', metadata_hash, task_id)
            if metadata_json then
                local metadata = cjson.decode(metadata_json)
                local heartbeat_expires_at = tonumber(metadata['heartbeat_expires_at'])

                -- Check if task is stuck (heartbeat expired)
                if current_time >= heartbeat_expires_at then
                    -- Get original task JSON from processing hash
                    local task_json = redis.call('HGET', KEYS[1], task_id)

                    if task_json then
                        -- Parse and update task with recovery metadata
                        local task = cjson.decode(task_json)
                        task['recovered_at'] = ARGV[1]
                        task['previous_worker'] = metadata['worker_id']
                        task['stuck_duration_ms'] = current_time - tonumber(metadata['claimed_at'])
                        task['recovery_reason'] = 'heartbeat_expired'
                        task['worker_id'] = cjson.null

                        -- Remove from processing (both hash and metadata)
                        redis.call('HDEL', KEYS[1], task_id)
                        redis.call('HDEL', metadata_hash, task_id)
                        redis.call('HDEL', KEYS[3], task_id)

                        -- Requeue for processing with FULL task data (ZADD for sorted set)
                        local priority = tonumber(task['priority']) or 5
                        local score = (10 - priority) * 1e13 + current_time  -- FIX BUG #1: Inverted priority, higher priority = lower score
                        redis.call('ZADD', KEYS[2], score, cjson.encode(task))

                        recovered = recovered + 1
                    end
                end
            end
        end

        return tostring(recovered)
    """

    def __init__(self, host='aio-01', port=6379, db=0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self._load_scripts()

    def _load_scripts(self):
        """Load Lua scripts into Redis and store SHA-1 hashes."""
        self.SCRIPTS['claim_task'] = self.redis.script_load(self.LUA_CLAIM_TASK)
        self.SCRIPTS['complete_task'] = self.redis.script_load(self.LUA_COMPLETE_TASK)
        self.SCRIPTS['fail_task'] = self.redis.script_load(self.LUA_FAIL_TASK)
        self.SCRIPTS['batch_claim'] = self.redis.script_load(self.LUA_BATCH_CLAIM)
        self.SCRIPTS['update_heartbeat'] = self.redis.script_load(self.LUA_UPDATE_HEARTBEAT)
        self.SCRIPTS['recover_stuck'] = self.redis.script_load(self.LUA_RECOVER_STUCK)

    def claim_task(self, queue_name: str, worker_id: str,
                   heartbeat_ttl_ms: int = 300000, queue_mode: str = 'zset') -> Optional[Dict]:
        """
        Atomically claim a task from the queue.

        Args:
            queue_name: Redis queue key (e.g., 'redis:queue:store:high')
            worker_id: Worker identifier
            heartbeat_ttl_ms: Heartbeat TTL in milliseconds (default 5 minutes)
            queue_mode: Queue type - 'zset' for priority queues, 'list' for FIFO (default 'zset')

        Returns:
            Task dict or None if queue is empty
        """
        # Extract stage:priority from queue name: redis:queue:{stage}:{priority}
        # Support both "redis:queue:store:high" and "redis:queue:store" formats
        parts = queue_name.split(':')
        if len(parts) >= 4:
            # redis:queue:stage:priority -> use "stage:priority"
            stage = f"{parts[2]}:{parts[3]}"
        elif len(parts) >= 3:
            # redis:queue:stage -> use "stage"
            stage = parts[2]
        else:
            # Fallback for non-standard format
            stage = parts[-1]
        processing_set = f'redis:processing:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'
        current_time_ms = int(time.time() * 1000)

        result = self.redis.evalsha(
            self.SCRIPTS['claim_task'],
            3,  # numkeys
            queue_name, processing_set, heartbeat_hash,
            worker_id, str(current_time_ms), str(heartbeat_ttl_ms), queue_mode
        )

        return json.loads(result) if result else None

    def complete_task(self, task_id: str, worker_id: str, result_json: str,
                     stage: str = 'store', next_queue: Optional[str] = None,
                     completed_ttl_sec: int = 86400, next_queue_mode: str = 'list') -> str:
        """
        Atomically complete a task.

        Args:
            task_id: Task identifier
            worker_id: Worker identifier (must match claim)
            result_json: JSON result to store
            stage: Stage name with optional priority (e.g., 'store', 'store:high', 'chunk:medium')
            next_queue: Optional next queue to push result to (full name: 'redis:queue:chunk:high')
            completed_ttl_sec: TTL for completed record (default 24 hours)
            next_queue_mode: Queue type for next queue - 'list' (FIFO) or 'zset' (priority), default 'list'

        Returns:
            "OK" or error message
        """
        processing_set = f'redis:processing:{stage}'
        completed_hash = f'redis:completed:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'
        current_time_ms = int(time.time() * 1000)

        return self.redis.evalsha(
            self.SCRIPTS['complete_task'],
            4,  # numkeys
            processing_set, completed_hash, heartbeat_hash, next_queue or '',
            str(task_id), worker_id, result_json, str(current_time_ms), str(completed_ttl_sec), next_queue_mode
        )

    def fail_task(self, task_id: str, worker_id: str, error_msg: str,
                  stage: str = 'store', max_retries: int = 3) -> str:
        """
        Atomically fail a task (requeue or move to DLQ).

        Args:
            task_id: Task identifier
            worker_id: Worker identifier (must match claim)
            error_msg: Error message
            stage: Stage name with optional priority (e.g., 'store', 'store:high', 'chunk:medium')
            max_retries: Maximum retry attempts before DLQ

        Returns:
            "REQUEUED" or "DEAD_LETTER" or error message
        """
        processing_set = f'redis:processing:{stage}'
        queue_name = f'redis:queue:{stage}'
        dlq_name = f'redis:dlq:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'
        current_time_ms = int(time.time() * 1000)

        return self.redis.evalsha(
            self.SCRIPTS['fail_task'],
            4,  # numkeys
            processing_set, queue_name, dlq_name, heartbeat_hash,
            str(task_id), worker_id, error_msg, str(current_time_ms), str(max_retries)
        )

    def batch_claim_tasks(self, queue_name: str, worker_id: str,
                         batch_size: int = 10, heartbeat_ttl_ms: int = 300000,
                         queue_mode: str = 'zset') -> List[Dict]:
        """
        Atomically claim multiple tasks in one operation.

        Args:
            queue_name: Redis queue key (e.g., 'redis:queue:store:high')
            worker_id: Worker identifier
            batch_size: Number of tasks to claim
            heartbeat_ttl_ms: Heartbeat TTL in milliseconds
            queue_mode: Queue type - 'zset' for priority queues, 'list' for FIFO (default 'zset')

        Returns:
            List of task dicts
        """
        # Extract stage:priority from queue name: redis:queue:{stage}:{priority}
        # Support both "redis:queue:store:high" and "redis:queue:store" formats
        parts = queue_name.split(':')
        if len(parts) >= 4:
            # redis:queue:stage:priority -> use "stage:priority"
            stage = f"{parts[2]}:{parts[3]}"
        elif len(parts) >= 3:
            # redis:queue:stage -> use "stage"
            stage = parts[2]
        else:
            # Fallback for non-standard format
            stage = parts[-1]
        processing_set = f'redis:processing:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'
        current_time_ms = int(time.time() * 1000)

        result = self.redis.evalsha(
            self.SCRIPTS['batch_claim'],
            3,  # numkeys
            queue_name, processing_set, heartbeat_hash,
            worker_id, str(current_time_ms), str(heartbeat_ttl_ms), str(batch_size), queue_mode
        )

        return json.loads(result) if result else []

    def update_heartbeat(self, task_id: str, worker_id: str, stage: str = 'store',
                        heartbeat_ttl_sec: int = 300) -> str:
        """
        Update worker heartbeat for a task.

        Args:
            task_id: Task identifier
            worker_id: Worker identifier
            stage: Stage name with optional priority (e.g., 'store', 'store:high', 'chunk:medium')
            heartbeat_ttl_sec: Heartbeat TTL in seconds

        Returns:
            "OK" or error message
        """
        heartbeat_hash = f'redis:heartbeat:{stage}'
        processing_metadata_hash = f'redis:processing:{stage}:metadata'
        current_time_ms = int(time.time() * 1000)
        heartbeat_ttl_ms = heartbeat_ttl_sec * 1000

        return self.redis.evalsha(
            self.SCRIPTS['update_heartbeat'],
            2,  # numkeys (FIX BUG #2: now updates both heartbeat hash AND metadata hash)
            heartbeat_hash, processing_metadata_hash,
            str(task_id), worker_id, str(current_time_ms), str(heartbeat_ttl_sec), str(heartbeat_ttl_ms)
        )

    def recover_stuck_tasks(self, stage: str = 'store',
                           stuck_threshold_ms: int = 300000) -> int:
        """
        Recover tasks with expired heartbeats.

        Args:
            stage: Stage name with optional priority (e.g., 'store', 'store:high', 'chunk:medium')
            stuck_threshold_ms: Time since last heartbeat to consider stuck (default 5 min)

        Returns:
            Number of recovered tasks
        """
        processing_set = f'redis:processing:{stage}'
        queue_name = f'redis:queue:{stage}'
        heartbeat_hash = f'redis:heartbeat:{stage}'
        current_time_ms = int(time.time() * 1000)

        result = self.redis.evalsha(
            self.SCRIPTS['recover_stuck'],
            3,  # numkeys
            processing_set, queue_name, heartbeat_hash,
            str(current_time_ms), str(stuck_threshold_ms)
        )

        return int(result)


if __name__ == '__main__':
    # Example usage
    ops = RedisAtomicOps(host='aio-01', port=6379)

    # Claim a task from priority queue
    task = ops.claim_task('redis:queue:store:high', 'worker-test-1')
    if task:
        print(f"Claimed task: {task['id']}")

        # Complete successfully (stage includes priority level)
        result = json.dumps({'status': 'processed'})
        status = ops.complete_task(
            task['id'],
            'worker-test-1',
            result,
            stage='store:high',  # Match the queue's stage:priority format
            next_queue='redis:queue:chunk:medium'  # Next stage with priority
        )
        print(f"Complete status: {status}")
    else:
        print("No tasks available")

    # Recover stuck tasks (specify stage:priority)
    recovered = ops.recover_stuck_tasks('store:high')
    print(f"Recovered {recovered} stuck tasks")
