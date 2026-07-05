/**
 * Embedding Generation Pool
 *
 * Throttles embedding generation to prevent CPU overload.
 * Limits concurrent processes and implements queuing.
 */

const { spawn } = require('child_process');
const path = require('path');

class EmbeddingPool {
  constructor(options = {}) {
    this.maxConcurrent = options.maxConcurrent || 4; // Max 4 concurrent embeddings
    this.timeout = options.timeout || 120000; // 120 second timeout (for model loading)
    this.pythonScript = path.join(__dirname, 'generate-embeddings.py');

    this.running = 0;
    this.queue = [];
  }

  /**
   * Generate embeddings with throttling
   * @param {string|string[]} texts - Text(s) to embed
   * @returns {Promise<number[]|number[][]>} Embedding(s)
   */
  async generate(texts) {
    // Normalize to array
    const isArray = Array.isArray(texts);
    const textsArray = isArray ? texts : [texts];

    // If at capacity, queue the request
    if (this.running >= this.maxConcurrent) {
      await new Promise((resolve) => {
        this.queue.push(resolve);
      });
    }

    this.running++;

    try {
      const result = await this._generateInternal(textsArray);
      return isArray ? result : result[0];
    } finally {
      this.running--;

      // Process next in queue
      if (this.queue.length > 0) {
        const next = this.queue.shift();
        next();
      }
    }
  }

  /**
   * Internal embedding generation (no throttling)
   */
  async _generateInternal(texts) {
    return new Promise((resolve, reject) => {
      const process = spawn('python3', [this.pythonScript], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';
      let timeoutId;

      // Set timeout
      timeoutId = setTimeout(() => {
        process.kill('SIGTERM');
        reject(new Error(`Embedding generation timeout (>${this.timeout}ms)`));
      }, this.timeout);

      process.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        clearTimeout(timeoutId);

        if (code !== 0) {
          reject(new Error(`Embedding generation failed: ${stderr}`));
          return;
        }

        try {
          const result = JSON.parse(stdout);

          if (result.error) {
            reject(new Error(result.error));
            return;
          }

          resolve(result.embeddings || []);
        } catch (err) {
          reject(new Error(`Failed to parse embedding result: ${err.message}`));
        }
      });

      process.on('error', (err) => {
        clearTimeout(timeoutId);
        reject(err);
      });

      // Send input to Python script
      process.stdin.write(JSON.stringify(texts));
      process.stdin.end();
    });
  }

  /**
   * Get current pool status
   */
  getStatus() {
    return {
      running: this.running,
      queued: this.queue.length,
      maxConcurrent: this.maxConcurrent
    };
  }
}

// Singleton instance
let globalPool = null;

function getEmbeddingPool(options) {
  if (!globalPool) {
    globalPool = new EmbeddingPool(options);
  }
  return globalPool;
}

module.exports = {
  EmbeddingPool,
  getEmbeddingPool
};
