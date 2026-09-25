#!/usr/bin/env python3
"""
Test suite for Retry with Exponential Backoff system
Phase 1 CREATE: Unit and integration tests for all 4 workers
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from retry_with_backoff import (
    BackoffEngine, BackoffConfig, BackoffStrategy,
    RetryWrapper, RetryConfig, ExhaustedRetriesError,
    CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerError,
    IntegratedRetryClient, retry,
)


# ============================================================================
# WORKER 1: Backoff Engine Tests
# ============================================================================

class TestBackoffEngine:
    """Test WORKER 1: Backoff engine with jitter"""

    def test_exponential_backoff_no_jitter(self):
        """Test exponential backoff calculation"""
        config = BackoffConfig(
            initial_delay_ms=100,
            max_delay_ms=30000,
            multiplier=2.0,
            strategy=BackoffStrategy.EXPONENTIAL,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        expected = [100, 200, 400, 800]
        for attempt, expected_delay in enumerate(expected):
            actual = engine.calculate_delay_ms(attempt)
            assert actual == expected_delay, f"Attempt {attempt}: expected {expected_delay}ms, got {actual}ms"

    def test_exponential_backoff_with_cap(self):
        """Test that backoff is capped at max_delay_ms"""
        config = BackoffConfig(
            initial_delay_ms=100,
            max_delay_ms=500,  # Low cap
            multiplier=2.0,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        # Should cap at 500
        delay = engine.calculate_delay_ms(10)  # 100 * 2^10 = 102400ms
        assert delay <= 500

    def test_linear_backoff(self):
        """Test linear backoff strategy"""
        config = BackoffConfig(
            initial_delay_ms=100,
            strategy=BackoffStrategy.LINEAR,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        expected = [100, 200, 300, 400]
        for attempt, expected_delay in enumerate(expected):
            actual = engine.calculate_delay_ms(attempt)
            assert actual == expected_delay

    def test_fibonacci_backoff(self):
        """Test Fibonacci backoff strategy"""
        config = BackoffConfig(
            initial_delay_ms=100,
            strategy=BackoffStrategy.FIBONACCI,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        # Fibonacci: 1, 1, 2, 3, 5... * 100ms = 100, 100, 200, 300, 500
        expected = [100, 100, 200, 300, 500]
        for attempt, expected_delay in enumerate(expected):
            actual = engine.calculate_delay_ms(attempt)
            assert actual == expected_delay

    def test_jitter_adds_randomness(self):
        """Test that jitter adds variance to delays"""
        config = BackoffConfig(
            initial_delay_ms=100,
            use_jitter=True,
            jitter_factor=0.1
        )
        engine = BackoffEngine(config)

        delays = [engine.calculate_delay_ms(0) for _ in range(100)]
        # All delays should be close to 100ms but not exactly 100ms
        assert all(90 <= d <= 110 for d in delays), f"Delays not in jitter range: {set(delays)}"
        # Should have variance
        assert len(set(delays)) > 1, "No variance in jittered delays"

    @pytest.mark.asyncio
    async def test_async_sleep(self):
        """Test async sleep until next attempt"""
        config = BackoffConfig(
            initial_delay_ms=50,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        start = time.time()
        actual_delay = await engine.sleep_until_next_attempt(0)
        elapsed = (time.time() - start) * 1000

        assert 40 < elapsed < 100, f"Expected ~50ms sleep, got {elapsed}ms"
        assert actual_delay == 50.0

    def test_sync_sleep(self):
        """Test sync sleep until next attempt"""
        config = BackoffConfig(
            initial_delay_ms=50,
            use_jitter=False
        )
        engine = BackoffEngine(config)

        start = time.time()
        actual_delay = engine.sleep_until_next_attempt_sync(0)
        elapsed = (time.time() - start) * 1000

        assert 40 < elapsed < 100, f"Expected ~50ms sleep, got {elapsed}ms"


# ============================================================================
# WORKER 2: Retry Wrapper Tests
# ============================================================================

class TestRetryWrapper:
    """Test WORKER 2: Retry wrapper with retry logic"""

    def test_retryable_exception_check(self):
        """Test retryable exception detection"""
        wrapper = RetryWrapper()

        assert wrapper.is_retryable(TimeoutError("timeout"))
        assert wrapper.is_retryable(ConnectionError("connection"))
        assert not wrapper.is_retryable(ValueError("value error"))
        assert not wrapper.is_retryable(None)

    def test_retryable_status_code(self):
        """Test retryable HTTP status codes"""
        wrapper = RetryWrapper()

        class HTTPError(Exception):
            def __init__(self, status_code):
                self.status_code = status_code

        assert wrapper.is_retryable(HTTPError(500))
        assert wrapper.is_retryable(HTTPError(503))
        assert not wrapper.is_retryable(HTTPError(400))

    def test_sync_retry_immediate_success(self):
        """Test sync retry that succeeds immediately"""
        wrapper = RetryWrapper()
        func = Mock(return_value="success")

        result = wrapper.sync_retry(func, operation_name="test")

        assert result == "success"
        func.assert_called_once()
        assert wrapper.stats['total_attempts'] == 1
        assert wrapper.stats['successful_retries'] == 0

    def test_sync_retry_with_retryable_failure(self):
        """Test sync retry with one failure then success"""
        wrapper = RetryWrapper()
        func = Mock(side_effect=[
            ConnectionError("Connection failed"),
            "success"
        ])

        result = wrapper.sync_retry(func, operation_name="test")

        assert result == "success"
        assert func.call_count == 2
        assert wrapper.stats['total_attempts'] == 2
        assert wrapper.stats['successful_retries'] == 1
        assert wrapper.stats['retried_calls'] == 1

    def test_sync_retry_exhausted(self):
        """Test sync retry with exhausted retries"""
        config = RetryConfig(
            max_retries=3,
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        )
        wrapper = RetryWrapper(config)
        func = Mock(side_effect=TimeoutError("Always times out"))

        with pytest.raises(ExhaustedRetriesError) as exc_info:
            wrapper.sync_retry(func, operation_name="test")

        assert exc_info.value.attempts == 3
        assert func.call_count == 3
        assert wrapper.stats['total_attempts'] == 3
        assert wrapper.stats['failed_calls'] == 1

    def test_sync_retry_non_retryable_error(self):
        """Test that non-retryable errors fail immediately"""
        config = RetryConfig(max_retries=5)
        wrapper = RetryWrapper(config)
        func = Mock(side_effect=ValueError("Not retryable"))

        with pytest.raises(ValueError):
            wrapper.sync_retry(func, operation_name="test")

        func.assert_called_once()
        assert wrapper.stats['total_attempts'] == 1
        assert wrapper.stats['failed_calls'] == 1

    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry success"""
        wrapper = RetryWrapper()
        func = AsyncMock(return_value="async success")

        result = await wrapper.async_retry(func, operation_name="test")

        assert result == "async success"
        assert wrapper.stats['total_attempts'] == 1

    @pytest.mark.asyncio
    async def test_async_retry_with_failure(self):
        """Test async retry with one failure"""
        wrapper = RetryWrapper()
        func = AsyncMock(side_effect=[
            TimeoutError("Timeout"),
            "success"
        ])

        result = await wrapper.async_retry(func, operation_name="test")

        assert result == "success"
        assert func.call_count == 2
        assert wrapper.stats['successful_retries'] == 1

    def test_retry_decorator_sync(self):
        """Test @retry decorator on sync function"""
        call_count = 0

        @retry(RetryConfig(
            max_retries=3,
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        ))
        def unstable_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("First call fails")
            return "success"

        result = unstable_function()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_decorator_async(self):
        """Test @retry decorator on async function"""
        call_count = 0

        @retry(RetryConfig(
            max_retries=3,
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        ))
        async def async_unstable():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("First call fails")
            return "async success"

        result = await async_unstable()
        assert result == "async success"
        assert call_count == 2


