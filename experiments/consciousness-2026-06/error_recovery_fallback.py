#!/usr/bin/env python3
"""
Error Recovery Fallback Strategy

Fleet Consensus: CRITICAL PRIORITY - Deploy Now
Issue: #185
Evidence: 84% reward with fallback, 24% with skip (catastrophic)

Fallback chain:
1. Primary strategy attempt
2. Fallback strategy (if primary fails)
3. Retry with exponential backoff
4. Alternative strategy
5. NEVER skip (anti-pattern)
"""

import time
import logging
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class RecoveryResult:
    success: bool
    result: Any
    strategy: str
    attempts: int
    duration_ms: float
    recovered_from: Optional[str] = None
    error: Optional[Exception] = None

class ErrorRecoveryFallback:
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_ms: int = 1000,
        max_backoff_ms: int = 30000,
        fallback_strategy: str = 'simple_retry',
        alternative_strategies: List[Callable] = None,
        logger: logging.Logger = None
    ):
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.fallback_strategy = fallback_strategy
        self.alternative_strategies = alternative_strategies or []
        self.logger = logger or logging.getLogger(__name__)

        # Circuit breaker state
        self.circuit_open = False
        self.circuit_opened_at = None
        self.circuit_failures = 0
        self.circuit_failure_threshold = 5
        self.circuit_reset_ms = 60000  # 1 minute

    def execute(
        self,
        primary_fn: Callable,
        fallback_fn: Optional[Callable] = None,
        context: Dict = None
    ) -> RecoveryResult:
        """
        Execute with error recovery

        Args:
            primary_fn: Primary strategy function
            fallback_fn: Fallback strategy function
            context: Execution context

        Returns:
            RecoveryResult with success status, result, strategy used, and attempts
        """
        start_time = time.time()
        last_error = None
        context = context or {}

        # Step 1: Try primary strategy
        try:
            self.logger.info("[Recovery] Attempting primary strategy...")
            result = self._attempt_strategy(primary_fn, context)
            return RecoveryResult(
                success=True,
                result=result,
                strategy='primary',
                attempts=1,
                duration_ms=(time.time() - start_time) * 1000
            )
        except Exception as error:
            self.logger.warning(f"[Recovery] Primary failed: {error}")
            last_error = error

        # Step 2: Try fallback strategy
        if fallback_fn:
            try:
                self.logger.info("[Recovery] Attempting fallback strategy...")
                result = self._attempt_strategy(fallback_fn, context)
                return RecoveryResult(
                    success=True,
                    result=result,
                    strategy='fallback',
                    attempts=2,
                    duration_ms=(time.time() - start_time) * 1000,
                    recovered_from=str(last_error)
                )
            except Exception as error:
                self.logger.warning(f"[Recovery] Fallback failed: {error}")
                last_error = error

        # Step 3: Retry with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            backoff_ms = min(
                self.initial_backoff_ms * (2 ** (attempt - 1)),
                self.max_backoff_ms
            )

            self.logger.info(f"[Recovery] Retry {attempt}/{self.max_retries} after {backoff_ms}ms...")
            time.sleep(backoff_ms / 1000.0)

            try:
                result = self._attempt_strategy(primary_fn, context)
                return RecoveryResult(
                    success=True,
                    result=result,
                    strategy='retry',
                    attempts=2 + attempt,
                    duration_ms=(time.time() - start_time) * 1000,
                    recovered_from=str(last_error)
                )
            except Exception as error:
                self.logger.warning(f"[Recovery] Retry {attempt} failed: {error}")
                last_error = error

        # Step 4: Try alternative strategies
        for i, alt_strategy in enumerate(self.alternative_strategies):
            try:
                self.logger.info(f"[Recovery] Attempting alternative strategy {i + 1}...")
                result = self._attempt_strategy(alt_strategy, context)
                return RecoveryResult(
                    success=True,
                    result=result,
                    strategy=f'alternative_{i + 1}',
                    attempts=2 + self.max_retries + i + 1,
                    duration_ms=(time.time() - start_time) * 1000,
                    recovered_from=str(last_error)
                )
            except Exception as error:
                self.logger.warning(f"[Recovery] Alternative {i + 1} failed: {error}")
                last_error = error

        # Step 5: NEVER skip - return failure with context
        # Fleet evidence: Skip = 24% reward (catastrophic)
        return RecoveryResult(
            success=False,
            result=None,
            strategy='exhausted',
            attempts=2 + self.max_retries + len(self.alternative_strategies),
            duration_ms=(time.time() - start_time) * 1000,
            error=last_error
        )

    def execute_with_circuit_breaker(
        self,
        primary_fn: Callable,
        fallback_fn: Optional[Callable] = None,
        context: Dict = None
    ) -> RecoveryResult:
        """Execute with circuit breaker pattern"""
        if self.circuit_open:
            time_since_open = (time.time() * 1000) - self.circuit_opened_at
            if time_since_open < self.circuit_reset_ms:
                # Circuit open - immediately use fallback
                self.logger.warning("[Recovery] Circuit open - using fallback directly")
                try:
                    result = self._attempt_strategy(fallback_fn, context)
                    return RecoveryResult(
                        success=True,
                        result=result,
                        strategy='circuit_breaker_fallback',
                        attempts=1,
                        duration_ms=0
                    )
                except Exception as error:
                    return RecoveryResult(
                        success=False,
                        result=None,
                        strategy='circuit_breaker_failed',
                        attempts=1,
                        duration_ms=0,
                        error=error
                    )
            else:
                # Try to close circuit
                self.circuit_open = False
                self.circuit_failures = 0

        # Normal execution with circuit breaker tracking
        recovery = self.execute(primary_fn, fallback_fn, context)

        if not recovery.success:
            self.circuit_failures += 1
            if self.circuit_failures >= self.circuit_failure_threshold:
                self.circuit_open = True
                self.circuit_opened_at = time.time() * 1000
                self.logger.error(f"[Recovery] Circuit breaker opened after {self.circuit_failures} failures")
        elif recovery.strategy == 'primary':
            # Reset on successful primary
            self.circuit_failures = max(0, self.circuit_failures - 1)

        return recovery

    def _attempt_strategy(self, strategy_fn: Callable, context: Dict) -> Any:
        """Attempt to execute a strategy function"""
        if strategy_fn is None:
            raise ValueError('Strategy function is null')
        return strategy_fn(context)


if __name__ == '__main__':
    # Example usage
    import random

    logging.basicConfig(level=logging.INFO)

    recovery = ErrorRecoveryFallback(
        max_retries=3,
        initial_backoff_ms=1000
    )

    def primary_strategy(context):
        """Simulate occasional failure"""
        if random.random() < 0.3:
            raise Exception('Primary strategy failed')
        return {'status': 'success', 'data': 'Primary result'}

    def fallback_strategy(context):
        """More reliable fallback"""
        if random.random() < 0.1:
            raise Exception('Fallback strategy failed')
        return {'status': 'success', 'data': 'Fallback result'}

    result = recovery.execute(primary_strategy, fallback_strategy, {})
    print(f"\nRecovery result:")
    print(f"  Success: {result.success}")
    print(f"  Strategy: {result.strategy}")
    print(f"  Attempts: {result.attempts}")
    print(f"  Duration: {result.duration_ms:.2f}ms")
    if result.result:
        print(f"  Result: {result.result}")
