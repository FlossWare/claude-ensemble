/**
 * Model Cache - Persistent in-memory cache for model predictions
 *
 * Provides TTL-based caching for model predictions with stats tracking.
 * Separate from Python model caching (which caches loaded model objects).
 * This caches prediction results for identical inputs.
 *
 * Usage:
 *   const cache = require('./model-cache.cjs');
 *
 *   // Get cached result
 *   const result = cache.get('model_name:{"feature1":1}');
 *
 *   // Store result (30 min default TTL)
 *   cache.set('model_name:{"feature1":1}', { prediction: 0.85 });
 *
 *   // Custom TTL (10 minutes)
 *   cache.set('key', result, 10 * 60 * 1000);
 *
 *   // Clear all cache
 *   cache.clear();
 *
 *   // Get statistics
 *   const stats = cache.getStats();
 */

const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes default

class ModelCache {
  constructor() {
    this.cache = new Map();
    this.stats = {
      hits: 0,
      misses: 0,
      stores: 0,
      evictions: 0
    };
    this.maxSize = 10000; // Prevent unbounded growth

    // Periodic cleanup of expired entries (every 5 minutes)
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 5 * 60 * 1000);
  }

  /**
   * Get cached value
   * @param {string} key - Cache key
   * @returns {any|null} Cached value or null if not found/expired
   */
  get(key) {
    const entry = this.cache.get(key);

    if (!entry) {
      this.stats.misses++;
      return null;
    }

    // Check expiration
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      this.stats.misses++;
      this.stats.evictions++;
      return null;
    }

    this.stats.hits++;
    entry.lastAccessed = Date.now();
    return entry.value;
  }

  /**
   * Store value in cache
   * @param {string} key - Cache key
   * @param {any} value - Value to cache
   * @param {number} ttl - Time to live in milliseconds (default: 30 min)
   */
  set(key, value, ttl = CACHE_TTL_MS) {
    // Enforce max size using LRU eviction
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      this.evictLRU();
    }

    this.cache.set(key, {
      value,
      expiresAt: Date.now() + ttl,
      createdAt: Date.now(),
      lastAccessed: Date.now()
    });

    this.stats.stores++;
  }

  /**
   * Clear all cache entries
   */
  clear() {
    const size = this.cache.size;
    this.cache.clear();
    this.stats.evictions += size;
  }

  /**
   * Delete specific key
   * @param {string} key - Cache key
   * @returns {boolean} True if key existed
   */
  delete(key) {
    const existed = this.cache.has(key);
    if (existed) {
      this.cache.delete(key);
      this.stats.evictions++;
    }
    return existed;
  }

  /**
   * Check if key exists and is not expired
   * @param {string} key - Cache key
   * @returns {boolean}
   */
  has(key) {
    const entry = this.cache.get(key);
    if (!entry) return false;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      this.stats.evictions++;
      return false;
    }

    return true;
  }

  /**
   * Get cache statistics
   * @returns {Object} Statistics object
   */
  getStats() {
    const now = Date.now();
    let expiredCount = 0;

    // Count expired entries without removing them
    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiresAt) {
        expiredCount++;
      }
    }

    const hitRate = this.stats.hits + this.stats.misses > 0
      ? (this.stats.hits / (this.stats.hits + this.stats.misses) * 100).toFixed(2)
      : 0;

    return {
      size: this.cache.size,
      active: this.cache.size - expiredCount,
      expired: expiredCount,
      hits: this.stats.hits,
      misses: this.stats.misses,
      stores: this.stats.stores,
      evictions: this.stats.evictions,
      hitRate: parseFloat(hitRate),
      maxSize: this.maxSize,
      memoryEstimate: this.estimateMemory()
    };
  }

  /**
   * Reset statistics counters
   */
  resetStats() {
    this.stats = {
      hits: 0,
      misses: 0,
      stores: 0,
      evictions: 0
    };
  }

  /**
   * Remove expired entries
   * @returns {number} Number of entries removed
   */
  cleanup() {
    const now = Date.now();
    let removed = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiresAt) {
        this.cache.delete(key);
        removed++;
        this.stats.evictions++;
      }
    }

    return removed;
  }

  /**
   * Evict least recently used entry
   */
  evictLRU() {
    let oldestKey = null;
    let oldestTime = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccessed < oldestTime) {
        oldestTime = entry.lastAccessed;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.cache.delete(oldestKey);
      this.stats.evictions++;
    }
  }

  /**
   * Estimate memory usage (rough approximation)
   * @returns {string} Memory estimate in human-readable format
   */
  estimateMemory() {
    const entries = [...this.cache.entries()];
    const jsonSize = JSON.stringify(entries).length;

    if (jsonSize < 1024) {
      return `${jsonSize} B`;
    } else if (jsonSize < 1024 * 1024) {
      return `${(jsonSize / 1024).toFixed(2)} KB`;
    } else {
      return `${(jsonSize / (1024 * 1024)).toFixed(2)} MB`;
    }
  }

  /**
   * Get all keys (useful for debugging)
   * @returns {Array<string>}
   */
  keys() {
    return [...this.cache.keys()];
  }

  /**
   * Get cache size
   * @returns {number}
   */
  size() {
    return this.cache.size;
  }

  /**
   * Destroy cache and cleanup interval
   */
  destroy() {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.clear();
  }
}

// Export singleton instance
const instance = new ModelCache();

// Graceful shutdown
process.on('SIGINT', () => {
  instance.destroy();
});

process.on('SIGTERM', () => {
  instance.destroy();
});

module.exports = instance;
