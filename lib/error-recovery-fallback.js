#!/usr/bin/env node
/**
 * Error Recovery Fallback Strategy
 *
 * Fleet Consensus: CRITICAL PRIORITY - Deploy Now
 * Issue: #185
 * Evidence: 84% reward with fallback, 24% with skip (catastrophic)
 *
 * Fallback chain:
 * 1. Primary strategy attempt
 * 2. Fallback strategy (if primary fails)
 * 3. Retry with exponential backoff
 * 4. Alternative strategy
 * 5. NEVER skip (anti-pattern)
 */

class ErrorRecoveryFallback {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 3;
    this.initialBackoffMs = options.initialBackoffMs || 1000;
    this.maxBackoffMs = options.maxBackoffMs || 30000;
    this.fallbackStrategy = options.fallbackStrategy || 'simple_retry';
    this.alternativeStrategies = options.alternativeStrategies || [];
    this.logger = options.logger || console;
  }

  /**
   * Execute with error recovery
   * @param {Function} primaryFn - Primary strategy function
   * @param {Function} fallbackFn - Fallback strategy function
   * @param {Object} context - Execution context
   * @returns {Promise<{success: boolean, result: any, strategy: string, attempts: number}>}
   */
  async execute(primaryFn, fallbackFn, context = {}) {
    const startTime = Date.now();
    let lastError = null;

    // Step 1: Try primary strategy
    try {
      this.logger.log(`[Recovery] Attempting primary strategy...`);
      const result = await this.attemptStrategy(primaryFn, context);
      return {
        success: true,
        result,
        strategy: 'primary',
        attempts: 1,
        durationMs: Date.now() - startTime
      };
    } catch (error) {
      this.logger.warn(`[Recovery] Primary failed: ${error.message}`);
      lastError = error;
    }

    // Step 2: Try fallback strategy
    if (fallbackFn) {
      try {
        this.logger.log(`[Recovery] Attempting fallback strategy...`);
        const result = await this.attemptStrategy(fallbackFn, context);
        return {
          success: true,
          result,
          strategy: 'fallback',
          attempts: 2,
          durationMs: Date.now() - startTime,
          recoveredFrom: lastError.message
        };
      } catch (error) {
        this.logger.warn(`[Recovery] Fallback failed: ${error.message}`);
        lastError = error;
      }
    }

    // Step 3: Retry with exponential backoff
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      const backoffMs = Math.min(
        this.initialBackoffMs * Math.pow(2, attempt - 1),
        this.maxBackoffMs
      );

      this.logger.log(`[Recovery] Retry ${attempt}/${this.maxRetries} after ${backoffMs}ms...`);
      await this.sleep(backoffMs);

      try {
        const result = await this.attemptStrategy(primaryFn, context);
        return {
          success: true,
          result,
          strategy: 'retry',
          attempts: 2 + attempt,
          durationMs: Date.now() - startTime,
          recoveredFrom: lastError.message
        };
      } catch (error) {
        this.logger.warn(`[Recovery] Retry ${attempt} failed: ${error.message}`);
        lastError = error;
      }
    }

    // Step 4: Try alternative strategies
    for (let i = 0; i < this.alternativeStrategies.length; i++) {
      const altStrategy = this.alternativeStrategies[i];
      try {
        this.logger.log(`[Recovery] Attempting alternative strategy ${i + 1}...`);
        const result = await this.attemptStrategy(altStrategy, context);
        return {
          success: true,
          result,
          strategy: `alternative_${i + 1}`,
          attempts: 2 + this.maxRetries + i + 1,
          durationMs: Date.now() - startTime,
          recoveredFrom: lastError.message
        };
      } catch (error) {
        this.logger.warn(`[Recovery] Alternative ${i + 1} failed: ${error.message}`);
        lastError = error;
      }
    }

    // Step 5: NEVER skip - return failure with context
    // Fleet evidence: Skip = 24% reward (catastrophic)
    return {
      success: false,
      result: null,
      strategy: 'exhausted',
      attempts: 2 + this.maxRetries + this.alternativeStrategies.length,
      durationMs: Date.now() - startTime,
      error: lastError,
      message: 'All recovery strategies exhausted - never skipping (anti-pattern)'
    };
  }

  /**
   * Execute with circuit breaker pattern
   */
  async executeWithCircuitBreaker(primaryFn, fallbackFn, context = {}) {
    if (this.circuitOpen) {
      const timeSinceOpen = Date.now() - this.circuitOpenedAt;
      if (timeSinceOpen < this.circuitResetMs) {
        // Circuit open - immediately use fallback
        this.logger.warn(`[Recovery] Circuit open - using fallback directly`);
        try {
          const result = await this.attemptStrategy(fallbackFn, context);
          return {
            success: true,
            result,
            strategy: 'circuit_breaker_fallback',
            attempts: 1
          };
        } catch (error) {
          return {
            success: false,
            result: null,
            strategy: 'circuit_breaker_failed',
            attempts: 1,
            error
          };
        }
      } else {
        // Try to close circuit
        this.circuitOpen = false;
        this.circuitFailures = 0;
      }
    }

    // Normal execution with circuit breaker tracking
    const recovery = await this.execute(primaryFn, fallbackFn, context);

    if (!recovery.success) {
      this.circuitFailures++;
      if (this.circuitFailures >= this.circuitFailureThreshold) {
        this.circuitOpen = true;
        this.circuitOpenedAt = Date.now();
        this.logger.error(`[Recovery] Circuit breaker opened after ${this.circuitFailures} failures`);
      }
    } else if (recovery.strategy === 'primary') {
      // Reset on successful primary
      this.circuitFailures = Math.max(0, this.circuitFailures - 1);
    }

    return recovery;
  }

  async attemptStrategy(strategyFn, context) {
    if (!strategyFn) {
      throw new Error('Strategy function is null');
    }
    return await strategyFn(context);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Circuit breaker state
  circuitOpen = false;
  circuitOpenedAt = null;
  circuitFailures = 0;
  circuitFailureThreshold = 5;
  circuitResetMs = 60000; // 1 minute
}

module.exports = ErrorRecoveryFallback;

// CLI usage
if (require.main === module) {
  const recovery = new ErrorRecoveryFallback({
    maxRetries: 3,
    initialBackoffMs: 1000,
    fallbackStrategy: 'simple_retry'
  });

  // Example usage
  const primaryStrategy = async (context) => {
    // Simulate occasional failure
    if (Math.random() < 0.3) {
      throw new Error('Primary strategy failed');
    }
    return { status: 'success', data: 'Primary result' };
  };

  const fallbackStrategy = async (context) => {
    // More reliable fallback
    if (Math.random() < 0.1) {
      throw new Error('Fallback strategy failed');
    }
    return { status: 'success', data: 'Fallback result' };
  };

  recovery.execute(primaryStrategy, fallbackStrategy, {})
    .then(result => {
      console.log(JSON.stringify(result, null, 2));
    });
}
