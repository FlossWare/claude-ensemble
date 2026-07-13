-- Redis Atomic Operations for Queue Processing
-- All multi-step operations wrapped in Lua scripts for atomicity
-- KEYS and ARGV are passed from the calling application

--------------------------------------------------------------------------------
-- 1. ATOMIC ENQUEUE WITH DEDUPLICATION
--------------------------------------------------------------------------------
-- Atomically add URL to queue if not already processed or queued
-- KEYS[1] = queue name (list)
-- KEYS[2] = processed set
-- KEYS[3] = queued set
-- ARGV[1] = URL
-- ARGV[2] = timestamp
-- Returns: 1 if enqueued, 0 if duplicate, -1 if already processed

local function atomic_enqueue(queue, processed_set, queued_set, url, timestamp)
    -- Check if already processed
    if redis.call('SISMEMBER', processed_set, url) == 1 then
        return -1
    end

    -- Check if already queued
    if redis.call('SISMEMBER', queued_set, url) == 1 then
        return 0
    end

    -- Add to queue and queued set atomically
    redis.call('RPUSH', queue, url)
    redis.call('SADD', queued_set, url)
    redis.call('HSET', queue .. ':metadata', url, timestamp)

    return 1
end

--------------------------------------------------------------------------------
-- 2. ATOMIC DEQUEUE WITH CLAIM
--------------------------------------------------------------------------------
-- Atomically dequeue URL and mark as in-progress
-- KEYS[1] = queue name (list)
-- KEYS[2] = queued set
-- KEYS[3] = in-progress set
-- ARGV[1] = worker_id
-- ARGV[2] = timestamp
-- ARGV[3] = timeout (seconds)
-- Returns: URL or nil

local function atomic_dequeue(queue, queued_set, in_progress_set, worker_id, timestamp, timeout)
    -- Pop from queue
    local url = redis.call('LPOP', queue)

    if not url then
        return nil
    end

    -- Move from queued to in-progress
    redis.call('SREM', queued_set, url)
    redis.call('SADD', in_progress_set, url)

    -- Set worker claim with TTL (separate key for proper expiration)
    redis.call('SETEX', in_progress_set .. ':claim:' .. url, timeout, worker_id)
    redis.call('HSET', in_progress_set .. ':timestamps', url, timestamp)

    return url
end

--------------------------------------------------------------------------------
-- 3. ATOMIC COMPLETE WITH CLEANUP
--------------------------------------------------------------------------------
-- Atomically mark URL as completed and clean up tracking data
-- KEYS[1] = in-progress set
-- KEYS[2] = processed set
-- KEYS[3] = queue name (for metadata cleanup)
-- ARGV[1] = URL
-- ARGV[2] = worker_id
-- ARGV[3] = timestamp
-- ARGV[4] = result (success/failure)
-- Returns: 1 if completed, 0 if not claimed by this worker, -1 if not in progress

local function atomic_complete(in_progress_set, processed_set, queue, url, worker_id, timestamp, result)
    -- Verify URL is in progress
    if redis.call('SISMEMBER', in_progress_set, url) == 0 then
        return -1
    end

    -- Verify worker owns the claim
    local claimed_by = redis.call('GET', in_progress_set .. ':claim:' .. url)
    if claimed_by ~= worker_id then
        return 0
    end

    -- Move from in-progress to processed
    redis.call('SREM', in_progress_set, url)
    redis.call('SADD', processed_set, url)

    -- Clean up claim data (separate key with TTL)
    redis.call('DEL', in_progress_set .. ':claim:' .. url)
    redis.call('HDEL', in_progress_set .. ':timestamps', url)

    -- Store completion metadata
    redis.call('HSET', processed_set .. ':results', url, result)
    redis.call('HSET', processed_set .. ':timestamps', url, timestamp)
    redis.call('HSET', processed_set .. ':workers', url, worker_id)

    -- Clean up queue metadata
    redis.call('HDEL', queue .. ':metadata', url)

    return 1
end

--------------------------------------------------------------------------------
-- 4. ATOMIC RETRY WITH BACKOFF
--------------------------------------------------------------------------------
-- Atomically move failed URL back to queue with retry tracking
-- KEYS[1] = in-progress set
-- KEYS[2] = queue name (list)
-- KEYS[3] = queued set
-- KEYS[4] = retry counter hash
-- ARGV[1] = URL
-- ARGV[2] = worker_id
-- ARGV[3] = max_retries
-- ARGV[4] = timestamp
-- Returns: retry_count if requeued, -1 if max retries exceeded, -2 if not claimed by worker

local function atomic_retry(in_progress_set, queue, queued_set, retry_counter, url, worker_id, max_retries, timestamp)
    -- Verify worker owns the claim
    local claimed_by = redis.call('GET', in_progress_set .. ':claim:' .. url)
    if claimed_by ~= worker_id then
        return -2
    end

    -- Increment retry counter
    local retry_count = redis.call('HINCRBY', retry_counter, url, 1)

    -- Check max retries
    if retry_count > tonumber(max_retries) then
        -- Move to dead letter queue
        redis.call('SREM', in_progress_set, url)
        redis.call('SADD', queue .. ':dead_letter', url)
        redis.call('HSET', queue .. ':dead_letter:reasons', url, 'max_retries_exceeded')
        redis.call('HSET', queue .. ':dead_letter:timestamps', url, timestamp)

        -- Clean up
        redis.call('DEL', in_progress_set .. ':claim:' .. url)
        redis.call('HDEL', in_progress_set .. ':timestamps', url)

        return -1
    end

    -- Re-queue with exponential backoff priority
    local priority = retry_count * retry_count -- Exponential backoff
    redis.call('SREM', in_progress_set, url)
    redis.call('RPUSH', queue, url)
    redis.call('SADD', queued_set, url)
    redis.call('HSET', queue .. ':retry_priority', url, priority)
    redis.call('HSET', queue .. ':retry_timestamp', url, timestamp)

    -- Clean up claim
    redis.call('DEL', in_progress_set .. ':claim:' .. url)
    redis.call('HDEL', in_progress_set .. ':timestamps', url)

    return retry_count
