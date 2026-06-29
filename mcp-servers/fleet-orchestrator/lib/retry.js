const RETRYABLE_CODES = ['ECONNREFUSED', 'ETIMEDOUT', 'ENOTFOUND', 'EHOSTUNREACH'];
const RETRYABLE_STATUS = [429, 503, 504, 408];

function isRetryable(error) {
  if (RETRYABLE_CODES.includes(error.code)) return true;
  if (RETRYABLE_STATUS.includes(error.statusCode)) return true;
  if (error.statusCode >= 500 && error.statusCode < 600) return true;
  return false;
}

export async function withRetry(fn, opts = {}) {
  const maxRetries = opts.maxRetries || 3;
  const backoffMs = opts.backoffMs || 1000;
  const backoffMultiplier = opts.backoffMultiplier || 2;
  const totalTimeout = opts.totalTimeout;

  const startTime = Date.now();

  let lastError;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    // Check total timeout
    if (totalTimeout && (Date.now() - startTime) >= totalTimeout) {
      throw new Error('Total timeout exceeded');
    }

    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries - 1 && !isRetryable(error)) {
        throw error; // Don't retry auth/client errors
      }
      if (attempt < maxRetries - 1) {
        // Add jitter: multiply by random factor between 0.5 and 1.5
        const delay = backoffMs * Math.pow(backoffMultiplier, attempt) * (0.5 + Math.random());
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}
