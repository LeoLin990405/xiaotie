"""重试与错误恢复机制

提供统一的 API 调用的错误处理和重试功能：
- 指数退避、线性、斐波那契等重试策略
- 错误分类 (可重试/不可重试)
- 断路器模式
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Type, TypeVar

T = TypeVar("T")


class ErrorCategory(Enum):
    """错误分类"""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTH = "auth"
    SERVER = "server"
    CLIENT = "client"
    UNKNOWN = "unknown"


class BackoffStrategy(Enum):
    """退避策略"""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    CONSTANT = "constant"


# 常见错误类型
class RetryableError(Exception):
    """可重试错误基类"""

    pass


class RateLimitError(RetryableError):
    """速率限制错误"""

    def __init__(self, message: str = "请求频率超限", retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(RetryableError):
    """超时错误"""

    pass


class ServerError(RetryableError):
    """服务器错误 (5xx)"""

    def __init__(self, message: str = "服务器错误", status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(Exception):
    """认证错误 (不可重试)"""

    pass


class InvalidRequestError(Exception):
    """无效请求错误 (不可重试)"""

    pass


class RetryExhaustedError(Exception):
    """重试耗尽异常"""

    def __init__(self, last_exception: Exception, attempts: int):
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(f"重试 {attempts} 次后失败: {last_exception}")


@dataclass
class RetryConfig:
    """重试配置"""

    enabled: bool = True
    max_retries: int = 3
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    exponential_base: float = 2.0
    jitter: bool = True  # 是否添加随机抖动
    retryable_exceptions: tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))

    def should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        return self.enabled and any(
            isinstance(error, err_type) for err_type in self.retryable_exceptions
        )

    def calculate_delay(self, attempt: int) -> float:
        """计算退避延迟"""
        if self.backoff == BackoffStrategy.CONSTANT:
            delay = self.initial_delay
        elif self.backoff == BackoffStrategy.LINEAR:
            delay = self.initial_delay * (attempt + 1)
        elif self.backoff == BackoffStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.exponential_base**attempt)
        elif self.backoff == BackoffStrategy.FIBONACCI:
            a, b = 1, 1
            for _ in range(attempt):
                a, b = b, a + b
            delay = self.initial_delay * a
        else:
            delay = self.initial_delay

        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * (0.75 + random.random() * 0.5)

        return delay


@dataclass
class RetryState:
    """重试状态"""

    attempt: int = 0
    total_delay: float = 0.0
    errors: List[Exception] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time


class CircuitBreakerOpen(Exception):
    """断路器打开异常"""

    pass


class CircuitBreaker:
    """断路器"""

    class State(Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> State:
        if self._state == self.State.OPEN:
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = self.State.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        state = self.state
        if state == self.State.CLOSED:
            return True
        elif state == self.State.OPEN:
            return False
        else:
            return self._half_open_calls < self.half_open_max_calls

    def record_success(self) -> None:
        if self._state == self.State.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = self.State.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.State.HALF_OPEN:
            self._state = self.State.OPEN
            self._half_open_calls = 0
        elif self._failure_count >= self.failure_threshold:
            self._state = self.State.OPEN

    def reset(self) -> None:
        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


def async_retry(
    config: RetryConfig,
    on_retry: Callable[[Exception, int], None] | None = None,
    circuit_breaker: CircuitBreaker | None = None,
):
    """异步重试装饰器，集成断路器模式"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not config.enabled:
                if circuit_breaker and not circuit_breaker.allow_request():
                    raise CircuitBreakerOpen("Circuit breaker is open")
                try:
                    result = await func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result
                except Exception:
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    raise

            if circuit_breaker and not circuit_breaker.allow_request():
                raise CircuitBreakerOpen("Circuit breaker is open")

            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result

                except Exception as e:
                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    last_exception = e
                    if not config.should_retry(e) or attempt >= config.max_retries:
                        raise RetryExhaustedError(e, attempt + 1)

                    delay = config.calculate_delay(attempt)
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = max(delay, e.retry_after)

                    if on_retry:
                        on_retry(e, attempt + 1)
                    await asyncio.sleep(delay)

            raise RetryExhaustedError(last_exception, config.max_retries + 1)

        return wrapper

    return decorator
