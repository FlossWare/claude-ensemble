export class CircuitBreaker {
  constructor({ threshold = 5, resetTimeout = 30000 } = {}) {
    this.threshold = threshold;
    this.resetTimeout = resetTimeout;
    this.failures = new Map();
    this.openUntil = new Map();

    // Periodic cleanup to prevent memory leak
    this.cleanupInterval = setInterval(() => this.cleanup(), this.resetTimeout * 2);
  }

  cleanup() {
    const now = Date.now();

    // Clean up expired circuit breaker states
    for (const [worker, until] of this.openUntil) {
      if (until < now) {
        this.openUntil.delete(worker);
        // Also reset failure count for recovered workers
        this.failures.delete(worker);
      }
    }

    // Clean up old failure entries for workers that haven't failed recently
    // Keep entries that are either currently open or have recent failures
    for (const [worker, count] of this.failures) {
      if (!this.openUntil.has(worker) && count === 0) {
        this.failures.delete(worker);
      }
    }
  }

  destroy() {
    // Allow explicit cleanup of the interval
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
  }

  onFailure(worker) {
    const count = this.failures.get(worker) || 0;
    this.failures.set(worker, count + 1);
    if (count + 1 >= this.threshold) {
      this.openUntil.set(worker, Date.now() + this.resetTimeout);
    }
  }

  async execute(worker, fn) {
    const openUntil = this.openUntil.get(worker);
    if (openUntil && Date.now() < openUntil) {
      throw new Error(`Circuit breaker OPEN for ${worker}`);
    }

    try {
      const result = await fn();
      this.failures.set(worker, 0);
      this.openUntil.delete(worker);
      return result;
    } catch (error) {
      this.onFailure(worker);
      throw error;
    }
  }
}
