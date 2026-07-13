-- Redis Lua Scripts for Atomic Queue Operations
-- Provides race-condition-free claim, complete, and fail operations

-- Helper: Safe JSON decode with error handling
local function safe_decode(json_str, context)
    if not json_str or json_str == '' then
        return nil, 'ERROR: Empty JSON string in ' .. context
    end

    local success, result = pcall(cjson.decode, json_str)
    if not success then
        return nil, 'ERROR: Invalid JSON in ' .. context .. ': ' .. tostring(result)
    end

    return result, nil
end

-- Helper: Safe JSON encode with error handling
local function safe_encode(obj, context)
    local success, result = pcall(cjson.encode, obj)
    if not success then
        return nil, 'ERROR: JSON encode failed in ' .. context .. ': ' .. tostring(result)
    end

    return result, nil
end

-- Helper: Validate required arguments
local function validate_args(required_keys, required_argv, context)
    if #KEYS < required_keys then
        return 'ERROR: ' .. context .. ' requires ' .. required_keys .. ' KEYS, got ' .. #KEYS
    end

    if #ARGV < required_argv then
        return 'ERROR: ' .. context .. ' requires ' .. required_argv .. ' ARGV, got ' .. #ARGV
    end

    return nil
end

-- Helper: Safe Redis call with error handling
local function safe_redis_call(cmd, ...)
    local success, result = pcall(redis.call, cmd, ...)
    if not success then
        return nil, 'ERROR: Redis ' .. cmd .. ' failed: ' .. tostring(result)
    end

    return result, nil
end

