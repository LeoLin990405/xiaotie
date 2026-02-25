"""线程工具单元测试

测试覆盖：
- SessionConfig 配置
- SessionManager HTTP会话管理
  - 创建/关闭 session
  - 请求重试
  - 统计信息
  - 上下文管理器
- ThreadSafeCounter 线程安全计数器
  - increment/decrement/reset
  - 并发安全性
- RateLimiter 速率限制器
  - 令牌桶算法
  - 异步/同步获取
"""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.scraper.threading_utils import (
    RateLimiter,
    SessionConfig,
    SessionManager,
    ThreadSafeCounter,
)


# ============================================================
# SessionConfig 测试
# ============================================================


class TestSessionConfig:

    def test_defaults(self):
        c = SessionConfig()
        assert c.timeout == 30.0
        assert c.max_retries == 3
        assert c.retry_delay == 1.0
        assert c.headers == {}
        assert c.proxy is None
        assert c.verify_ssl is True
        assert c.max_connections == 10

    def test_custom(self):
        c = SessionConfig(
            timeout=60.0,
            max_retries=5,
            proxy="http://proxy:8080",
            headers={"X-Custom": "val"},
        )
        assert c.timeout == 60.0
        assert c.max_retries == 5
        assert c.proxy == "http://proxy:8080"
        assert c.headers["X-Custom"] == "val"


# ============================================================
# ThreadSafeCounter 测试
# ============================================================


class TestThreadSafeCounter:

    def test_initial_value(self):
        c = ThreadSafeCounter()
        assert c.value == 0

    def test_initial_custom(self):
        c = ThreadSafeCounter(initial=10)
        assert c.value == 10

    def test_increment(self):
        c = ThreadSafeCounter()
        result = c.increment()
        assert result == 1
        assert c.value == 1

    def test_increment_amount(self):
        c = ThreadSafeCounter()
        c.increment(5)
        assert c.value == 5

    def test_decrement(self):
        c = ThreadSafeCounter(initial=10)
        result = c.decrement()
        assert result == 9
        assert c.value == 9

    def test_decrement_amount(self):
        c = ThreadSafeCounter(initial=10)
        c.decrement(3)
        assert c.value == 7

    def test_reset(self):
        c = ThreadSafeCounter(initial=5)
        c.increment(10)
        old = c.reset()
        assert old == 15
        assert c.value == 0

    def test_thread_safety(self):
        """多线程并发递增测试"""
        c = ThreadSafeCounter()
        num_threads = 10
        increments_per_thread = 100

        def worker():
            for _ in range(increments_per_thread):
                c.increment()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert c.value == num_threads * increments_per_thread


# ============================================================
# SessionManager 测试
# ============================================================


class TestSessionManager:

    def test_init_default(self):
        sm = SessionManager()
        assert sm._session is None
        assert sm.stats["requests"] == 0
        assert sm.stats["errors"] == 0

    def test_init_custom_config(self):
        config = SessionConfig(timeout=60.0, max_connections=20)
        sm = SessionManager(config)
        assert sm._config.timeout == 60.0
        assert sm._config.max_connections == 20

    @pytest.mark.asyncio
    async def test_get_session_creates_session(self):
        sm = SessionManager()
        with patch("xiaotie.scraper.threading_utils.aiohttp") as mock_aiohttp:
            mock_session = MagicMock()
            mock_session.closed = False
            mock_aiohttp.ClientSession.return_value = mock_session
            mock_aiohttp.TCPConnector.return_value = MagicMock()
            mock_aiohttp.ClientTimeout.return_value = MagicMock()

            session = await sm.get_session()
            assert session is not None

    @pytest.mark.asyncio
    async def test_close_when_no_session(self):
        sm = SessionManager()
        await sm.close()  # should not raise

    @pytest.mark.asyncio
    async def test_context_manager(self):
        sm = SessionManager()
        async with sm:
            pass  # should not raise

    def test_stats_initial(self):
        sm = SessionManager()
        stats = sm.stats
        assert stats["requests"] == 0
        assert stats["errors"] == 0


