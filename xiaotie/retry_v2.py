"""错误恢复机制

提供 LLM API 调用的错误处理和重试功能：
- 指数退避重试
- 错误分类 (可重试/不可重试)
- Provider 降级策略
- 断路器模式
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

T = TypeVar("T")


class ErrorCategory(Enum):
    """错误分类"""

    RETRYABLE = "retryable"  # 可重试错误
    NON_RETRYABLE = "non_retryable"  # 不可重试错误
    RATE_LIMIT = "rate_limit"  # 速率限制
    TIMEOUT = "timeout"  # 超时
    AUTH = "auth"  # 认证错误
    SERVER = "server"  # 服务器错误
    CLIENT = "client"  # 客户端错误
    UNKNOWN = "unknown"  # 未知错误


class BackoffStrategy(Enum):
    """退避策略"""

    LINEAR = "linear"  # 线性退避
    EXPONENTIAL = "exponential"  # 指数退避
    FIBONACCI = "fibonacci"  # 斐波那契退避
    CONSTANT = "constant"  # 固定间隔


# 常见错误类型
class RetryableError(Exception):
    """可重试错误基类"""

    pass


class RateLimitError(RetryableError):
    """速率限制错误"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(RetryableError):
    """超时错误"""

    pass


class ServerError(RetryableError):
    """服务器错误 (5xx)"""

    def __init__(self, message: str = "Server error", status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(Exception):
    """认证错误 (不可重试)"""

    pass


class InvalidRequestError(Exception):
    """无效请求错误 (不可重试)"""

    pass


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 3
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    jitter: bool = True  # 是否添加随机抖动
    retry_on: List[Type[Exception]] = field(
        default_factory=lambda: [RateLimitError, TimeoutError, ServerError]
    )
    fallback_provider: Optional[str] = None  # 降级 Provider

    def should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        return any(isinstance(error, err_type) for err_type in self.retry_on)


@dataclass
class RetryState:
    """重试状态"""

    attempt: int = 0
    total_delay: float = 0.0
    errors: List[Exception] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        """已用时间"""
        return time.time() - self.start_time


def calculate_delay(
    attempt: int,
    strategy: BackoffStrategy,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> float:
    """计算退避延迟

    Args:
        attempt: 当前尝试次数 (从 0 开始)
        strategy: 退避策略
        base_delay: 基础延迟
        max_delay: 最大延迟
        jitter: 是否添加随机抖动

    Returns:
        延迟时间（秒）
    """
    if strategy == BackoffStrategy.CONSTANT:
        delay = base_delay
    elif strategy == BackoffStrategy.LINEAR:
        delay = base_delay * (attempt + 1)
    elif strategy == BackoffStrategy.EXPONENTIAL:
        delay = base_delay * (2**attempt)
    elif strategy == BackoffStrategy.FIBONACCI:
        # 斐波那契数列
        a, b = 1, 1
        for _ in range(attempt):
            a, b = b, a + b
        delay = base_delay * a
    else:
        delay = base_delay

    # 限制最大延迟
    delay = min(delay, max_delay)

    # 添加随机抖动 (±25%)
    if jitter:
        delay = delay * (0.75 + random.random() * 0.5)

    return delay


def classify_error(error: Exception) -> ErrorCategory:
    """分类错误

    Args:
        error: 异常对象

    Returns:
        错误分类
    """
    if isinstance(error, RateLimitError):
        return ErrorCategory.RATE_LIMIT
    elif isinstance(error, TimeoutError):
        return ErrorCategory.TIMEOUT
    elif isinstance(error, AuthenticationError):
        return ErrorCategory.AUTH
    elif isinstance(error, ServerError):
        return ErrorCategory.SERVER
    elif isinstance(error, InvalidRequestError):
        return ErrorCategory.CLIENT
    elif isinstance(error, RetryableError):
        return ErrorCategory.RETRYABLE
    else:
        return ErrorCategory.UNKNOWN


class CircuitBreaker:
    """断路器

    防止对故障服务的持续调用：
    - CLOSED: 正常状态，允许调用
    - OPEN: 断开状态，拒绝调用
    - HALF_OPEN: 半开状态，允许少量调用测试
    """

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
        """
        Args:
            failure_threshold: 触发断开的连续失败次数
            recovery_timeout: 断开后恢复尝试的超时时间
            half_open_max_calls: 半开状态允许的最大调用次数
        """
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
        """获取当前状态"""
        if self._state == self.State.OPEN:
            # 检查是否应该转换到半开状态
            if self._last_failure_time and time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.State.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == self.State.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == self.State.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == self.State.HALF_OPEN

    def allow_request(self) -> bool:
        """检查是否允许请求"""
        state = self.state
        if state == self.State.CLOSED:
            return True
        elif state == self.State.OPEN:
            return False
        else:  # HALF_OPEN
            return self._half_open_calls < self.half_open_max_calls

    def record_success(self) -> None:
        """记录成功"""
        if self._state == self.State.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                # 恢复到关闭状态
                self._state = self.State.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.State.HALF_OPEN:
            # 半开状态下失败，立即断开
            self._state = self.State.OPEN
            self._half_open_calls = 0
        elif self._failure_count >= self.failure_threshold:
            # 达到阈值，断开
            self._state = self.State.OPEN

    def reset(self) -> None:
        """重置断路器"""
        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


class CircuitBreakerOpen(Exception):
    """断路器打开异常"""

    pass


async def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig,
    *args,
    **kwargs,
) -> T:
    """带退避的重试执行

    Args:
        func: 要执行的函数（同步或异步）
        config: 重试配置
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次失败的异常
    """
    state = RetryState()

    while state.attempt <= config.max_retries:
        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        except Exception as e:
            state.errors.append(e)

            # 检查是否应该重试
            if not config.should_retry(e) or state.attempt >= config.max_retries:
                raise

            # 计算延迟
            delay = calculate_delay(
                state.attempt,
                config.backoff,
                config.base_delay,
                config.max_delay,
                config.jitter,
            )

            # 如果是速率限制错误，使用服务器建议的延迟
            if isinstance(e, RateLimitError) and e.retry_after:
                delay = max(delay, e.retry_after)

            state.total_delay += delay
            state.attempt += 1

            # 等待
            await asyncio.sleep(delay)

    # 不应该到达这里
    raise state.errors[-1] if state.errors else RuntimeError("Retry failed")


class RetryExecutor:
    """重试执行器

    提供更高级的重试功能，包括断路器和降级。

    使用示例:
    ```python
    executor = RetryExecutor(
        config=RetryConfig(max_retries=3),
        circuit_breaker=CircuitBreaker(),
    )

    result = await executor.execute(
        llm.generate,
        messages=messages,
    )
    ```
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        fallback: Optional[Callable[..., T]] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        on_success: Optional[Callable[[T], None]] = None,
        on_failure: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Args:
            config: 重试配置
            circuit_breaker: 断路器
            fallback: 降级函数
            on_retry: 重试回调
            on_success: 成功回调
            on_failure: 失败回调
        """
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker
        self.fallback = fallback
        self.on_retry = on_retry
        self.on_success = on_success
        self.on_failure = on_failure

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """执行函数，带重试和断路器

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpen: 断路器打开
            Exception: 最后一次失败的异常
        """
        # 检查断路器
        if self.circuit_breaker and not self.circuit_breaker.allow_request():
            if self.fallback:
                return await self._execute_fallback(*args, **kwargs)
            raise CircuitBreakerOpen("Circuit breaker is open")

        state = RetryState()

        while state.attempt <= self.config.max_retries:
            try:
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # 记录成功
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                if self.on_success:
                    self.on_success(result)

                return result

            except Exception as e:
                state.errors.append(e)

                # 记录失败
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()

                # 检查是否应该重试
                if not self.config.should_retry(e) or state.attempt >= self.config.max_retries:
                    if self.on_failure:
                        self.on_failure(e)

                    # 尝试降级
                    if self.fallback:
                        return await self._execute_fallback(*args, **kwargs)
                    raise

                # 回调
                if self.on_retry:
                    self.on_retry(e, state.attempt)

                # 计算延迟
                delay = calculate_delay(
                    state.attempt,
                    self.config.backoff,
                    self.config.base_delay,
                    self.config.max_delay,
                    self.config.jitter,
                )

                if isinstance(e, RateLimitError) and e.retry_after:
                    delay = max(delay, e.retry_after)

                state.total_delay += delay
                state.attempt += 1

                await asyncio.sleep(delay)

        # 不应该到达这里
        raise state.errors[-1] if state.errors else RuntimeError("Retry failed")

    async def _execute_fallback(self, *args, **kwargs) -> T:
        """执行降级函数"""
        if asyncio.iscoroutinefunction(self.fallback):
            return await self.fallback(*args, **kwargs)
        return self.fallback(*args, **kwargs)
