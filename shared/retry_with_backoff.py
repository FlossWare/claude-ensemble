#!/usr/bin/env python3
"""
Retry with Exponential Backoff - Handle API Transient Failures Gracefully
Phase 1 CREATE: Exponential backoff, circuit breaker, jitter, and retry wrapper

Components:
1. Backoff Engine (WORKER 1 - Haiku): Exponential backoff with configurable jitter
2. Retry Wrapper (WORKER 2 - Sonnet): Decorator for Claude/provider API calls
3. Circuit Breaker (WORKER 3 - Opus 4.8): Detect failure patterns, fail fast
4. Integration (WORKER 4 - Gemini): Wire into Thompson router, test on failures
"""

import time
import random
import logging
import asyncio
from typing import Callable, Any, Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timedelta
from functools import wraps
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# WORKER 1: BACKOFF ENGINE (Haiku) - Exponential backoff with jitter
# ============================================================================

class BackoffStrategy(Enum):
    """Backoff strategies for retry logic"""
    LINEAR = "linear"              # 100ms, 200ms, 300ms
    EXPONENTIAL = "exponential"    # 100ms, 200ms, 400ms, 800ms
    FIBONACCI = "fibonacci"        # 100ms, 100ms, 200ms, 300ms, 500ms


@dataclass
class BackoffConfig:
    """Configuration for backoff behavior"""
    initial_delay_ms: float = 100       # Start with 100ms
    max_delay_ms: float = 30000         # Cap at 30 seconds
    multiplier: float = 2.0             # Exponential growth factor
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    use_jitter: bool = True             # Add randomness to avoid thundering herd
    jitter_factor: float = 0.1          # 10% jitter on top of calculated delay

    def __post_init__(self):
        """Validate config"""
        if self.initial_delay_ms <= 0:
            raise ValueError("initial_delay_ms must be positive")
        if self.max_delay_ms < self.initial_delay_ms:
            raise ValueError("max_delay_ms must be >= initial_delay_ms")
        if self.multiplier <= 1.0:
            raise ValueError("multiplier must be > 1.0")


class BackoffEngine:
    """WORKER 1: Calculate backoff delays with jitter"""

    def __init__(self, config: BackoffConfig = None):
        """Initialize backoff engine"""
        self.config = config or BackoffConfig()
        self._attempt_counter = 0

    def calculate_delay_ms(self, attempt: int) -> float:
        """
        Calculate next backoff delay in milliseconds.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in milliseconds
        """
        if attempt < 0:
            raise ValueError("attempt must be >= 0")

        # Calculate base delay based on strategy
        if self.config.strategy == BackoffStrategy.EXPONENTIAL:
            base_delay = self.config.initial_delay_ms * (self.config.multiplier ** attempt)
        elif self.config.strategy == BackoffStrategy.LINEAR:
            base_delay = self.config.initial_delay_ms * (attempt + 1)
        elif self.config.strategy == BackoffStrategy.FIBONACCI:
            base_delay = self._fibonacci_delay(attempt)
        else:
            base_delay = self.config.initial_delay_ms

        # Cap at maximum
        capped_delay = min(base_delay, self.config.max_delay_ms)

        # Add jitter to avoid thundering herd
        if self.config.use_jitter:
            jitter = capped_delay * self.config.jitter_factor * random.random()
            final_delay = capped_delay + jitter
        else:
            final_delay = capped_delay

        return final_delay

    def _fibonacci_delay(self, attempt: int) -> float:
        """Calculate Fibonacci-based delay"""
        # Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13, 21...
        if attempt <= 1:
            fib = 1
        else:
            a, b = 1, 1
            for _ in range(attempt - 1):
                a, b = b, a + b
            fib = b
        return self.config.initial_delay_ms * fib

    async def sleep_until_next_attempt(self, attempt: int) -> float:
        """
        Async sleep until next retry attempt.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Actual delay applied (ms)
        """
        delay_ms = self.calculate_delay_ms(attempt)
        delay_s = delay_ms / 1000.0
        logger.info(f"Backoff: attempt {attempt}, sleeping {delay_ms:.1f}ms")
        await asyncio.sleep(delay_s)
        return delay_ms

    def sleep_until_next_attempt_sync(self, attempt: int) -> float:
        """Synchronous version of sleep_until_next_attempt"""
        delay_ms = self.calculate_delay_ms(attempt)
        delay_s = delay_ms / 1000.0
        logger.info(f"Backoff: attempt {attempt}, sleeping {delay_ms:.1f}ms")
        time.sleep(delay_s)
        return delay_ms