end

--------------------------------------------------------------------------------
-- 5. ATOMIC RECLAIM STALE JOBS
--------------------------------------------------------------------------------
-- Atomically reclaim jobs that have been in-progress too long
-- KEYS[1] = in-progress set
-- KEYS[2] = queue name (list)
-- KEYS[3] = queued set
-- ARGV[1] = current_timestamp
-- ARGV[2] = timeout (seconds)
-- Returns: table of reclaimed URLs

local function atomic_reclaim_stale(in_progress_set, queue, queued_set, current_timestamp, timeout)
    local reclaimed = {}
    local threshold = tonumber(current_timestamp) - tonumber(timeout)

    -- Get all in-progress URLs
    local urls = redis.call('SMEMBERS', in_progress_set)

    for _, url in ipairs(urls) do
        local claim_timestamp = redis.call('HGET', in_progress_set .. ':timestamps', url)

        if claim_timestamp and tonumber(claim_timestamp) < threshold then
            -- Stale job found - reclaim it
            redis.call('SREM', in_progress_set, url)
            redis.call('RPUSH', queue, url)
            redis.call('SADD', queued_set, url)

            -- Clean up stale claim (separate key with TTL)
            redis.call('DEL', in_progress_set .. ':claim:' .. url)
            redis.call('HDEL', in_progress_set .. ':timestamps', url)

            -- Mark as reclaimed
            redis.call('HINCRBY', queue .. ':reclaim_count', url, 1)

            table.insert(reclaimed, url)
        end
    end

    return reclaimed
end

--------------------------------------------------------------------------------
-- 6. ATOMIC BATCH ENQUEUE
--------------------------------------------------------------------------------
-- Atomically enqueue multiple URLs with deduplication
-- KEYS[1] = queue name (list)
-- KEYS[2] = processed set
-- KEYS[3] = queued set
-- ARGV[1] = JSON array of URLs
-- ARGV[2] = timestamp
-- Returns: table with counts {enqueued, duplicates, already_processed}

local function atomic_batch_enqueue(queue, processed_set, queued_set, urls_json, timestamp)
    local cjson = require('cjson')
    local urls = cjson.decode(urls_json)

    local enqueued = 0
    local duplicates = 0
    local already_processed = 0

    for _, url in ipairs(urls) do
        -- Check if already processed
        if redis.call('SISMEMBER', processed_set, url) == 1 then
            already_processed = already_processed + 1
        -- Check if already queued
        elseif redis.call('SISMEMBER', queued_set, url) == 1 then
            duplicates = duplicates + 1
        else
            -- Add to queue and queued set atomically
            redis.call('RPUSH', queue, url)
            redis.call('SADD', queued_set, url)
            redis.call('HSET', queue .. ':metadata', url, timestamp)
            enqueued = enqueued + 1
        end
    end

    return {enqueued, duplicates, already_processed}
end

--------------------------------------------------------------------------------
-- 7. ATOMIC QUEUE STATS
--------------------------------------------------------------------------------
-- Atomically gather queue statistics
-- KEYS[1] = queue name (list)
-- KEYS[2] = processed set
-- KEYS[3] = queued set
-- KEYS[4] = in-progress set
-- Returns: table with stats {pending, processed, queued, in_progress, dead_letter}

local function atomic_queue_stats(queue, processed_set, queued_set, in_progress_set)
    local pending = redis.call('LLEN', queue)
    local processed = redis.call('SCARD', processed_set)
    local queued = redis.call('SCARD', queued_set)
    local in_progress = redis.call('SCARD', in_progress_set)
    local dead_letter = redis.call('SCARD', queue .. ':dead_letter')

    return {pending, processed, queued, in_progress, dead_letter}
end

--------------------------------------------------------------------------------
-- 8. ATOMIC PRIORITY ENQUEUE
--------------------------------------------------------------------------------
-- Atomically enqueue with priority (LPUSH for high priority, RPUSH for normal)
-- KEYS[1] = queue name (list)
-- KEYS[2] = processed set
-- KEYS[3] = queued set
-- ARGV[1] = URL
-- ARGV[2] = timestamp
-- ARGV[3] = priority (high/normal)
-- Returns: 1 if enqueued, 0 if duplicate, -1 if already processed

local function atomic_priority_enqueue(queue, processed_set, queued_set, url, timestamp, priority)
    -- Check if already processed
    if redis.call('SISMEMBER', processed_set, url) == 1 then
        return -1
    end

    -- Check if already queued
    if redis.call('SISMEMBER', queued_set, url) == 1 then
        return 0
    end

    -- Add to queue based on priority
    if priority == 'high' then
        redis.call('LPUSH', queue, url)  -- Front of queue
    else
        redis.call('RPUSH', queue, url)  -- Back of queue
    end

    redis.call('SADD', queued_set, url)
    redis.call('HSET', queue .. ':metadata', url, timestamp)
    redis.call('HSET', queue .. ':priority', url, priority)

    return 1
end

--------------------------------------------------------------------------------
-- EXPORT FUNCTIONS (for documentation - actual use via EVAL)
--------------------------------------------------------------------------------
-- These functions are called via redis.eval() from application code
-- Each function signature is documented above