# ============================================================================
# WORKER 3: Circuit Breaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test WORKER 3: Circuit breaker pattern"""

    def test_circuit_initially_closed(self):
        """Test circuit starts in CLOSED state"""
        cb = CircuitBreaker("test")
        assert cb.get_state() == "closed"
        assert cb.call_allowed()

    def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            error_rate_threshold=1.0  # Only open on failure_threshold, not error rate
        )
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.get_state() == "closed"

        cb.record_failure()
        assert cb.get_state() == "closed"  # Still closed at 2 failures

        cb.record_failure()
        assert cb.get_state() == "open"  # Opens at 3 failures
        assert not cb.call_allowed()

    def test_circuit_goes_half_open_after_timeout(self):
        """Test circuit goes to HALF_OPEN after recovery timeout"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_s=0  # Immediate recovery
        )
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.get_state() == "open"

        # Wait for timeout (0 seconds)
        assert cb.call_allowed()  # Should go to HALF_OPEN
        assert cb.get_state() == "half_open"

    def test_circuit_closes_after_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_s=0,
            success_threshold=1
        )
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.get_state() == "open"

        cb.call_allowed()  # Move to HALF_OPEN
        cb.record_success()
        assert cb.get_state() == "closed"

    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test circuit reopens if failure during recovery"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_s=0
        )
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        cb.call_allowed()  # Move to HALF_OPEN

        cb.record_failure()  # Failure during recovery
        assert cb.get_state() == "open"

    def test_sync_call_succeeds(self):
        """Test sync_call with successful function"""
        cb = CircuitBreaker("test")
        func = Mock(return_value="result")

        result = cb.sync_call(func)
        assert result == "result"
        assert cb.stats['successes'] == 1

    def test_sync_call_fails_open_circuit(self):
        """Test sync_call rejects when circuit open"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=3600)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        func = Mock()
        with pytest.raises(CircuitBreakerError):
            cb.sync_call(func)

        assert cb.stats['rejected'] == 1
        func.assert_not_called()

    def test_sync_call_with_fallback(self):
        """Test sync_call uses fallback when circuit open"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=3600)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        func = Mock()
        fallback = Mock(return_value="fallback result")

        result = cb.sync_call(func, on_circuit_open=fallback)
        assert result == "fallback result"
        func.assert_not_called()
        fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_call_succeeds(self):
        """Test async_call with successful function"""
        cb = CircuitBreaker("test")
        func = AsyncMock(return_value="async result")

        result = await cb.async_call(func)
        assert result == "async result"
        assert cb.stats['successes'] == 1

    @pytest.mark.asyncio
    async def test_async_call_fails_open(self):
        """Test async_call rejects when circuit open"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=3600)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        func = AsyncMock()
        with pytest.raises(CircuitBreakerError):
            await cb.async_call(func)

    def test_stats_tracking(self):
        """Test that stats are tracked correctly"""
        cb = CircuitBreaker("test")

        cb.record_success()
        cb.record_success()
        cb.record_failure()

        stats = cb.get_stats()
        assert stats['total_calls'] == 3
        assert stats['successes'] == 2
        assert stats['failures'] == 1