# ============================================================================
# WORKER 2: RETRY WRAPPER (Sonnet) - Decorator for API calls
# ============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    backoff: BackoffConfig = field(default_factory=BackoffConfig)
    # Transient errors to retry on (HTTP status codes, exception types)
    retryable_exceptions: Tuple[type, ...] = (
        TimeoutError,
        ConnectionError,
        asyncio.TimeoutError,
    )
    retryable_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    # Log each retry attempt
    verbose: bool = True


class RetryableError(Exception):
    """Raised when retryable error occurs"""
    def __init__(self, message: str, attempt: int, last_exception: Exception = None):
        self.message = message
        self.attempt = attempt
        self.last_exception = last_exception
        super().__init__(message)


class ExhaustedRetriesError(Exception):
    """Raised when all retry attempts exhausted"""
    def __init__(self, message: str, attempts: int, last_exception: Exception = None):
        self.message = message
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(message)


class RetryWrapper:
    """WORKER 2: Retry wrapper for async and sync API calls"""

    def __init__(self, config: RetryConfig = None):
        """Initialize retry wrapper"""
        self.config = config or RetryConfig()
        self.backoff_engine = BackoffEngine(self.config.backoff)
        self.stats = {
            'total_attempts': 0,
            'successful_retries': 0,  # Succeeded after failure
            'failed_calls': 0,
            'retried_calls': 0,
        }

    def is_retryable(self, exc: Exception) -> bool:
        """Check if exception is retryable"""
        if exc is None:
            return False

        # Check if exception type is in retryable list
        if isinstance(exc, self.config.retryable_exceptions):
            return True

        # Check if exception has status_code attribute (for HTTP errors)
        if hasattr(exc, 'status_code'):
            return exc.status_code in self.config.retryable_status_codes

        return False

    async def async_retry(self,
                          func: Callable,
                          *args,
                          operation_name: str = None,
                          **kwargs) -> Any:
        """
        Retry an async function with exponential backoff.

        Args:
            func: Async function to call
            args: Positional arguments for func
            operation_name: Name for logging
            kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            ExhaustedRetriesError: When all retries exhausted
        """
        if operation_name is None:
            operation_name = getattr(func, '__name__', 'unknown')

        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                self.stats['total_attempts'] += 1

                if attempt == 0:
                    logger.info(f"[{operation_name}] Starting (max {self.config.max_retries} attempts)")
                else:
                    logger.info(f"[{operation_name}] Retry attempt {attempt}")

                result = await func(*args, **kwargs)

                if attempt > 0:
                    self.stats['successful_retries'] += 1
                    logger.info(f"[{operation_name}] Succeeded after {attempt} retries")

                return result

            except Exception as e:
                last_exception = e

                if not self.is_retryable(e):
                    logger.error(f"[{operation_name}] Non-retryable error: {e}")
                    self.stats['failed_calls'] += 1
                    raise

                if attempt >= self.config.max_retries - 1:
                    logger.error(f"[{operation_name}] Exhausted retries after {attempt + 1} attempts")
                    self.stats['failed_calls'] += 1
                    raise ExhaustedRetriesError(
                        f"{operation_name} failed after {attempt + 1} attempts: {e}",
                        attempts=attempt + 1,
                        last_exception=e
                    )

                # Log and backoff
                if self.config.verbose:
                    logger.warning(f"[{operation_name}] Attempt {attempt} failed: {e}")

                self.stats['retried_calls'] += 1
                delay_ms = await self.backoff_engine.sleep_until_next_attempt(attempt)

    def sync_retry(self,
                   func: Callable,
                   *args,
                   operation_name: str = None,
                   **kwargs) -> Any:
        """Synchronous version of async_retry"""
        if operation_name is None:
            operation_name = getattr(func, '__name__', 'unknown')

        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                self.stats['total_attempts'] += 1

                if attempt == 0:
                    logger.info(f"[{operation_name}] Starting (max {self.config.max_retries} attempts)")
                else:
                    logger.info(f"[{operation_name}] Retry attempt {attempt}")

                result = func(*args, **kwargs)

                if attempt > 0:
                    self.stats['successful_retries'] += 1
                    logger.info(f"[{operation_name}] Succeeded after {attempt} retries")

                return result

            except Exception as e:
                last_exception = e

                if not self.is_retryable(e):
                    logger.error(f"[{operation_name}] Non-retryable error: {e}")
                    self.stats['failed_calls'] += 1
                    raise

                if attempt >= self.config.max_retries - 1:
                    logger.error(f"[{operation_name}] Exhausted retries after {attempt + 1} attempts")
                    self.stats['failed_calls'] += 1
                    raise ExhaustedRetriesError(
                        f"{operation_name} failed after {attempt + 1} attempts: {e}",
                        attempts=attempt + 1,
                        last_exception=e
                    )

                if self.config.verbose:
                    logger.warning(f"[{operation_name}] Attempt {attempt} failed: {e}")

                self.stats['retried_calls'] += 1
                self.backoff_engine.sleep_until_next_attempt_sync(attempt)

    def get_stats(self) -> Dict[str, Any]:
        """Get retry statistics"""
        return self.stats.copy()


