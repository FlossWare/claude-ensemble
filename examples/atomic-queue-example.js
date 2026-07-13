/**
 * Example Usage: Redis Atomic Queue Operations
 *
 * Demonstrates how to use atomic operations for safe, race-free queue processing
 */

import { RedisAtomic } from '../shared/redis-atomic-wrapper.js';
import Redis from 'ioredis';

// Connect to Redis
const redis = new Redis({
    host: 'aio-01',
    port: 6379,
    db: 0
});

const atomic = new RedisAtomic(redis);
const queueName = 'scrape_queue';

/**
 * Producer: Enqueue URLs for processing
 */
async function producer() {
    console.log('=== PRODUCER: Enqueuing URLs ===');

    const urls = [
        'https://example.com/page1',
        'https://example.com/page2',
        'https://example.com/page3',
        'https://example.com/page1', // Duplicate
    ];

    // Batch enqueue
    const result = await atomic.batchEnqueue(queueName, urls);
    console.log(`Enqueued: ${result.enqueued}, Duplicates: ${result.duplicates}`);

    // Enqueue with priority
    await atomic.priorityEnqueue(queueName, 'https://example.com/urgent', 'high');
    console.log('Enqueued high-priority URL');

    // Show stats
    const stats = await atomic.stats(queueName);
    console.log('Queue stats:', stats);
}

/**
 * Consumer: Process URLs from queue
 */
async function consumer(workerId) {
    console.log(`=== CONSUMER ${workerId}: Processing URLs ===`);

    while (true) {
        // Dequeue next URL
        const url = await atomic.dequeue(queueName, workerId, 300);

        if (!url) {
            console.log(`${workerId}: Queue empty, exiting`);
            break;
        }

        console.log(`${workerId}: Processing ${url}`);

        try {
            // Simulate processing
            await processUrl(url);

            // Mark as complete
            const result = await atomic.complete(queueName, url, workerId, 'success');

            if (result === 1) {
                console.log(`${workerId}: Completed ${url}`);
            } else {
                console.error(`${workerId}: Failed to complete ${url} (result: ${result})`);
            }
        } catch (err) {
            console.error(`${workerId}: Error processing ${url}:`, err.message);

            // Retry with backoff
            const retryCount = await atomic.retry(queueName, url, workerId, 3);

            if (retryCount === -1) {
                console.error(`${workerId}: ${url} moved to dead letter queue (max retries)`);
            } else if (retryCount === -2) {
                console.error(`${workerId}: Cannot retry ${url} (not owned by this worker)`);
            } else {
                console.log(`${workerId}: Retrying ${url} (attempt ${retryCount})`);
            }
        }
    }
}

/**
 * Simulate URL processing (sometimes fails)
 */
async function processUrl(url) {
    await new Promise(resolve => setTimeout(resolve, 100));

    // Simulate 20% failure rate
    if (Math.random() < 0.2) {
        throw new Error('Simulated processing error');
    }
}

/**
 * Monitor: Reclaim stale jobs periodically
 */
async function monitor() {
    console.log('=== MONITOR: Checking for stale jobs ===');

    setInterval(async () => {
        const reclaimed = await atomic.reclaimStale(queueName, 300);

        if (reclaimed.length > 0) {
            console.log(`MONITOR: Reclaimed ${reclaimed.length} stale jobs:`, reclaimed);
        }

        // Show stats
        const stats = await atomic.stats(queueName);
        console.log('MONITOR: Queue stats:', stats);

        // Check dead letter queue
        if (stats.dead_letter > 0) {
            const deadUrls = await redis.smembers(`${queueName}:dead_letter`);
            console.log('MONITOR: Dead letter queue:', deadUrls);
        }
    }, 10000); // Every 10 seconds
}

/**
 * Main: Run example
 */
async function main() {
    console.log('Starting Redis Atomic Queue Example\n');

    // Start monitor
    monitor();

    // Run producer
    await producer();
    console.log('');

    // Run multiple consumers in parallel
    await Promise.all([
        consumer('worker-1'),
        consumer('worker-2'),
        consumer('worker-3')
    ]);

    console.log('\n=== FINAL STATS ===');
    const stats = await atomic.stats(queueName);
    console.log(stats);

    // Cleanup
    await redis.quit();
    process.exit(0);
}

// Run example
main().catch(err => {
    console.error('Error:', err);
    process.exit(1);
});
