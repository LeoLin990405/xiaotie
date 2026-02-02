"""错误恢复机制测试"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from xiaotie.retry_v2 import (
    AuthenticationError,
    BackoffStrategy,
    CircuitBreaker,
    CircuitBreakerOpen,
    ErrorCategory,
    InvalidRequestError,
    RateLimitError,
    RetryConfig,
    RetryExecutor,
    RetryState,
    RetryableError,
    ServerError,
    TimeoutError,
    calculate_delay,
    classify_error,
    retry_with_backoff,
)


class TestErrorCategory:
    """ErrorCategory 测试"""

    def test_all_categories(self):
        """测试所有错误分类"""
        assert ErrorCategory.RETRYABLE.value == "retryable"
        assert ErrorCategory.NON_RETRYABLE.value == "non_retryable"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.TIMEOUT.value == "timeout"


class TestBackoffStrategy:
    """BackoffStrategy 测试"""

    def test_all_strategies(self):
        """测试所有退避策略"""
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.FIBONACCI.value == "fibonacci"
        assert BackoffStrategy.CONSTANT.value == "constant"


class TestErrorTypes:
    """错误类型测试"""

    def test_rate_limit_error(self):
        """测试速率限制错误"""
        error = RateLimitError("Too many requests", retry_after=30.0)
        assert str(error) == "Too many requests"
        assert error.retry_after == 30.0
        assert isinstance(error, RetryableError)

    def test_timeout_error(self):
        """测试超时错误"""
        error = TimeoutError("Request timed out")
        assert isinstance(error, RetryableError)

    def test_server_error(self):
        """测试服务器错误"""
        error = ServerError("Internal server error", status_code=503)
        assert error.status_code == 503
        assert isinstance(error, RetryableError)

    def test_authentication_error(self):
        """测试认证错误"""
        error = AuthenticationError("Invalid API key")
        assert not isinstance(error, RetryableError)

    def test_invalid_request_error(self):
        """测试无效请求错误"""
        error = InvalidRequestError("Bad request")
        assert not isinstance(error, RetryableError)


class TestRetryConfig:
    """RetryConfig 测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.backoff == BackoffStrategy.EXPONENTIAL
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_should_retry_retryable(self):
        """测试可重试错误"""
        config = RetryConfig()
        assert config.should_retry(RateLimitError()) is True
        assert config.should_retry(TimeoutError()) is True
        assert config.should_retry(ServerError()) is True

    def test_should_retry_non_retryable(self):
        """测试不可重试错误"""
        config = RetryConfig()
        assert config.should_retry(AuthenticationError()) is False
        assert config.should_retry(InvalidRequestError()) is False
        assert config.should_retry(ValueError()) is False


class TestRetryState:
    """RetryState 测试"""

    def test_initial_state(self):
        """测试初始状态"""
        state = RetryState()
        assert state.attempt == 0
        assert state.total_delay == 0.0
        assert state.errors == []

    def test_elapsed_time(self):
        """测试已用时间"""
        state = RetryState()
        time.sleep(0.1)
        assert state.elapsed_time >= 0.1