def retry(config: RetryConfig = None):
    """
    Decorator for retrying functions with exponential backoff.

    Usage:
        @retry(RetryConfig(max_retries=3))
        async def api_call():
            ...
    """
    retry_config = config or RetryConfig()
    wrapper = RetryWrapper(retry_config)

    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await wrapper.async_retry(
                    func, *args,
                    operation_name=func.__name__,
                    **kwargs
                )
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return wrapper.sync_retry(
                    func, *args,
                    operation_name=func.__name__,
                    **kwargs
                )
            return sync_wrapper

    return decorator


# ============================================================================
# WORKER 3: CIRCUIT BREAKER (Opus 4.8) - Detect service failures
# ============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Service down, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5         # Failures before opening circuit
    recovery_timeout_s: int = 60       # Seconds before trying half-open
    success_threshold: int = 2         # Successes in half-open to close
    error_rate_threshold: float = 0.5  # Fail if 50%+ requests fail


class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    pass


class CircuitBreaker:
    """WORKER 3: Circuit breaker to detect repeated failures and fail fast"""

    def __init__(self, service_name: str, config: CircuitBreakerConfig = None):
        """Initialize circuit breaker"""
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        self.stats = {
            'total_calls': 0,
            'failures': 0,
            'successes': 0,
            'rejected': 0,  # Calls rejected because circuit open
            'state_changes': 0,
        }

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time passed to try recovery"""
        if self.last_failure_time is None:
            return False

        recovery_time = self.last_failure_time + timedelta(seconds=self.config.recovery_timeout_s)
        return datetime.now() >= recovery_time

    def record_success(self):
        """Record successful call"""
        self.stats['total_calls'] += 1
        self.stats['successes'] += 1
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._change_state(CircuitState.CLOSED)
                logger.info(f"[{self.service_name}] Circuit CLOSED - service recovered")
        elif self.state == CircuitState.CLOSED:
            pass  # Normal operation

    def record_failure(self):
        """Record failed call"""
        self.stats['total_calls'] += 1
        self.stats['failures'] += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0

        # Need minimum number of calls to evaluate error rate
        if self.stats['total_calls'] >= 10:
            error_rate = self.stats['failures'] / self.stats['total_calls']
        else:
            error_rate = 0

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold or \
               (self.stats['total_calls'] >= 10 and error_rate >= self.config.error_rate_threshold):
                self._change_state(CircuitState.OPEN)
                logger.warning(f"[{self.service_name}] Circuit OPEN - too many failures")

        elif self.state == CircuitState.HALF_OPEN:
            self._change_state(CircuitState.OPEN)
            logger.warning(f"[{self.service_name}] Circuit back to OPEN - recovery failed")

    def call_allowed(self) -> bool:
        """Check if call is allowed based on circuit state"""
        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._change_state(CircuitState.HALF_OPEN)
                logger.info(f"[{self.service_name}] Circuit HALF_OPEN - attempting recovery")
                return True
            else:
                self.stats['rejected'] += 1
                return False

        elif self.state == CircuitState.HALF_OPEN:
            return True  # Allow test call

        return False

    def _change_state(self, new_state: CircuitState):
        """Change circuit state"""
        if self.state != new_state:
            old_state = self.state.value
            self.state = new_state
            self.last_state_change = datetime.now()
            self.stats['state_changes'] += 1
            logger.info(f"[{self.service_name}] State change: {old_state} -> {new_state.value}")

    async def async_call(self,
                        func: Callable,
                        *args,
                        on_circuit_open: Callable = None,
                        **kwargs) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to call
            args: Positional arguments
            on_circuit_open: Fallback function if circuit open
            kwargs: Keyword arguments

        Returns:
            Result from func or fallback

        Raises:
            CircuitBreakerError: If circuit open and no fallback
        """
        if not self.call_allowed():
            if on_circuit_open:
                return await on_circuit_open(*args, **kwargs) if asyncio.iscoroutinefunction(on_circuit_open) else on_circuit_open(*args, **kwargs)
            raise CircuitBreakerError(f"{self.service_name} circuit is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def sync_call(self,
                  func: Callable,
                  *args,
                  on_circuit_open: Callable = None,
                  **kwargs) -> Any:
        """Synchronous version of async_call"""
        if not self.call_allowed():
            if on_circuit_open:
                return on_circuit_open(*args, **kwargs)
            raise CircuitBreakerError(f"{self.service_name} circuit is OPEN")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def get_state(self) -> str:
        """Get current circuit state"""
        return self.state.value

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            **self.stats,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'uptime_since_change_s': (datetime.now() - self.last_state_change).total_seconds(),
        }


