/**
 * Redis Atomic Operations Wrapper
 *
 * Loads and executes Lua scripts for atomic multi-step operations.
 * All operations are transactional and race-condition free.
 *
 * Usage:
 *   const { RedisAtomic } = require('./redis-atomic-wrapper.js');
 *   const atomic = new RedisAtomic(redisClient);
 *
 *   const result = await atomic.enqueue('scrape_queue', 'https://example.com');
 */

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class RedisAtomic {
    constructor(redisClient) {
        this.redis = redisClient;
        this.scripts = {};
        this.scriptSHAs = {};
        this.luaPath = path.join(__dirname, 'redis-atomic-operations.lua');

        // Load all Lua functions on initialization
        this._loadScripts();
    }

    /**
     * Load Lua scripts from file and prepare for execution
     * @private
     */
    _loadScripts() {
        const luaContent = fs.readFileSync(this.luaPath, 'utf8');

        // Define individual script functions
        // Each function is extracted from the main Lua file

        this.scripts.enqueue = `
            ${this._extractFunction(luaContent, 'atomic_enqueue')}
            return atomic_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        `;

        this.scripts.dequeue = `
            ${this._extractFunction(luaContent, 'atomic_dequeue')}
            return atomic_dequeue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3])
        `;

        this.scripts.complete = `
            ${this._extractFunction(luaContent, 'atomic_complete')}
            return atomic_complete(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
        `;

        this.scripts.retry = `
            ${this._extractFunction(luaContent, 'atomic_retry')}
            return atomic_retry(KEYS[1], KEYS[2], KEYS[3], KEYS[4], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
        `;

        this.scripts.reclaimStale = `
            ${this._extractFunction(luaContent, 'atomic_reclaim_stale')}
            return atomic_reclaim_stale(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        `;

        this.scripts.batchEnqueue = `
            ${this._extractFunction(luaContent, 'atomic_batch_enqueue')}
            return atomic_batch_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2])
        `;

        this.scripts.stats = `
            ${this._extractFunction(luaContent, 'atomic_queue_stats')}
            return atomic_queue_stats(KEYS[1], KEYS[2], KEYS[3], KEYS[4])
        `;

        this.scripts.priorityEnqueue = `
            ${this._extractFunction(luaContent, 'atomic_priority_enqueue')}
            return atomic_priority_enqueue(KEYS[1], KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3])
        `;
    }

    /**
     * Extract a function definition from Lua content
     * @private
     */
    _extractFunction(content, functionName) {
        const startPattern = new RegExp(`local function ${functionName}\\(`);
        const start = content.search(startPattern);

        if (start === -1) {
            throw new Error(`Function ${functionName} not found in Lua file`);
        }

        // Find matching 'end' by counting nested function/end pairs
        let depth = 0;
        let inFunction = false;
        let end = start;

        for (let i = start; i < content.length; i++) {
            const remaining = content.slice(i);

            if (remaining.startsWith('function')) {
                depth++;
                inFunction = true;
            } else if (remaining.startsWith('end')) {
                if (inFunction) {
                    depth--;
                    if (depth === 0) {
                        end = i + 3; // Include 'end'
                        break;
                    }
                }
            }
        }

        return content.slice(start, end);
    }

    /**
     * Execute Lua script with EVALSHA (with fallback to EVAL)
     * @private
     */
    async _evalScript(scriptName, keys, args) {
        const script = this.scripts[scriptName];

        if (!script) {
            throw new Error(`Script ${scriptName} not found`);
        }

        // Generate SHA1 hash of script
        const sha = crypto.createHash('sha1').update(script).digest('hex');

        try {
            // Try EVALSHA first (faster if script cached on Redis)
            return await this.redis.evalsha(sha, keys.length, ...keys, ...args);
        } catch (err) {
            if (err.message.includes('NOSCRIPT')) {
                // Script not cached, use EVAL
                return await this.redis.eval(script, keys.length, ...keys, ...args);
            }
            throw err;
        }
    }

    /**
     * Atomically enqueue a URL with deduplication
     *
     * @param {string} queueName - Name of the queue
     * @param {string} url - URL to enqueue
     * @param {string} [timestamp] - Optional timestamp (defaults to Date.now())
     * @returns {Promise<number>} 1 if enqueued, 0 if duplicate, -1 if already processed
     */
    async enqueue(queueName, url, timestamp = Date.now().toString()) {
        const keys = [
            queueName,
            `${queueName}:processed`,
            `${queueName}:queued`
        ];
        const args = [url, timestamp];

        return await this._evalScript('enqueue', keys, args);
    }

    /**
     * Atomically dequeue a URL and claim it for processing
     *
     * @param {string} queueName - Name of the queue
     * @param {string} workerId - Identifier for the worker claiming this job
     * @param {number} [timeout=300] - Timeout in seconds before job is considered stale
     * @returns {Promise<string|null>} URL to process, or null if queue empty
     */
    async dequeue(queueName, workerId, timeout = 300) {
        const keys = [
            queueName,
            `${queueName}:queued`,
            `${queueName}:in_progress`
        ];
        const args = [workerId, Date.now().toString(), timeout.toString()];

        return await this._evalScript('dequeue', keys, args);
    }

    /**
     * Atomically mark a job as completed
     *
     * @param {string} queueName - Name of the queue
     * @param {string} url - URL that was processed
     * @param {string} workerId - Worker that processed this job
     * @param {string} result - Result status (success/failure)
     * @returns {Promise<number>} 1 if completed, 0 if not owned by worker, -1 if not in progress
     */
    async complete(queueName, url, workerId, result = 'success') {
        const keys = [
            `${queueName}:in_progress`,
            `${queueName}:processed`,
            queueName
        ];
        const args = [url, workerId, Date.now().toString(), result];

        return await this._evalScript('complete', keys, args);
    }

    /**
     * Atomically retry a failed job with backoff
     *
     * @param {string} queueName - Name of the queue
     * @param {string} url - URL to retry
     * @param {string} workerId - Worker that failed this job
     * @param {number} [maxRetries=3] - Maximum retry attempts
     * @returns {Promise<number>} Retry count if requeued, -1 if max retries exceeded, -2 if not owned by worker
     */
    async retry(queueName, url, workerId, maxRetries = 3) {
        const keys = [
            `${queueName}:in_progress`,
            queueName,
            `${queueName}:queued`,
            `${queueName}:retry_count`
        ];
        const args = [url, workerId, maxRetries.toString(), Date.now().toString()];

        return await this._evalScript('retry', keys, args);
    }

    /**
     * Atomically reclaim stale jobs that have timed out
     *
     * @param {string} queueName - Name of the queue
     * @param {number} [timeout=300] - Timeout in seconds
     * @returns {Promise<string[]>} Array of reclaimed URLs
     */
    async reclaimStale(queueName, timeout = 300) {
        const keys = [
            `${queueName}:in_progress`,
            queueName,
            `${queueName}:queued`
        ];
        const args = [Date.now().toString(), timeout.toString()];

        return await this._evalScript('reclaimStale', keys, args);
    }

    /**
     * Atomically enqueue multiple URLs in a batch
     *
     * @param {string} queueName - Name of the queue
     * @param {string[]} urls - Array of URLs to enqueue
     * @returns {Promise<{enqueued: number, duplicates: number, already_processed: number}>}
     */
    async batchEnqueue(queueName, urls) {
        const keys = [
            queueName,
            `${queueName}:processed`,
            `${queueName}:queued`
        ];
        const args = [JSON.stringify(urls), Date.now().toString()];

        const [enqueued, duplicates, already_processed] = await this._evalScript('batchEnqueue', keys, args);

        return { enqueued, duplicates, already_processed };
    }

    /**
     * Atomically get queue statistics
     *
     * @param {string} queueName - Name of the queue
     * @returns {Promise<{pending: number, processed: number, queued: number, in_progress: number, dead_letter: number}>}
     */
    async stats(queueName) {
        const keys = [
            queueName,
            `${queueName}:processed`,
            `${queueName}:queued`,
            `${queueName}:in_progress`
        ];
        const args = [];

        const [pending, processed, queued, in_progress, dead_letter] = await this._evalScript('stats', keys, args);

        return { pending, processed, queued, in_progress, dead_letter };
    }

    /**
     * Atomically enqueue a URL with priority
     *
     * @param {string} queueName - Name of the queue
     * @param {string} url - URL to enqueue
     * @param {string} [priority='normal'] - Priority level (high/normal)
     * @returns {Promise<number>} 1 if enqueued, 0 if duplicate, -1 if already processed
     */
    async priorityEnqueue(queueName, url, priority = 'normal') {
        const keys = [
            queueName,
            `${queueName}:processed`,
            `${queueName}:queued`
        ];
        const args = [url, Date.now().toString(), priority];

        return await this._evalScript('priorityEnqueue', keys, args);
    }
}

export { RedisAtomic };