class TestCalculateDelay:
    """calculate_delay 测试"""

    def test_constant_strategy(self):
        """测试固定间隔策略"""
        delay = calculate_delay(0, BackoffStrategy.CONSTANT, base_delay=2.0, jitter=False)
        assert delay == 2.0
        delay = calculate_delay(5, BackoffStrategy.CONSTANT, base_delay=2.0, jitter=False)
        assert delay == 2.0

    def test_linear_strategy(self):
        """测试线性退避策略"""
        delay = calculate_delay(0, BackoffStrategy.LINEAR, base_delay=1.0, jitter=False)
        assert delay == 1.0
        delay = calculate_delay(1, BackoffStrategy.LINEAR, base_delay=1.0, jitter=False)
        assert delay == 2.0
        delay = calculate_delay(2, BackoffStrategy.LINEAR, base_delay=1.0, jitter=False)
        assert delay == 3.0

    def test_exponential_strategy(self):
        """测试指数退避策略"""
        delay = calculate_delay(0, BackoffStrategy.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert delay == 1.0
        delay = calculate_delay(1, BackoffStrategy.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert delay == 2.0
        delay = calculate_delay(2, BackoffStrategy.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert delay == 4.0
        delay = calculate_delay(3, BackoffStrategy.EXPONENTIAL, base_delay=1.0, jitter=False)
        assert delay == 8.0

    def test_fibonacci_strategy(self):
        """测试斐波那契退避策略"""
        delay = calculate_delay(0, BackoffStrategy.FIBONACCI, base_delay=1.0, jitter=False)
        assert delay == 1.0
        delay = calculate_delay(1, BackoffStrategy.FIBONACCI, base_delay=1.0, jitter=False)
        assert delay == 1.0
        delay = calculate_delay(2, BackoffStrategy.FIBONACCI, base_delay=1.0, jitter=False)
        assert delay == 2.0
        delay = calculate_delay(3, BackoffStrategy.FIBONACCI, base_delay=1.0, jitter=False)
        assert delay == 3.0
        delay = calculate_delay(4, BackoffStrategy.FIBONACCI, base_delay=1.0, jitter=False)
        assert delay == 5.0

    def test_max_delay(self):
        """测试最大延迟限制"""
        delay = calculate_delay(10, BackoffStrategy.EXPONENTIAL, base_delay=1.0, max_delay=10.0, jitter=False)
        assert delay == 10.0

    def test_jitter(self):
        """测试随机抖动"""
        delays = [calculate_delay(0, BackoffStrategy.CONSTANT, base_delay=10.0, jitter=True) for _ in range(10)]
        # 抖动应该产生不同的值
        assert len(set(delays)) > 1
        # 所有值应该在 ±25% 范围内
        for d in delays:
            assert 7.5 <= d <= 12.5


class TestClassifyError:
    """classify_error 测试"""

    def test_classify_rate_limit(self):
        """测试分类速率限制错误"""
        assert classify_error(RateLimitError()) == ErrorCategory.RATE_LIMIT

    def test_classify_timeout(self):
        """测试分类超时错误"""
        assert classify_error(TimeoutError()) == ErrorCategory.TIMEOUT

    def test_classify_auth(self):
        """测试分类认证错误"""
        assert classify_error(AuthenticationError()) == ErrorCategory.AUTH

    def test_classify_server(self):
        """测试分类服务器错误"""
        assert classify_error(ServerError()) == ErrorCategory.SERVER

    def test_classify_client(self):
        """测试分类客户端错误"""
        assert classify_error(InvalidRequestError()) == ErrorCategory.CLIENT

    def test_classify_unknown(self):
        """测试分类未知错误"""
        assert classify_error(ValueError()) == ErrorCategory.UNKNOWN


class TestCircuitBreaker:
    """CircuitBreaker 测试"""

    def test_initial_state(self):
        """测试初始状态"""
        cb = CircuitBreaker()
        assert cb.is_closed
        assert not cb.is_open
        assert cb.allow_request()

    def test_open_after_failures(self):
        """测试失败后断开"""
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open
        assert not cb.allow_request()

    def test_success_resets_failure_count(self):
        """测试成功重置失败计数"""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # 应该仍然关闭，因为成功重置了计数
        assert cb.is_closed

    def test_half_open_after_timeout(self):
        """测试超时后半开"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.is_open
        time.sleep(0.15)
        assert cb.is_half_open
        assert cb.allow_request()

    def test_half_open_to_closed(self):
        """测试半开到关闭"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.is_half_open
        cb.record_success()
        cb.record_success()
        assert cb.is_closed

    def test_half_open_to_open(self):
        """测试半开到断开"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.is_half_open
        cb.record_failure()
        assert cb.is_open

    def test_reset(self):
        """测试重置"""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.is_open
        cb.reset()
        assert cb.is_closed


class TestRetryWithBackoff:
    """retry_with_backoff 测试"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """测试第一次成功"""
        async def success_func():
            return "success"

        result = await retry_with_backoff(success_func, RetryConfig())
        assert result == "success"

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """测试重试后成功"""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ServerError()
            return "success"

        config = RetryConfig(base_delay=0.01)
        result = await retry_with_backoff(fail_then_succeed, config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        async def always_fail():
            raise ServerError()

        config = RetryConfig(max_retries=2, base_delay=0.01)
        with pytest.raises(ServerError):
            await retry_with_backoff(always_fail, config)

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """测试不可重试错误"""
        call_count = 0

        async def auth_error():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError()

        config = RetryConfig()
        with pytest.raises(AuthenticationError):
            await retry_with_backoff(auth_error, config)
        assert call_count == 1  # 不应该重试

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after(self):
        """测试速率限制的 retry_after"""
        call_count = 0
        start_time = time.time()

        async def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0.1)
            return "success"

        config = RetryConfig(base_delay=0.01)
        result = await retry_with_backoff(rate_limited, config)
        elapsed = time.time() - start_time
        assert result == "success"
        assert elapsed >= 0.1  # 应该等待 retry_after 时间


class TestRetryExecutor:
    """RetryExecutor 测试"""

    @pytest.mark.asyncio
    async def test_success(self):
        """测试成功执行"""
        executor = RetryExecutor()
        async def success_func():
            return "success"
        result = await executor.execute(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_circuit_breaker(self):
        """测试带断路器"""
        cb = CircuitBreaker(failure_threshold=3)
        executor = RetryExecutor(
            config=RetryConfig(max_retries=0, base_delay=0.01),  # 不重试
            circuit_breaker=cb,
        )

        async def always_fail():
            raise ServerError()

        # 第一次失败
        with pytest.raises(ServerError):
            await executor.execute(always_fail)

        # 第二次失败
        with pytest.raises(ServerError):
            await executor.execute(always_fail)

        # 第三次失败，断路器打开
        with pytest.raises(ServerError):
            await executor.execute(always_fail)

        # 断路器打开，拒绝请求
        with pytest.raises(CircuitBreakerOpen):
            await executor.execute(always_fail)

    @pytest.mark.asyncio
    async def test_with_fallback(self):
        """测试带降级"""
        async def fallback_func():
            return "fallback"

        executor = RetryExecutor(
            config=RetryConfig(max_retries=1, base_delay=0.01),
            fallback=fallback_func,
        )

        async def always_fail():
            raise ServerError()

        result = await executor.execute(always_fail)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_callbacks(self):
        """测试回调"""
        retry_calls = []
        success_calls = []
        failure_calls = []

        executor = RetryExecutor(
            config=RetryConfig(max_retries=2, base_delay=0.01),
            on_retry=lambda e, a: retry_calls.append((e, a)),
            on_success=lambda r: success_calls.append(r),
            on_failure=lambda e: failure_calls.append(e),
        )

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ServerError()
            return "success"

        result = await executor.execute(fail_then_succeed)
        assert result == "success"
        assert len(retry_calls) == 1
        assert len(success_calls) == 1
        assert len(failure_calls) == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_fallback(self):
        """测试断路器打开时使用降级"""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()  # 手动打开断路器

        async def fallback_func():
            return "fallback"

        executor = RetryExecutor(
            circuit_breaker=cb,
            fallback=fallback_func,
        )

        async def main_func():
            return "main"

        result = await executor.execute(main_func)
        assert result == "fallback"
