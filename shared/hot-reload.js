/**
 * Hot-Reload System
 *
 * Dynamic import system with cache busting for live code updates.
 * Enables picking up code changes, learning updates, and discovered patterns
 * without restarting daemons or workflows.
 *
 * Features:
 * - Cache-busted imports for code changes
 * - TTL-based caching for performance
 * - Support for JSON data files (discoveries, learnings)
 * - Automatic retry on import failures
 * - Debug logging for troubleshooting
 *
 * Usage:
 *   import { hotImport, hotImportJSON, clearCache } from './hot-reload.js';
 *
 *   // Import code module with hot-reload
 *   const orchestrator = await hotImport('./orchestrator.js');
 *   const model = await orchestrator.selectModel('code-review');
 *
 *   // Import JSON data with hot-reload
 *   const discoveries = await hotImportJSON('./learning/discoveries.json');
 *
 *   // Clear cache for specific module
 *   clearCache('./orchestrator.js');
 *
 *   // Force reload all cached modules
 *   clearCache();
 */

import { readFileSync, existsSync } from 'fs';
import { pathToFileURL } from 'url';
import { resolve } from 'path';

// ============================================================================
// CONSTANTS
// ============================================================================

const DEFAULT_TTL_MS = 5000; // 5s cache TTL for learning updates
const CODE_TTL_MS = 1000;    // 1s cache TTL for code changes
const JSON_TTL_MS = 5000;    // 5s cache TTL for JSON data

// ============================================================================
// CACHE MANAGEMENT
// ============================================================================

const _cache = new Map();

/**
 * Cache entry structure:
 * {
 *   module: <imported module>,
 *   timestamp: <Date.now()>,
 *   ttl: <ms>,
 *   path: <absolute path>,
 *   type: 'code' | 'json',
 * }
 */

/**
 * Check if cache entry is still valid
 */
function _isCacheValid(entry) {
  if (!entry) return false;
  const age = Date.now() - entry.timestamp;
  return age < entry.ttl;
}

/**
 * Clear cache for a specific module or all modules
 *
 * @param {string} [modulePath] - Path to module, or undefined to clear all
 */
export function clearCache(modulePath) {
  if (modulePath) {
    const absPath = resolve(modulePath);
    _cache.delete(absPath);
    if (process.env.HOT_RELOAD_DEBUG) {
      console.log(`[hot-reload] Cleared cache: ${absPath}`);
    }
  } else {
    const count = _cache.size;
    _cache.clear();
    if (process.env.HOT_RELOAD_DEBUG) {
      console.log(`[hot-reload] Cleared all cache (${count} entries)`);
    }
  }
}

/**
 * Get cache statistics
 *
 * @returns {object} Cache stats
 */
export function getCacheStats() {
  const stats = {
    total: _cache.size,
    valid: 0,
    expired: 0,
    byType: { code: 0, json: 0 },
  };

  for (const entry of _cache.values()) {
    if (_isCacheValid(entry)) {
      stats.valid++;
    } else {
      stats.expired++;
    }
    stats.byType[entry.type] = (stats.byType[entry.type] || 0) + 1;
  }

  return stats;
}

// ============================================================================
// HOT IMPORT - CODE MODULES
// ============================================================================

/**
 * Import a module with cache busting for hot-reload
 *
 * @param {string} modulePath - Path to module (relative or absolute)
 * @param {object} options - Import options
 * @param {number} options.ttl - Cache TTL in milliseconds (default: 1000ms)
 * @param {boolean} options.force - Force reload even if cached (default: false)
 * @param {number} options.retries - Number of retries on failure (default: 2)
 * @returns {Promise<object>} Imported module
 */
export async function hotImport(modulePath, options = {}) {
  const {
    ttl = CODE_TTL_MS,
    force = false,
    retries = 2,
  } = options;

  const absPath = resolve(modulePath);

  // Check cache first (unless force reload)
  if (!force) {
    const cached = _cache.get(absPath);
    if (cached && _isCacheValid(cached)) {
      if (process.env.HOT_RELOAD_DEBUG) {
        console.log(`[hot-reload] Cache hit: ${absPath}`);
      }
      return cached.module;
    }
  }

  // Import with cache busting
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Use timestamp query parameter to bust Node.js module cache
      const cacheBuster = `?t=${Date.now()}_${attempt}`;
      const fileUrl = pathToFileURL(absPath).href + cacheBuster;

      const module = await import(fileUrl);

      // Cache the imported module
      _cache.set(absPath, {
        module,
        timestamp: Date.now(),
        ttl,
        path: absPath,
        type: 'code',
      });

      if (process.env.HOT_RELOAD_DEBUG) {
        console.log(`[hot-reload] Imported (attempt ${attempt + 1}): ${absPath}`);
      }

      return module;
    } catch (err) {
      lastError = err;
      if (process.env.HOT_RELOAD_DEBUG) {
        console.warn(`[hot-reload] Import failed (attempt ${attempt + 1}): ${err.message}`);
      }

      // Wait before retry (exponential backoff)
      if (attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, 100 * Math.pow(2, attempt)));
      }
    }
  }

  // All retries failed
  throw new Error(`Failed to import ${modulePath} after ${retries + 1} attempts: ${lastError.message}`);
}

