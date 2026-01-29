"""重试机制"""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import Callable, Type, Tuple


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
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )

    def calculate_delay(self, attempt: int) -> float:
        """计算指数退避延迟"""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


def async_retry(
    config: RetryConfig,
    on_retry: Callable[[Exception, int], None] | None = None
):
    """异步重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not config.enabled:
                return await func(*args, **kwargs)

            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt >= config.max_retries:
                        raise RetryExhaustedError(e, attempt + 1)

                    delay = config.calculate_delay(attempt)
                    if on_retry:
                        on_retry(e, attempt + 1)
                    await asyncio.sleep(delay)

            raise RetryExhaustedError(last_exception, config.max_retries + 1)
        return wrapper
    return decorator
