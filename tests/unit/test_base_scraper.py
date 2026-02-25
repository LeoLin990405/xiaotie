"""BaseScraper 单元测试

测试覆盖：
- ScrapeResult 数据类
- ScrapeStatus 枚举
- ScraperConfig 配置
- ProgressTracker 进度跟踪
- BaseScraper 核心功能
  - 初始化与配置
  - validate() 3次验证
  - scrape() 单URL抓取
  - scrape_many() 并发抓取
  - cancel() 取消
  - 上下文管理器
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.scraper.base_scraper import (
    BaseScraper,
    ProgressTracker,
    ScraperConfig,
    ScrapeResult,
    ScrapeStatus,
)


# ============================================================
# ScrapeStatus 测试
# ============================================================


class TestScrapeStatus:

    def test_all_statuses(self):
        assert ScrapeStatus.PENDING.value == "pending"
        assert ScrapeStatus.RUNNING.value == "running"
        assert ScrapeStatus.VALIDATING.value == "validating"
        assert ScrapeStatus.COMPLETED.value == "completed"
        assert ScrapeStatus.FAILED.value == "failed"
        assert ScrapeStatus.CANCELLED.value == "cancelled"


# ============================================================
# ScrapeResult 测试
# ============================================================


class TestScrapeResult:

    def test_default_values(self):
        r = ScrapeResult(url="https://example.com")
        assert r.url == "https://example.com"
        assert r.data is None
        assert r.status == ScrapeStatus.PENDING
        assert r.attempts == 0
        assert r.validation_passes == 0
        assert r.content_hash == ""
        assert r.error is None

    def test_duration_none_when_incomplete(self):
        r = ScrapeResult(url="https://example.com")
        assert r.duration is None

    def test_duration_calculated(self):
        now = datetime.now()
        r = ScrapeResult(
            url="https://example.com",
            started_at=now,
            completed_at=now + timedelta(seconds=5),
        )
        assert abs(r.duration - 5.0) < 0.01

    def test_is_valid_false(self):
        r = ScrapeResult(url="https://example.com", validation_passes=2)
        assert r.is_valid is False

    def test_is_valid_true(self):
        r = ScrapeResult(url="https://example.com", validation_passes=3)
        assert r.is_valid is True

    def test_metadata_default_empty(self):
        r = ScrapeResult(url="https://example.com")
        assert r.metadata == {}

    def test_metadata_custom(self):
        r = ScrapeResult(url="https://example.com", metadata={"key": "val"})
        assert r.metadata["key"] == "val"


# ============================================================
# ScraperConfig 测试
# ============================================================


class TestScraperConfig:

    def test_defaults(self):
        c = ScraperConfig()
        assert c.max_workers == 5
        assert c.validation_rounds == 3
        assert c.validation_interval == 2.0
        assert c.rate_limit == 5.0
        assert c.rate_burst == 10
        assert c.timeout == 30.0
        assert c.max_retries == 3
        assert c.retry_delay == 1.0
        assert "XiaoTie" in c.user_agent
        assert c.proxy is None
        assert c.verify_ssl is True
        assert c.headers == {}

    def test_custom_values(self):
        c = ScraperConfig(
            max_workers=10,
            timeout=60.0,
            proxy="http://proxy:8080",
            headers={"X-Custom": "value"},
        )
        assert c.max_workers == 10
        assert c.timeout == 60.0
        assert c.proxy == "http://proxy:8080"
        assert c.headers["X-Custom"] == "value"


# ============================================================
# ProgressTracker 测试
# ============================================================


class TestProgressTracker:

    def test_init(self):
        p = ProgressTracker(total=10)
        assert p.total == 10
        assert p.completed == 0
        assert p.failed == 0
        assert p.skipped == 0

    def test_update_completed(self):
        p = ProgressTracker(total=5)
        p.update("completed")
        assert p.completed == 1
        assert p.processed == 1

    def test_update_failed(self):
        p = ProgressTracker(total=5)
        p.update("failed")
        assert p.failed == 1

    def test_update_skipped(self):
        p = ProgressTracker(total=5)
        p.update("skipped")
        assert p.skipped == 1

    def test_processed(self):
        p = ProgressTracker(total=10)
        p.update("completed")
        p.update("failed")
        p.update("skipped")
        assert p.processed == 3

    def test_progress_zero_total(self):
        p = ProgressTracker(total=0)
        assert p.progress == 0.0

    def test_progress_calculation(self):
        p = ProgressTracker(total=4)
        p.update("completed")
        p.update("completed")
        assert abs(p.progress - 0.5) < 0.01

    def test_elapsed(self):
        p = ProgressTracker(total=1)
        assert p.elapsed >= 0.0

    def test_eta_none_when_no_progress(self):
        p = ProgressTracker(total=10)
        assert p.eta is None

    def test_eta_calculated(self):
        p = ProgressTracker(total=10)
        p.update("completed")
        # eta should be a positive number
        eta = p.eta
        assert eta is None or eta >= 0

    def test_callback(self):
        p = ProgressTracker(total=5)
        called = []
        p.on_progress(lambda tracker: called.append(tracker.processed))
        p.update("completed")
        assert called == [1]

    def test_summary(self):
        p = ProgressTracker(total=3)
        p.update("completed")
        p.update("failed")
        s = p.summary()
        assert s["total"] == 3
        assert s["completed"] == 1
        assert s["failed"] == 1
        assert "progress" in s
        assert "elapsed" in s


# ============================================================
# BaseScraper 测试（使用具体子类）
# ============================================================


class MockScraper(BaseScraper):
    """测试用的具体爬虫实现"""

    def __init__(self, config=None, parse_result=None, extract_result=None):
        super().__init__(config)
        self._parse_result = parse_result or {"title": "Test"}
        self._extract_result = extract_result or {"title": "Test"}

    async def parse(self, html: str, url: str):
        return self._parse_result

    async def extract(self, data):
        return self._extract_result


class TestBaseScraperInit:

    def test_default_config(self):
        scraper = MockScraper()
        assert scraper.config.max_workers == 5
        assert scraper._cancelled is False
        assert scraper._results == []

    def test_custom_config(self):
        config = ScraperConfig(max_workers=10, timeout=60.0)
        scraper = MockScraper(config=config)
        assert scraper.config.max_workers == 10
        assert scraper.config.timeout == 60.0

    def test_progress_initially_none(self):
        scraper = MockScraper()
        assert scraper.progress is None


class TestBaseScraperValidate:

    @pytest.mark.asyncio
    async def test_validate_success(self):
        """3次验证全部一致应返回 COMPLETED"""
        scraper = MockScraper()
        scraper.fetch = AsyncMock(return_value="<html>test</html>")

        result = await scraper.validate("https://example.com", rounds=3)
        assert result.status == ScrapeStatus.COMPLETED
        assert result.validation_passes == 3
        assert result.attempts == 3
        assert result.content_hash != ""
        assert result.data == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_validate_inconsistent_data(self):
        """数据不一致应返回 FAILED"""
        call_count = 0

        async def varying_extract(data):
            nonlocal call_count
            call_count += 1
            return {"title": f"Test-{call_count}"}

        scraper = MockScraper()
        scraper.fetch = AsyncMock(return_value="<html>test</html>")
        scraper.extract = varying_extract

        # 使用 validation_interval=0 加速测试
        scraper.config.validation_interval = 0.0
        result = await scraper.validate("https://example.com", rounds=3)
        assert result.status == ScrapeStatus.FAILED

    @pytest.mark.asyncio
    async def test_validate_fetch_error(self):
        """fetch 异常应记录错误"""
        scraper = MockScraper()
        scraper.fetch = AsyncMock(side_effect=Exception("Network error"))
        scraper.config.validation_interval = 0.0

        result = await scraper.validate("https://example.com", rounds=3)
        assert result.error is not None
        assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_validate_sets_timestamps(self):
        scraper = MockScraper()
        scraper.fetch = AsyncMock(return_value="<html></html>")
        scraper.config.validation_interval = 0.0

        result = await scraper.validate("https://example.com", rounds=3)
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration is not None


class TestBaseScraperScrape:

    @pytest.mark.asyncio
    async def test_scrape_delegates_to_validate(self):
        scraper = MockScraper()
        scraper.fetch = AsyncMock(return_value="<html></html>")
        scraper.config.validation_interval = 0.0

        result = await scraper.scrape("https://example.com")
        assert result.url == "https://example.com"
        assert result.attempts == scraper.config.validation_rounds


class TestBaseScraperScrapeMany:

    @pytest.mark.asyncio
    async def test_scrape_many(self):
        scraper = MockScraper()
        scraper.fetch = AsyncMock(return_value="<html></html>")
        scraper.config.validation_interval = 0.0

        urls = ["https://example.com/1", "https://example.com/2"]
        results = await scraper.scrape_many(urls)
        assert len(results) == 2
        assert scraper.progress is not None
        assert scraper.progress.total == 2

    @pytest.mark.asyncio
    async def test_scrape_many_respects_max_workers(self):
        scraper = MockScraper(config=ScraperConfig(max_workers=1))
        scraper.fetch = AsyncMock(return_value="<html></html>")
        scraper.config.validation_interval = 0.0

        urls = ["https://example.com/1", "https://example.com/2"]
        results = await scraper.scrape_many(urls)
        assert len(results) == 2


class TestBaseScraperCancel:

    @pytest.mark.asyncio
    async def test_cancel(self):
        scraper = MockScraper()
        scraper.cancel()
        assert scraper._cancelled is True


class TestBaseScraperContextManager:

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with MockScraper() as scraper:
            assert scraper is not None

    @pytest.mark.asyncio
    async def test_session_stats(self):
        scraper = MockScraper()
        stats = scraper.session_stats
        assert "requests" in stats
        assert "errors" in stats