// ============================================================================
// HOT IMPORT - JSON DATA
// ============================================================================

/**
 * Import a JSON file with hot-reload
 *
 * @param {string} jsonPath - Path to JSON file (relative or absolute)
 * @param {object} options - Import options
 * @param {number} options.ttl - Cache TTL in milliseconds (default: 5000ms)
 * @param {boolean} options.force - Force reload even if cached (default: false)
 * @param {object} options.defaultValue - Default value if file doesn't exist (default: null)
 * @returns {Promise<object>} Parsed JSON data
 */
export async function hotImportJSON(jsonPath, options = {}) {
  const {
    ttl = JSON_TTL_MS,
    force = false,
    defaultValue = null,
  } = options;

  const absPath = resolve(jsonPath);

  // Check cache first (unless force reload)
  if (!force) {
    const cached = _cache.get(absPath);
    if (cached && _isCacheValid(cached)) {
      if (process.env.HOT_RELOAD_DEBUG) {
        console.log(`[hot-reload] JSON cache hit: ${absPath}`);
      }
      return cached.module;
    }
  }

  // Check if file exists
  if (!existsSync(absPath)) {
    if (process.env.HOT_RELOAD_DEBUG) {
      console.log(`[hot-reload] JSON file not found: ${absPath}`);
    }
    return defaultValue;
  }

  try {
    // Read and parse JSON
    const content = readFileSync(absPath, 'utf-8');
    const data = JSON.parse(content);

    // Cache the parsed data
    _cache.set(absPath, {
      module: data,
      timestamp: Date.now(),
      ttl,
      path: absPath,
      type: 'json',
    });

    if (process.env.HOT_RELOAD_DEBUG) {
      console.log(`[hot-reload] Loaded JSON: ${absPath}`);
    }

    return data;
  } catch (err) {
    if (process.env.HOT_RELOAD_DEBUG) {
      console.error(`[hot-reload] JSON parse error: ${err.message}`);
    }
    throw new Error(`Failed to load JSON from ${jsonPath}: ${err.message}`);
  }
}

// ============================================================================
// SYNCHRONOUS VARIANTS (for compatibility)
// ============================================================================

/**
 * Synchronous JSON import (no caching, for immediate reads)
 *
 * @param {string} jsonPath - Path to JSON file
 * @param {object} defaultValue - Default value if file doesn't exist
 * @returns {object} Parsed JSON data
 */
export function hotImportJSONSync(jsonPath, defaultValue = null) {
  const absPath = resolve(jsonPath);

  if (!existsSync(absPath)) {
    return defaultValue;
  }

  try {
    const content = readFileSync(absPath, 'utf-8');
    return JSON.parse(content);
  } catch (err) {
    if (process.env.HOT_RELOAD_DEBUG) {
      console.error(`[hot-reload] Sync JSON parse error: ${err.message}`);
    }
    return defaultValue;
  }
}

// ============================================================================
// CACHE CLEANUP
// ============================================================================

/**
 * Clean up expired cache entries
 *
 * @returns {number} Number of entries removed
 */
export function cleanExpiredCache() {
  let removed = 0;

  for (const [key, entry] of _cache.entries()) {
    if (!_isCacheValid(entry)) {
      _cache.delete(key);
      removed++;
    }
  }

  if (process.env.HOT_RELOAD_DEBUG && removed > 0) {
    console.log(`[hot-reload] Cleaned ${removed} expired cache entries`);
  }

  return removed;
}

// Auto-cleanup every minute
setInterval(cleanExpiredCache, 60000);

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  hotImport,
  hotImportJSON,
  hotImportJSONSync,
  clearCache,
  getCacheStats,
  cleanExpiredCache,
};