class TestSessionManagerRequest:
    """SessionManager.request() 方法测试（含重试逻辑）"""

    @pytest.mark.asyncio
    async def test_request_success(self):
        """成功请求应返回响应并递增计数"""
        config = SessionConfig(max_retries=3, retry_delay=0.01)
        sm = SessionManager(config)
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.closed = False
        sm._session = mock_session

        resp = await sm.request("GET", "https://example.com")
        assert resp is mock_response
        assert sm.stats["requests"] == 1
        assert sm.stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_request_retry_then_success(self):
        """前两次失败，第三次成功 → 应返回响应"""
        config = SessionConfig(max_retries=3, retry_delay=0.01)
        sm = SessionManager(config)
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(
            side_effect=[Exception("fail1"), Exception("fail2"), mock_response]
        )
        mock_session.closed = False
        sm._session = mock_session

        resp = await sm.request("GET", "https://example.com")
        assert resp is mock_response
        assert sm.stats["requests"] == 3
        assert sm.stats["errors"] == 2

    @pytest.mark.asyncio
    async def test_request_all_retries_exhausted(self):
        """所有重试都失败 → 应抛出最后一个异常"""
        config = SessionConfig(max_retries=2, retry_delay=0.01)
        sm = SessionManager(config)
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(
            side_effect=[Exception("err1"), Exception("err2")]
        )
        mock_session.closed = False
        sm._session = mock_session

        with pytest.raises(Exception, match="err2"):
            await sm.request("GET", "https://example.com")
        assert sm.stats["requests"] == 2
        assert sm.stats["errors"] == 2

    @pytest.mark.asyncio
    async def test_request_with_proxy(self):
        """配置了 proxy 时应自动添加到 kwargs"""
        config = SessionConfig(proxy="http://proxy:8080", max_retries=1, retry_delay=0.01)
        sm = SessionManager(config)
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.closed = False
        sm._session = mock_session

        await sm.request("GET", "https://example.com")
        call_kwargs = mock_session.request.call_args
        assert call_kwargs[1].get("proxy") == "http://proxy:8080"

    @pytest.mark.asyncio
    async def test_get_shortcut(self):
        """get() 应调用 request('GET', ...)"""
        config = SessionConfig(max_retries=1, retry_delay=0.01)
        sm = SessionManager(config)
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.closed = False
        sm._session = mock_session

        resp = await sm.get("https://example.com")
        assert resp is mock_response
        mock_session.request.assert_called_once_with("GET", "https://example.com")

    @pytest.mark.asyncio
    async def test_post_shortcut(self):
        """post() 应调用 request('POST', ...)"""
        config = SessionConfig(max_retries=1, retry_delay=0.01)
        sm = SessionManager(config)
        mock_response = MagicMock()
        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.closed = False
        sm._session = mock_session

        resp = await sm.post("https://example.com", data="body")
        assert resp is mock_response
        mock_session.request.assert_called_once_with(
            "POST", "https://example.com", data="body"
        )

    @pytest.mark.asyncio
    async def test_close_active_session(self):
        """关闭活跃 session"""
        sm = SessionManager()
        mock_session = AsyncMock()
        mock_session.closed = False
        sm._session = mock_session

        await sm.close()
        mock_session.close.assert_called_once()
        assert sm._session is None


# ============================================================
# RateLimiter 测试
# ============================================================


class TestRateLimiter:

    def test_init(self):
        rl = RateLimiter(rate=10.0, burst=5)
        assert rl._rate == 10.0
        assert rl._burst == 5

    @pytest.mark.asyncio
    async def test_acquire_first_token(self):
        """首次获取应立即成功（有初始令牌）"""
        rl = RateLimiter(rate=10.0, burst=5)
        start = time.monotonic()
        await rl.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # should be nearly instant

    @pytest.mark.asyncio
    async def test_acquire_burst(self):
        """burst 个令牌应可快速获取"""
        rl = RateLimiter(rate=100.0, burst=3)
        for _ in range(3):
            await rl.acquire()
        # all 3 should succeed quickly

    def test_sync_acquire(self):
        rl = RateLimiter(rate=100.0, burst=3)
        with rl.sync_acquire():
            pass  # should not raise

    @pytest.mark.asyncio
    async def test_rate_limiting_effect(self):
        """超过 burst 后应有延迟"""
        rl = RateLimiter(rate=1000.0, burst=1)
        # 消耗初始令牌
        await rl.acquire()
        # 第二次应该需要等待（但 rate=1000 所以很快）
        start = time.monotonic()
        await rl.acquire()
        elapsed = time.monotonic() - start
        # 高速率下延迟应很小
        assert elapsed < 1.0
