/**
 * Test Suite for Redis Atomic Operations
 *
 * Tests all atomic operations for correctness, race conditions, and edge cases.
 *
 * Usage:
 *   npm test -- tests/redis-atomic-operations.test.js
 */

import { describe, it, beforeEach, after } from 'node:test';
import assert from 'node:assert';
import { RedisAtomic } from '../shared/redis-atomic-wrapper.js';
import Redis from 'ioredis';

const redis = new Redis({
    host: 'aio-01',
    port: 6379,
    db: 15 // Use separate DB for testing
});

const atomic = new RedisAtomic(redis);
const testQueue = 'test_queue_' + Date.now();

after(async () => {
    // Clean up test data
    const keys = await redis.keys(`${testQueue}*`);
    if (keys.length > 0) {
        await redis.del(...keys);
    }
    await redis.quit();
});

describe('Redis Atomic Operations', async () => {
    beforeEach(async () => {
        // Clear test queue before each test
        const keys = await redis.keys(`${testQueue}*`);
        if (keys.length > 0) {
            await redis.del(...keys);
        }
    });

    await describe('Atomic Enqueue', async () => {
        await it('should enqueue a new URL', async () => {
            const result = await atomic.enqueue(testQueue, 'https://example.com');
            assert.strictEqual(result, 1);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 1);
            assert.strictEqual(stats.queued, 1);
        });

        await it('should reject duplicate URLs', async () => {
            await atomic.enqueue(testQueue, 'https://example.com');
            const result = await atomic.enqueue(testQueue, 'https://example.com');

            assert.strictEqual(result, 0); // Duplicate

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 1); // Still only 1
        });

        await it('should reject already processed URLs', async () => {
            const url = 'https://example.com';

            // Enqueue, dequeue, and complete
            await atomic.enqueue(testQueue, url);
            await atomic.dequeue(testQueue, 'worker-1');
            await atomic.complete(testQueue, url, 'worker-1', 'success');

            // Try to enqueue again
            const result = await atomic.enqueue(testQueue, url);

            assert.strictEqual(result, -1); // Already processed

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.processed, 1);
            assert.strictEqual(stats.pending, 0);
        });
    });

    await describe('Atomic Dequeue', async () => {
        await it('should dequeue URLs in FIFO order', async () => {
            await atomic.enqueue(testQueue, 'https://example.com/1');
            await atomic.enqueue(testQueue, 'https://example.com/2');
            await atomic.enqueue(testQueue, 'https://example.com/3');

            const url1 = await atomic.dequeue(testQueue, 'worker-1');
            const url2 = await atomic.dequeue(testQueue, 'worker-1');
            const url3 = await atomic.dequeue(testQueue, 'worker-1');

            assert.strictEqual(url1, 'https://example.com/1');
            assert.strictEqual(url2, 'https://example.com/2');
            assert.strictEqual(url3, 'https://example.com/3');

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.in_progress, 3);
            assert.strictEqual(stats.pending, 0);
        });

        await it('should return null when queue is empty', async () => {
            const url = await atomic.dequeue(testQueue, 'worker-1');
            assert.strictEqual(url, null);
        });

        await it('should claim URLs for specific workers', async () => {
            await atomic.enqueue(testQueue, 'https://example.com');
            const url = await atomic.dequeue(testQueue, 'worker-1');

            // Verify claim
            const claim = await redis.hget(`${testQueue}:in_progress:claims`, url);
            assert.strictEqual(claim, 'worker-1');
        });
    });

    await describe('Atomic Complete', async () => {
        await it('should complete a job successfully', async () => {
            const url = 'https://example.com';
            await atomic.enqueue(testQueue, url);
            await atomic.dequeue(testQueue, 'worker-1');

            const result = await atomic.complete(testQueue, url, 'worker-1', 'success');
            assert.strictEqual(result, 1);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.processed, 1);
            assert.strictEqual(stats.in_progress, 0);
        });

        await it('should reject completion by wrong worker', async () => {
            const url = 'https://example.com';
            await atomic.enqueue(testQueue, url);
            await atomic.dequeue(testQueue, 'worker-1');

            const result = await atomic.complete(testQueue, url, 'worker-2', 'success');
            assert.strictEqual(result, 0); // Not owned by worker-2

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.in_progress, 1); // Still in progress
        });

        await it('should clean up claim data after completion', async () => {
            const url = 'https://example.com';
            await atomic.enqueue(testQueue, url);
            await atomic.dequeue(testQueue, 'worker-1');
            await atomic.complete(testQueue, url, 'worker-1', 'success');

            // Verify claim data removed
            const claim = await redis.hget(`${testQueue}:in_progress:claims`, url);
            assert.strictEqual(claim, null);

            const timestamp = await redis.hget(`${testQueue}:in_progress:timestamps`, url);
            assert.strictEqual(timestamp, null);
        });
    });

    await describe('Atomic Retry', async () => {
        await it('should retry a failed job', async () => {
            const url = 'https://example.com';
            await atomic.enqueue(testQueue, url);
            await atomic.dequeue(testQueue, 'worker-1');

            const retryCount = await atomic.retry(testQueue, url, 'worker-1', 3);
            assert.strictEqual(retryCount, 1);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 1); // Back in queue
            assert.strictEqual(stats.in_progress, 0);
        });

        await it('should move to dead letter queue after max retries', async () => {
            const url = 'https://example.com';
            await atomic.enqueue(testQueue, url);

            // Attempt 3 retries
            for (let i = 0; i < 3; i++) {
                await atomic.dequeue(testQueue, 'worker-1');
                await atomic.retry(testQueue, url, 'worker-1', 3);
            }

            // 4th retry should fail
            await atomic.dequeue(testQueue, 'worker-1');
            const retryCount = await atomic.retry(testQueue, url, 'worker-1', 3);
            assert.strictEqual(retryCount, -1); // Max retries exceeded

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.dead_letter, 1);
            assert.strictEqual(stats.in_progress, 0);
        });
    });

    await describe('Atomic Batch Enqueue', async () => {
        await it('should enqueue multiple URLs', async () => {
            const urls = [
                'https://example.com/1',
                'https://example.com/2',
                'https://example.com/3'
            ];

            const result = await atomic.batchEnqueue(testQueue, urls);
            assert.strictEqual(result.enqueued, 3);
            assert.strictEqual(result.duplicates, 0);
            assert.strictEqual(result.already_processed, 0);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 3);
        });

        await it('should handle duplicates in batch', async () => {
            const urls = [
                'https://example.com/1',
                'https://example.com/1', // Duplicate
                'https://example.com/2'
            ];

            const result = await atomic.batchEnqueue(testQueue, urls);
            assert.strictEqual(result.enqueued, 2);
            assert.strictEqual(result.duplicates, 1);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 2);
        });
    });

    await describe('Atomic Priority Enqueue', async () => {
        await it('should enqueue high priority URLs at front', async () => {
            await atomic.enqueue(testQueue, 'https://example.com/normal1');
            await atomic.priorityEnqueue(testQueue, 'https://example.com/high1', 'high');
            await atomic.enqueue(testQueue, 'https://example.com/normal2');

            const url1 = await atomic.dequeue(testQueue, 'worker-1');
            assert.strictEqual(url1, 'https://example.com/high1'); // High priority first
        });
    });

    await describe('Race Condition Tests', async () => {
        await it('should handle concurrent enqueues', async () => {
            const url = 'https://example.com';

            // Simulate 10 workers trying to enqueue same URL
            const promises = Array(10).fill(null).map(() =>
                atomic.enqueue(testQueue, url)
            );

            const results = await Promise.all(promises);

            // Only 1 should succeed
            const successes = results.filter(r => r === 1).length;
            const duplicates = results.filter(r => r === 0).length;

            assert.strictEqual(successes, 1);
            assert.strictEqual(duplicates, 9);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.pending, 1);
        });

        await it('should handle concurrent dequeues', async () => {
            // Enqueue 5 URLs
            for (let i = 1; i <= 5; i++) {
                await atomic.enqueue(testQueue, `https://example.com/${i}`);
            }

            // Simulate 10 workers trying to dequeue
            const promises = Array(10).fill(null).map((_, i) =>
                atomic.dequeue(testQueue, `worker-${i}`)
            );

            const results = await Promise.all(promises);

            // Only 5 should get URLs
            const urls = results.filter(r => r !== null);
            const nulls = results.filter(r => r === null);

            assert.strictEqual(urls.length, 5);
            assert.strictEqual(nulls.length, 5);

            const stats = await atomic.stats(testQueue);
            assert.strictEqual(stats.in_progress, 5);
            assert.strictEqual(stats.pending, 0);
        });
    });
});