-- Script 1: Atomic Claim Task (HYBRID mode)
-- KEYS[1] = queue name (e.g., "redis:queue:store:high")
-- KEYS[2] = processing hash (e.g., "redis:processing:store")
-- KEYS[3] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- ARGV[1] = worker_id
-- ARGV[2] = current timestamp (ms)
-- ARGV[3] = heartbeat TTL (ms, default 300000 = 5 minutes)
-- ARGV[4] = queue_mode (optional: "zset" for sorted sets, "list" for FIFO lists, default="list")
-- Returns: JSON task or nil or error message
local function claim_task()
    -- Validate arguments
    local err = validate_args(3, 3, 'claim_task')
    if err then return err end

    -- Validate worker_id
    if not ARGV[1] or ARGV[1] == '' then
        return 'ERROR: worker_id (ARGV[1]) is required'
    end

    -- Validate timestamp
    local current_time = tonumber(ARGV[2])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[2]): ' .. tostring(ARGV[2])
    end

    -- Validate heartbeat TTL
    local heartbeat_ttl = tonumber(ARGV[3])
    if not heartbeat_ttl or heartbeat_ttl <= 0 then
        return 'ERROR: Invalid heartbeat TTL (ARGV[3]): ' .. tostring(ARGV[3])
    end

    -- Determine queue mode (HYBRID: zset for priority, list for FIFO)
    local queue_mode = ARGV[4] or 'list'

    -- Pop from queue (ZPOPMIN for sorted sets, RPOP for lists)
    local task_json, err
    if queue_mode == 'zset' then
        -- Priority queue: ZPOPMIN (lowest score = highest priority)
        -- Formula: (10 - priority) * 1e13 + timestamp_ms
        -- Higher priority → lower score → pops first with ZPOPMIN
        local result, err = safe_redis_call('ZPOPMIN', KEYS[1])
        if err then return err end
        if not result or #result == 0 then
            return nil
        end
        -- ZPOPMIN returns [member, score]
        task_json = result[1]
    else
        -- FIFO queue: RPOP
        task_json, err = safe_redis_call('RPOP', KEYS[1])
        if err then return err end
        if not task_json then
            return nil
        end
    end

    -- Parse task
    local task, err = safe_decode(task_json, 'claim_task task_json')
    if err then return err end

    -- Validate task has id field
    if not task['id'] then
        return 'ERROR: Task missing required field: id'
    end

    local task_id = tostring(task['id'])

    -- Store FULL task data in processing hash (FIX BUG #1 & #3)
    -- Changed from SADD to HSET for O(1) lookups
    local _, err = safe_redis_call('HSET', KEYS[2], task_id, task_json)
    if err then return err end

    -- Store worker metadata in separate hash
    local metadata, err = safe_encode({
        worker_id = ARGV[1],
        claimed_at = ARGV[2],
        heartbeat_expires_at = current_time + heartbeat_ttl
    }, 'claim_task metadata')
    if err then return err end

    local _, err = safe_redis_call('HSET', KEYS[2] .. ':metadata', task_id, metadata)
    if err then return err end

    -- Set worker heartbeat
    local _, err = safe_redis_call('HSET', KEYS[3], task_id, ARGV[1] .. ':' .. ARGV[2])
    if err then return err end

    local _, err = safe_redis_call('EXPIRE', KEYS[3], math.ceil(heartbeat_ttl / 1000))
    if err then return err end

    -- Update task with worker info
    task['worker_id'] = ARGV[1]
    task['claimed_at'] = ARGV[2]

    return safe_encode(task, 'claim_task result')
end

-- Script 2: Atomic Complete Task
-- KEYS[1] = processing hash (e.g., "redis:processing:store")
-- KEYS[2] = completed hash (e.g., "redis:completed:store")
-- KEYS[3] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- KEYS[4] = next queue (e.g., "redis:queue:chunk") or nil
-- ARGV[1] = task_id
-- ARGV[2] = worker_id (for verification)
-- ARGV[3] = result_json (for next stage)
-- ARGV[4] = current timestamp (ms)
-- ARGV[5] = completed TTL (seconds, default 86400 = 24h)
-- Returns: "OK" or error message
local function complete_task()
    -- Validate arguments
    local err = validate_args(3, 5, 'complete_task')
    if err then return err end

    local task_id = ARGV[1]
    local worker_id = ARGV[2]

    -- Validate required fields
    if not task_id or task_id == '' then
        return 'ERROR: task_id (ARGV[1]) is required'
    end

    if not worker_id or worker_id == '' then
        return 'ERROR: worker_id (ARGV[2]) is required'
    end

    -- Validate timestamp
    local current_time = tonumber(ARGV[4])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[4]): ' .. tostring(ARGV[4])
    end

    -- Validate TTL
    local ttl = tonumber(ARGV[5])
    if not ttl or ttl <= 0 then
        return 'ERROR: Invalid TTL (ARGV[5]): ' .. tostring(ARGV[5])
    end

    -- O(1) lookup in processing hash (FIX BUG #3)
    local task_json, err = safe_redis_call('HGET', KEYS[1], task_id)
    if err then return err end

    if not task_json then
        return 'ERROR: Task ' .. task_id .. ' not found in processing hash'
    end

    -- Verify worker ownership
    local metadata_json, err = safe_redis_call('HGET', KEYS[1] .. ':metadata', task_id)
    if err then return err end

    if not metadata_json then
        return 'ERROR: Task ' .. task_id .. ' metadata not found'
    end

    local metadata, err = safe_decode(metadata_json, 'complete_task metadata')
    if err then return err end

    if metadata['worker_id'] ~= worker_id then
        return 'ERROR: Task ' .. task_id .. ' owned by different worker (' .. tostring(metadata['worker_id']) .. ')'
    end

    -- Remove from processing (both hash and metadata)
    local _, err = safe_redis_call('HDEL', KEYS[1], task_id)
    if err then return err end

    local _, err = safe_redis_call('HDEL', KEYS[1] .. ':metadata', task_id)
    if err then return err end

    -- Remove heartbeat
    local _, err = safe_redis_call('HDEL', KEYS[3], task_id)
    if err then return err end

    -- Store completion record
    local completion_record, err = safe_encode({
        id = task_id,
        worker_id = worker_id,
        completed_at = ARGV[4],
        result = ARGV[3]
    }, 'complete_task completion_record')
    if err then return err end

    local _, err = safe_redis_call('HSET', KEYS[2], task_id, completion_record)
    if err then return err end

    local _, err = safe_redis_call('EXPIRE', KEYS[2], ttl)
    if err then return err end

    -- Push to next queue if specified
    if KEYS[4] and KEYS[4] ~= '' then
        local _, err = safe_redis_call('LPUSH', KEYS[4], ARGV[3])
        if err then return err end
    end

    return 'OK'
end

-- Script 3: Atomic Fail Task (HYBRID mode)
-- KEYS[1] = processing hash (e.g., "redis:processing:store")
-- KEYS[2] = queue name (e.g., "redis:queue:store:medium")
-- KEYS[3] = DLQ name (e.g., "redis:dlq:store")
-- KEYS[4] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- ARGV[1] = task_id
-- ARGV[2] = worker_id (for verification)
-- ARGV[3] = error_message
-- ARGV[4] = current timestamp (ms)
-- ARGV[5] = max_retries (default 3)
-- ARGV[6] = queue_mode (optional: "zset" for sorted sets, "list" for FIFO lists, default="list")
-- ARGV[7] = priority_score (optional: for zset mode, score to use when requeueing)
-- Returns: "REQUEUED" or "DEAD_LETTER" or error message
local function fail_task()
    -- Validate arguments
    local err = validate_args(4, 5, 'fail_task')
    if err then return err end

    local task_id = ARGV[1]
    local worker_id = ARGV[2]
    local error_msg = ARGV[3]

    -- Validate required fields
    if not task_id or task_id == '' then
        return 'ERROR: task_id (ARGV[1]) is required'
    end

    if not worker_id or worker_id == '' then
        return 'ERROR: worker_id (ARGV[2]) is required'
    end

    if not error_msg or error_msg == '' then
        error_msg = 'Unknown error'
    end

    -- Validate timestamp
    local current_time = tonumber(ARGV[4])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[4]): ' .. tostring(ARGV[4])
    end

    -- Validate max_retries
    local max_retries = tonumber(ARGV[5])
    if not max_retries or max_retries < 0 then
        return 'ERROR: Invalid max_retries (ARGV[5]): ' .. tostring(ARGV[5])
    end

    -- O(1) lookup in processing hash (FIX BUG #3)
    local task_json, err = safe_redis_call('HGET', KEYS[1], task_id)
    if err then return err end

    if not task_json then
        return 'ERROR: Task ' .. task_id .. ' not found in processing hash'
    end

    -- Verify worker ownership
    local metadata_json, err = safe_redis_call('HGET', KEYS[1] .. ':metadata', task_id)
    if err then return err end

    if not metadata_json then
        return 'ERROR: Task ' .. task_id .. ' metadata not found'
    end

    local metadata, err = safe_decode(metadata_json, 'fail_task metadata')
    if err then return err end

    if metadata['worker_id'] ~= worker_id then
        return 'ERROR: Task ' .. task_id .. ' owned by different worker (' .. tostring(metadata['worker_id']) .. ')'
    end

    -- Remove from processing (both hash and metadata)
    local _, err = safe_redis_call('HDEL', KEYS[1], task_id)
    if err then return err end

    local _, err = safe_redis_call('HDEL', KEYS[1] .. ':metadata', task_id)
    if err then return err end

    -- Parse task and update retry info
    local task, err = safe_decode(task_json, 'fail_task task')
    if err then return err end

    local retries = tonumber(task['retries']) or 0

    -- Remove heartbeat
    local _, err = safe_redis_call('HDEL', KEYS[4], task_id)
    if err then return err end

    -- Increment retry count
    task['retries'] = retries + 1
    task['last_error'] = error_msg
    task['last_failed_at'] = ARGV[4]
    task['worker_id'] = cjson.null  -- Clear worker assignment

    -- Determine queue mode (HYBRID: zset for priority, list for FIFO)
    local queue_mode = ARGV[6] or 'list'

    -- Requeue or move to DLQ
    if task['retries'] <= max_retries then
        -- Requeue for retry
        local task_json_updated, err = safe_encode(task, 'fail_task requeue')
        if err then return err end

        if queue_mode == 'zset' then
            -- Priority queue: ZADD with score
            local score = tonumber(ARGV[7])
            if not score then
                return 'ERROR: Invalid priority_score (ARGV[7]): ' .. tostring(ARGV[7])
            end
            local _, err = safe_redis_call('ZADD', KEYS[2], score, task_json_updated)
            if err then return err end
        else
            -- FIFO queue: RPUSH
            local _, err = safe_redis_call('RPUSH', KEYS[2], task_json_updated)
            if err then return err end
        end

        return 'REQUEUED'
    else
        -- Move to dead letter queue (always FIFO list)
        task['dead_letter_at'] = ARGV[4]

        local task_json_updated, err = safe_encode(task, 'fail_task dlq')
        if err then return err end

        local _, err = safe_redis_call('LPUSH', KEYS[3], task_json_updated)
        if err then return err end

        return 'DEAD_LETTER'
    end
end

-- Script 4: Batch Claim Tasks (HYBRID mode)
-- KEYS[1] = queue name (e.g., "redis:queue:store:high")
-- KEYS[2] = processing hash (e.g., "redis:processing:store")
-- KEYS[3] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- ARGV[1] = worker_id
-- ARGV[2] = current timestamp (ms)
-- ARGV[3] = heartbeat TTL (ms, default 300000 = 5 minutes)
-- ARGV[4] = batch_size (default 10)
-- ARGV[5] = queue_mode (optional: "zset" for sorted sets, "list" for FIFO lists, default="list")
-- Returns: JSON array of tasks or error message
local function batch_claim_tasks()
    -- Validate arguments
    local err = validate_args(3, 4, 'batch_claim_tasks')
    if err then return err end

    local worker_id = ARGV[1]

    -- Validate worker_id
    if not worker_id or worker_id == '' then
        return 'ERROR: worker_id (ARGV[1]) is required'
    end

    -- Validate timestamp
    local current_time = tonumber(ARGV[2])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[2]): ' .. tostring(ARGV[2])
    end

    -- Validate heartbeat TTL
    local heartbeat_ttl = tonumber(ARGV[3])
    if not heartbeat_ttl or heartbeat_ttl <= 0 then
        return 'ERROR: Invalid heartbeat TTL (ARGV[3]): ' .. tostring(ARGV[3])
    end

    -- Validate batch_size
    local batch_size = tonumber(ARGV[4])
    if not batch_size or batch_size <= 0 or batch_size > 1000 then
        return 'ERROR: Invalid batch_size (ARGV[4]): ' .. tostring(ARGV[4]) .. ' (must be 1-1000)'
    end

    -- Determine queue mode (HYBRID: zset for priority, list for FIFO)
    local queue_mode = ARGV[5] or 'list'

    local tasks = {}
    local errors = {}

    for i = 1, batch_size do
        local task_json, err

        if queue_mode == 'zset' then
            -- Priority queue: ZPOPMIN (lowest score = highest priority)
            -- Formula: (10 - priority) * 1e13 + timestamp_ms
            local result, err = safe_redis_call('ZPOPMIN', KEYS[1])
            if err then
                table.insert(errors, 'Task ' .. i .. ': ' .. err)
                break
            end
            if not result or #result == 0 then
                break
            end
            -- ZPOPMIN returns [member, score]
            task_json = result[1]
        else
            -- FIFO queue: RPOP
            task_json, err = safe_redis_call('RPOP', KEYS[1])
            if err then
                table.insert(errors, 'Task ' .. i .. ': ' .. err)
                break
            end
            if not task_json then
                break
            end
        end

        local task, err = safe_decode(task_json, 'batch_claim_tasks task ' .. i)
        if err then
            table.insert(errors, err)
            -- Re-push failed task back to queue
            safe_redis_call('LPUSH', KEYS[1], task_json)
            break
        end

        -- Validate task has id field
        if not task['id'] then
            table.insert(errors, 'Task ' .. i .. ' missing required field: id')
            -- Re-push failed task back to queue
            safe_redis_call('LPUSH', KEYS[1], task_json)
            break
        end

        local task_id = tostring(task['id'])

        -- Store FULL task data in processing hash (FIX BUG #1 & #3)
        local _, err = safe_redis_call('HSET', KEYS[2], task_id, task_json)
        if err then
            table.insert(errors, 'Task ' .. task_id .. ': ' .. err)
            break
        end

        -- Store worker metadata in separate hash
        local metadata, err = safe_encode({
            worker_id = worker_id,
            claimed_at = current_time,
            heartbeat_expires_at = current_time + heartbeat_ttl
        }, 'batch_claim_tasks metadata ' .. task_id)
        if err then
            table.insert(errors, err)
            break
        end

        local _, err = safe_redis_call('HSET', KEYS[2] .. ':metadata', task_id, metadata)
        if err then
            table.insert(errors, 'Task ' .. task_id .. ' metadata: ' .. err)
            break
        end

        -- Set worker heartbeat
        local _, err = safe_redis_call('HSET', KEYS[3], task_id, worker_id .. ':' .. current_time)
        if err then
            table.insert(errors, 'Task ' .. task_id .. ' heartbeat: ' .. err)
            break
        end

        -- Update task
        task['worker_id'] = worker_id
        task['claimed_at'] = current_time

        table.insert(tasks, task)
    end

    -- Set heartbeat expiry
    if #tasks > 0 then
        local _, err = safe_redis_call('EXPIRE', KEYS[3], math.ceil(heartbeat_ttl / 1000))
        if err then
            table.insert(errors, 'Heartbeat expiry: ' .. err)
        end
    end

    -- If there were errors, return them
    if #errors > 0 then
        return 'ERROR: Batch claim partial failure - ' .. table.concat(errors, '; ')
    end

    return safe_encode(tasks, 'batch_claim_tasks result')
end

-- Script 5: Heartbeat Update
-- KEYS[1] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- KEYS[2] = processing metadata hash (e.g., "redis:processing:store:metadata")
-- ARGV[1] = task_id
-- ARGV[2] = worker_id
-- ARGV[3] = current timestamp (ms)
-- ARGV[4] = heartbeat TTL (seconds)
-- ARGV[5] = heartbeat TTL (ms)
-- Returns: "OK" or error message
local function update_heartbeat()
    -- Validate arguments
    local err = validate_args(2, 5, 'update_heartbeat')
    if err then return err end

    local task_id = ARGV[1]
    local worker_id = ARGV[2]

    -- Validate required fields
    if not task_id or task_id == '' then
        return 'ERROR: task_id (ARGV[1]) is required'
    end

    if not worker_id or worker_id == '' then
        return 'ERROR: worker_id (ARGV[2]) is required'
    end

    -- Validate timestamp
    local current_time = tonumber(ARGV[3])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[3]): ' .. tostring(ARGV[3])
    end

    -- Validate TTL seconds
    local ttl_sec = tonumber(ARGV[4])
    if not ttl_sec or ttl_sec <= 0 then
        return 'ERROR: Invalid TTL seconds (ARGV[4]): ' .. tostring(ARGV[4])
    end

    -- Validate TTL milliseconds
    local ttl_ms = tonumber(ARGV[5])
    if not ttl_ms or ttl_ms <= 0 then
        return 'ERROR: Invalid TTL milliseconds (ARGV[5]): ' .. tostring(ARGV[5])
    end

    -- Get current heartbeat
    local current, err = safe_redis_call('HGET', KEYS[1], task_id)
    if err then return err end

    if not current then
        return 'ERROR: Task ' .. task_id .. ' not in heartbeat registry'
    end

    -- Verify worker ownership
    local parts = {}
    for part in string.gmatch(current, "[^:]+") do
        table.insert(parts, part)
    end

    if #parts < 1 then
        return 'ERROR: Invalid heartbeat format for task ' .. task_id
    end

    if parts[1] ~= worker_id then
        return 'ERROR: Task ' .. task_id .. ' owned by different worker (' .. tostring(parts[1]) .. ')'
    end

    -- Update heartbeat hash
    local _, err = safe_redis_call('HSET', KEYS[1], task_id, worker_id .. ':' .. current_time)
    if err then return err end

    local _, err = safe_redis_call('EXPIRE', KEYS[1], ttl_sec)
    if err then return err end

    -- CRITICAL: Also update processing metadata hash (FIX BUG #2)
    -- This synchronizes heartbeat_expires_at used by recovery script
    local metadata_json, err = safe_redis_call('HGET', KEYS[2], task_id)
    if err then return err end

    if metadata_json then
        local metadata, err = safe_decode(metadata_json, 'update_heartbeat metadata')
        if err then return err end

        metadata['heartbeat_expires_at'] = current_time + ttl_ms

        local updated_metadata, err = safe_encode(metadata, 'update_heartbeat updated_metadata')
        if err then return err end

        local _, err = safe_redis_call('HSET', KEYS[2], task_id, updated_metadata)
        if err then return err end
    end

    return 'OK'
end

-- Script 6: Recover Stuck Tasks (HYBRID mode)
-- KEYS[1] = processing hash (e.g., "redis:processing:store")
-- KEYS[2] = queue name (e.g., "redis:queue:store:medium")
-- KEYS[3] = worker heartbeat hash (e.g., "redis:heartbeat:store")
-- ARGV[1] = current timestamp (ms)
-- ARGV[2] = stuck threshold (ms, default 300000 = 5 minutes)
-- ARGV[3] = queue_mode (optional: "zset" for sorted sets, "list" for FIFO lists, default="list")
-- ARGV[4] = priority_multiplier (optional: for zset mode, default 1e13)
-- Returns: count of recovered tasks or error message
local function recover_stuck_tasks()
    -- Validate arguments
    local err = validate_args(3, 2, 'recover_stuck_tasks')
    if err then return err end

    -- Validate timestamp
    local current_time = tonumber(ARGV[1])
    if not current_time or current_time <= 0 then
        return 'ERROR: Invalid timestamp (ARGV[1]): ' .. tostring(ARGV[1])
    end

    -- Validate stuck threshold
    local stuck_threshold = tonumber(ARGV[2])
    if not stuck_threshold or stuck_threshold <= 0 then
        return 'ERROR: Invalid stuck threshold (ARGV[2]): ' .. tostring(ARGV[2])
    end

    local recovered = 0
    local errors = {}

    -- Get all task IDs from processing metadata hash (O(n) but unavoidable for scan)
    local metadata_hash = KEYS[1] .. ':metadata'
    local task_ids, err = safe_redis_call('HKEYS', metadata_hash)
    if err then return err end

    if not task_ids then
        return '0'
    end

    for _, task_id in ipairs(task_ids) do
        -- Get metadata
        local metadata_json, err = safe_redis_call('HGET', metadata_hash, task_id)
        if err then
            table.insert(errors, 'Task ' .. task_id .. ' metadata get: ' .. err)
            -- Continue with other tasks
        elseif metadata_json then
            local metadata, err = safe_decode(metadata_json, 'recover_stuck_tasks metadata ' .. task_id)
            if err then
                table.insert(errors, err)
                -- Continue with other tasks
            else
                local heartbeat_expires_at = tonumber(metadata['heartbeat_expires_at'])
                if not heartbeat_expires_at then
                    table.insert(errors, 'Task ' .. task_id .. ' missing heartbeat_expires_at')
                    -- Continue with other tasks
                elseif current_time >= heartbeat_expires_at then
                    -- Get original task JSON from processing hash (FIX BUG #1)
                    local task_json, err = safe_redis_call('HGET', KEYS[1], task_id)
                    if err then
                        table.insert(errors, 'Task ' .. task_id .. ' get: ' .. err)
                        -- Continue with other tasks
                    elseif task_json then
                        -- Parse and update task with recovery metadata
                        local task, err = safe_decode(task_json, 'recover_stuck_tasks task ' .. task_id)
                        if err then
                            table.insert(errors, err)
                            -- Continue with other tasks
                        else
                            local claimed_at = tonumber(metadata['claimed_at'])
                            if not claimed_at then
                                table.insert(errors, 'Task ' .. task_id .. ' missing claimed_at')
                                claimed_at = current_time
                            end

                            task['recovered_at'] = ARGV[1]
                            task['previous_worker'] = metadata['worker_id']
                            task['stuck_duration_ms'] = current_time - claimed_at
                            task['recovery_reason'] = 'heartbeat_expired'
                            task['worker_id'] = cjson.null  -- Clear worker assignment

                            -- Remove from processing (both hash and metadata)
                            local _, err = safe_redis_call('HDEL', KEYS[1], task_id)
                            if err then
                                table.insert(errors, 'Task ' .. task_id .. ' hdel: ' .. err)
                            end

                            local _, err = safe_redis_call('HDEL', metadata_hash, task_id)
                            if err then
                                table.insert(errors, 'Task ' .. task_id .. ' metadata hdel: ' .. err)
                            end

                            -- Remove heartbeat
                            local _, err = safe_redis_call('HDEL', KEYS[3], task_id)
                            if err then
                                table.insert(errors, 'Task ' .. task_id .. ' heartbeat hdel: ' .. err)
                            end

                            -- Determine queue mode (HYBRID: zset for priority, list for FIFO)
                            local queue_mode = ARGV[3] or 'list'

                            -- Requeue for processing with FULL task data
                            local task_json_updated, err = safe_encode(task, 'recover_stuck_tasks requeue ' .. task_id)
                            if err then
                                table.insert(errors, err)
                            else
                                if queue_mode == 'zset' then
                                    -- Priority queue: ZADD with calculated score
                                    -- Formula: (10 - priority) * 1e13 + timestamp_ms
                                    local priority = tonumber(task['priority']) or 5
                                    local priority_multiplier = tonumber(ARGV[4]) or 1e13
                                    local score = ((10 - priority) * priority_multiplier) + current_time
                                    local _, err = safe_redis_call('ZADD', KEYS[2], score, task_json_updated)
                                    if err then
                                        table.insert(errors, 'Task ' .. task_id .. ' requeue: ' .. err)
                                    else
                                        recovered = recovered + 1
                                    end
                                else
                                    -- FIFO queue: RPUSH
                                    local _, err = safe_redis_call('RPUSH', KEYS[2], task_json_updated)
                                    if err then
                                        table.insert(errors, 'Task ' .. task_id .. ' requeue: ' .. err)
                                    else
                                        recovered = recovered + 1
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end

    -- Return count (even if there were partial errors, report what we recovered)
    -- Errors are logged separately by the caller
    if #errors > 0 and recovered == 0 then
        return 'ERROR: Recovery failed - ' .. table.concat(errors, '; ')
    end

    return tostring(recovered)
end

-- Return script names for registration
return {
    claim_task = claim_task,
    complete_task = complete_task,
    fail_task = fail_task,
    batch_claim_tasks = batch_claim_tasks,
    update_heartbeat = update_heartbeat,
    recover_stuck_tasks = recover_stuck_tasks
}