# ============================================================================
# WORKER 4: INTEGRATION - Thompson router integration
# ============================================================================

class IntegratedRetryClient:
    """Integration of retry + circuit breaker + Thompson router"""

    def __init__(self,
                 service_name: str,
                 retry_config: RetryConfig = None,
                 circuit_config: CircuitBreakerConfig = None):
        """Initialize integrated retry client"""
        self.service_name = service_name
        self.retry_wrapper = RetryWrapper(retry_config or RetryConfig())
        self.circuit_breaker = CircuitBreaker(service_name, circuit_config or CircuitBreakerConfig())
        self.request_log = []

    async def async_call(self,
                        func: Callable,
                        *args,
                        fallback: Callable = None,
                        **kwargs) -> Any:
        """
        Execute async call with full retry + circuit breaker logic.

        Args:
            func: Async function to call
            args: Positional arguments
            fallback: Fallback function if circuit open
            kwargs: Keyword arguments

        Returns:
            Result from func or fallback
        """
        operation_name = getattr(func, '__name__', self.service_name)

        try:
            # Try with circuit breaker protection
            async def protected_call():
                return await self.circuit_breaker.async_call(
                    self.retry_wrapper.async_retry,
                    func,
                    *args,
                    operation_name=operation_name,
                    **kwargs
                )

            result = await protected_call()
            self.request_log.append({
                'timestamp': datetime.now().isoformat(),
                'operation': operation_name,
                'status': 'success',
                'circuit_state': self.circuit_breaker.get_state(),
            })
            return result

        except Exception as e:
            logger.error(f"Call to {operation_name} failed: {e}")
            self.request_log.append({
                'timestamp': datetime.now().isoformat(),
                'operation': operation_name,
                'status': 'failed',
                'error': str(e),
                'circuit_state': self.circuit_breaker.get_state(),
            })

            if fallback:
                logger.info(f"Using fallback for {operation_name}")
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            raise

    def sync_call(self,
                  func: Callable,
                  *args,
                  fallback: Callable = None,
                  **kwargs) -> Any:
        """Synchronous version of async_call"""
        operation_name = getattr(func, '__name__', self.service_name)

        try:
            result = self.circuit_breaker.sync_call(
                self.retry_wrapper.sync_retry,
                func,
                *args,
                operation_name=operation_name,
                **kwargs
            )
            self.request_log.append({
                'timestamp': datetime.now().isoformat(),
                'operation': operation_name,
                'status': 'success',
                'circuit_state': self.circuit_breaker.get_state(),
            })
            return result

        except Exception as e:
            logger.error(f"Call to {operation_name} failed: {e}")
            self.request_log.append({
                'timestamp': datetime.now().isoformat(),
                'operation': operation_name,
                'status': 'failed',
                'error': str(e),
                'circuit_state': self.circuit_breaker.get_state(),
            })

            if fallback:
                logger.info(f"Using fallback for {operation_name}")
                return fallback(*args, **kwargs)
            raise

    def get_health_report(self) -> Dict[str, Any]:
        """Get health report for monitoring"""
        return {
            'service': self.service_name,
            'circuit': self.circuit_breaker.get_stats(),
            'retry': self.retry_wrapper.get_stats(),
            'recent_requests': self.request_log[-10:],  # Last 10 requests
        }

    def save_health_report(self, filepath: str):
        """Save health report to JSON file"""
        report = self.get_health_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Health report saved to {filepath}")


if __name__ == '__main__':
    # Simple test
    import sys

    # Test backoff engine
    print("=" * 60)
    print("WORKER 1: Backoff Engine Test")
    print("=" * 60)

    backoff = BackoffEngine(BackoffConfig(initial_delay_ms=100, use_jitter=False))
    print("Exponential backoff (no jitter):")
    for i in range(4):
        delay = backoff.calculate_delay_ms(i)
        print(f"  Attempt {i}: {delay:.1f}ms")

    # Test circuit breaker
    print("\n" + "=" * 60)
    print("WORKER 3: Circuit Breaker Test")
    print("=" * 60)

    cb = CircuitBreaker("test-service", CircuitBreakerConfig(failure_threshold=2))

    def failing_call():
        raise ConnectionError("Service down")

    def passing_call():
        return "OK"

    print(f"Initial state: {cb.get_state()}")

    # Simulate failures
    for i in range(3):
        if cb.call_allowed():
            try:
                failing_call()
            except:
                cb.record_failure()
        print(f"After failure {i+1}: {cb.get_state()}")

    # Try to call - should be rejected
    print(f"Call allowed when OPEN: {cb.call_allowed()}")

    print("\nCircuit breaker stats:")
    print(json.dumps(cb.get_stats(), indent=2, default=str))

    print("\n✓ Phase 1 CREATE complete - Ready for Phase 2 testing")
