"""错误恢复与重试机制测试"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from xiaotie.retry import (
    AuthenticationError,
    BackoffStrategy,
    CircuitBreaker,
    CircuitBreakerOpen,
    ErrorCategory,
    InvalidRequestError,
    RateLimitError,
    RetryConfig,
    RetryState,
    RetryableError,
    RetryExhaustedError,
    ServerError,
    TimeoutError,
    async_retry,
)

class TestErrorCategory:
    """ErrorCategory 测试"""

    def test_all_categories(self):
        assert ErrorCategory.RETRYABLE.value == "retryable"
        assert ErrorCategory.NON_RETRYABLE.value == "non_retryable"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.TIMEOUT.value == "timeout"


class TestErrorTypes:
    """错误类型测试"""

    def test_rate_limit_error(self):
        error = RateLimitError("Too many requests", retry_after=30.0)
        assert str(error) == "Too many requests"
        assert error.retry_after == 30.0
        assert isinstance(error, RetryableError)

    def test_timeout_error(self):
        error = TimeoutError("Request timed out")
        assert isinstance(error, RetryableError)

    def test_server_error(self):
        error = ServerError("Internal server error", status_code=503)
        assert error.status_code == 503
        assert isinstance(error, RetryableError)

    def test_authentication_error(self):
        error = AuthenticationError("Invalid API key")
        assert not isinstance(error, RetryableError)


class TestRetryConfig:
    """RetryConfig 测试"""

    def test_default_config(self):
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff == BackoffStrategy.EXPONENTIAL
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_should_retry_retryable(self):
        config = RetryConfig()
        config.retryable_exceptions = (RetryableError,)
        assert config.should_retry(RateLimitError()) is True
        assert config.should_retry(TimeoutError()) is True
        assert config.should_retry(ServerError()) is True

    def test_should_retry_non_retryable(self):
        config = RetryConfig()
        config.retryable_exceptions = (RetryableError,)
        assert config.should_retry(AuthenticationError()) is False
        assert config.should_retry(InvalidRequestError()) is False
        assert config.should_retry(ValueError()) is False


class TestCalculateDelay:
    """calculate_delay 测试"""

    def test_constant_strategy(self):
        config = RetryConfig(backoff=BackoffStrategy.CONSTANT, initial_delay=2.0, jitter=False)
        assert config.calculate_delay(0) == 2.0
        assert config.calculate_delay(5) == 2.0

    def test_linear_strategy(self):
        config = RetryConfig(backoff=BackoffStrategy.LINEAR, initial_delay=1.0, jitter=False)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 3.0

    def test_exponential_strategy(self):
        config = RetryConfig(backoff=BackoffStrategy.EXPONENTIAL, initial_delay=1.0, jitter=False)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0

    def test_max_delay(self):
        config = RetryConfig(backoff=BackoffStrategy.EXPONENTIAL, initial_delay=1.0, max_delay=10.0, jitter=False)
        assert config.calculate_delay(10) == 10.0

    def test_jitter(self):
        config = RetryConfig(backoff=BackoffStrategy.CONSTANT, initial_delay=10.0, jitter=True)
        delays = [config.calculate_delay(0) for _ in range(10)]
        assert len(set(delays)) > 1
        for d in delays:
            assert 7.5 <= d <= 12.5


class TestCircuitBreaker:
    """CircuitBreaker 测试"""

    def test_initial_state(self):
        cb = CircuitBreaker()
        assert cb.allow_request()

    def test_open_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert not cb.allow_request()

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.allow_request()

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert not cb.allow_request()
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.State.HALF_OPEN
        assert cb.allow_request()


class TestAsyncRetryDecorator:
    """async_retry 测试"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        config = RetryConfig()

        @async_retry(config)
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        call_count = 0

        config = RetryConfig(initial_delay=0.01, retryable_exceptions=(ServerError,))

        @async_retry(config)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServerError()
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        config = RetryConfig(max_retries=2, initial_delay=0.01, retryable_exceptions=(ServerError,))

        @async_retry(config)
        async def always_fail():
            raise ServerError()

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()
        assert isinstance(exc_info.value.last_exception, ServerError)

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        call_count = 0
        config = RetryConfig(retryable_exceptions=(ServerError,))

        @async_retry(config)
        async def auth_error():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError()

        with pytest.raises(RetryExhaustedError) as exc_info:
            await auth_error()
        assert call_count == 1
        assert isinstance(exc_info.value.last_exception, AuthenticationError)

    @pytest.mark.asyncio
    async def test_with_circuit_breaker(self):
        cb = CircuitBreaker(failure_threshold=2)
        config = RetryConfig(max_retries=0, initial_delay=0.01, retryable_exceptions=(ServerError,))

        @async_retry(config, circuit_breaker=cb)
        async def always_fail():
            raise ServerError()

        with pytest.raises(RetryExhaustedError):
            await always_fail()

        with pytest.raises(RetryExhaustedError):
            await always_fail()

        with pytest.raises(CircuitBreakerOpen):
            await always_fail()