# ============================================================================
# WORKER 4: Integration Tests
# ============================================================================

class TestIntegratedRetryClient:
    """Test WORKER 4: Integrated retry + circuit breaker"""

    def test_health_report(self):
        """Test health report generation"""
        client = IntegratedRetryClient("test-api")

        # Record some activity
        client.sync_call(Mock(return_value="ok"))
        client.sync_call(Mock(return_value="ok"), fallback=Mock(return_value="fallback"))

        report = client.get_health_report()

        assert report['service'] == "test-api"
        assert 'circuit' in report
        assert 'retry' in report
        assert 'recent_requests' in report
        assert len(report['recent_requests']) > 0

    def test_sync_call_success(self):
        """Test sync_call with success"""
        client = IntegratedRetryClient("test-api")
        func = Mock(return_value="result")

        result = client.sync_call(func)
        assert result == "result"
        assert len(client.request_log) == 1
        assert client.request_log[0]['status'] == 'success'

    def test_sync_call_with_fallback(self):
        """Test sync_call with fallback on circuit open"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=3600)
        client = IntegratedRetryClient(
            "test-api",
            circuit_config=config
        )

        # Trigger circuit open
        client.circuit_breaker.record_failure()

        func = Mock()
        fallback = Mock(return_value="fallback")

        result = client.sync_call(func, fallback=fallback)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_async_call_success(self):
        """Test async_call with success"""
        client = IntegratedRetryClient("test-api")
        func = AsyncMock(return_value="async result")

        result = await client.async_call(func)
        assert result == "async result"
        assert len(client.request_log) == 1

    @pytest.mark.asyncio
    async def test_simulated_api_failures(self):
        """Test integration with simulated API failures and recovery"""
        config_retry = RetryConfig(
            max_retries=5,  # Allow 5 retries
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        )
        config_circuit = CircuitBreakerConfig(
            failure_threshold=20,  # High threshold to not open circuit during test
            recovery_timeout_s=0
        )

        client = IntegratedRetryClient(
            "test-api",
            retry_config=config_retry,
            circuit_config=config_circuit
        )

        # Simulate flaky API that fails first 3 times then succeeds
        call_count = 0

        async def unstable_api():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                if call_count % 2 == 0:
                    raise TimeoutError(f"Transient failure {call_count}")
                else:
                    raise ConnectionError(f"Connection error {call_count}")
            return "finally succeeded"

        result = await client.async_call(unstable_api)
        assert result == "finally succeeded"
        assert call_count == 4  # 3 failures + 1 success

    def test_save_health_report(self, tmp_path):
        """Test saving health report to file"""
        client = IntegratedRetryClient("test-api")
        client.sync_call(Mock(return_value="ok"))

        report_path = str(tmp_path / "health.json")
        client.save_health_report(report_path)

        import json
        with open(report_path) as f:
            saved = json.load(f)

        assert saved['service'] == "test-api"
        assert 'circuit' in saved
        assert 'retry' in saved


# ============================================================================
# Integration Scenario Tests
# ============================================================================

class TestIntegrationScenarios:
    """End-to-end integration scenarios"""

    def test_scenario_api_recovery(self):
        """Scenario: API fails then recovers"""
        config_retry = RetryConfig(
            max_retries=2,
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        )
        config_circuit = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_s=0,
            success_threshold=1
        )

        client = IntegratedRetryClient(
            "api.example.com",
            retry_config=config_retry,
            circuit_config=config_circuit
        )

        # Phase 1: API is down
        func_down = Mock(side_effect=ConnectionError("Service down"))
        client.circuit_breaker.record_failure()
        client.circuit_breaker.record_failure()

        assert client.circuit_breaker.get_state() == "open"

        # Phase 2: Try recovery
        assert client.circuit_breaker.call_allowed()
        assert client.circuit_breaker.get_state() == "half_open"

        # Phase 3: API recovers
        client.circuit_breaker.record_success()
        assert client.circuit_breaker.get_state() == "closed"

    def test_scenario_transient_vs_permanent_failures(self):
        """Scenario: Mix of transient and permanent failures"""
        wrapper = RetryWrapper()

        # Transient: retried
        transient = Mock(side_effect=[TimeoutError("timeout"), "success"])
        result = wrapper.sync_retry(transient)
        assert result == "success"

        # Permanent: not retried
        permanent = Mock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError):
            wrapper.sync_retry(permanent)

        assert permanent.call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_scenario_cascade_failure_recovery(self):
        """Scenario: Multiple retries with eventual success"""
        config = RetryConfig(
            max_retries=5,
            backoff=BackoffConfig(initial_delay_ms=10, use_jitter=False)
        )
        wrapper = RetryWrapper(config)

        attempt_count = 0

        async def flaky_api():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 4:
                if attempt_count % 2 == 0:
                    raise TimeoutError()
                else:
                    raise ConnectionError()
            return "recovered"

        result = await wrapper.async_retry(flaky_api)
        assert result == "recovered"
        assert attempt_count == 4
        assert wrapper.stats['successful_retries'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
