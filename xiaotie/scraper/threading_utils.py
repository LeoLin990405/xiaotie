"""
线程安全工具

提供 Session 管理、线程安全计数器、速率限制器等并发工具。
"""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp


@dataclass
class SessionConfig:
    """Session 配置"""

    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    verify_ssl: bool = True
    max_connections: int = 10


class SessionManager:
    """线程安全的 HTTP Session 管理器

    管理多个并发 HTTP 会话，支持连接池、自动重试、代理配置。
    """

    def __init__(self, config: Optional[SessionConfig] = None):
        self._config = config or SessionConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._request_count = ThreadSafeCounter()
        self._error_count = ThreadSafeCounter()

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP session"""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    connector = aiohttp.TCPConnector(
                        limit=self._config.max_connections,
                        ssl=self._config.verify_ssl,
                    )
                    timeout = aiohttp.ClientTimeout(total=self._config.timeout)
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers=self._config.headers,
                    )
        return self._session

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """发送 HTTP 请求，支持自动重试"""
        session = await self.get_session()
        last_error: Optional[Exception] = None

        if self._config.proxy:
            kwargs.setdefault("proxy", self._config.proxy)

        for attempt in range(self._config.max_retries):
            try:
                self._request_count.increment()
                resp = await session.request(method, url, **kwargs)
                return resp
            except Exception as e:
                last_error = e
                self._error_count.increment()
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay * (attempt + 1))

        raise last_error  # type: ignore[misc]

    async def get(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        return await self.request("POST", url, **kwargs)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "requests": self._request_count.value,
            "errors": self._error_count.value,
        }

    async def close(self):
        """关闭 session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


class ThreadSafeCounter:
    """线程安全计数器"""

    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()

    def increment(self, amount: int = 1) -> int:
        with self._lock:
            self._value += amount
            return self._value

    def decrement(self, amount: int = 1) -> int:
        with self._lock:
            self._value -= amount
            return self._value

    def reset(self) -> int:
        with self._lock:
            old = self._value
            self._value = 0
            return old

    @property
    def value(self) -> int:
        return self._value


class RateLimiter:
    """速率限制器（令牌桶算法）"""

    def __init__(self, rate: float, burst: int = 1):
        self._rate = rate  # 每秒允许的请求数
        self._burst = burst
        self._tokens = float(burst)
        self._last_time = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取一个令牌，必要时等待"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_time
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_time = now

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    @contextmanager
    def sync_acquire(self):
        """同步版本的速率限制"""
        now = time.monotonic()
        elapsed = now - self._last_time
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_time = now

        if self._tokens < 1.0:
            wait_time = (1.0 - self._tokens) / self._rate
            time.sleep(wait_time)
            self._tokens = 0.0
        else:
            self._tokens -= 1.0
        yield
