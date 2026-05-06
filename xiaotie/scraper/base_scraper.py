"""
爬虫基类

提供 BaseScraper 抽象基类，实现3次验证、多线程并发、进度跟踪。
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .threading_utils import RateLimiter, SessionConfig, SessionManager


class ScrapeStatus(Enum):
    """抓取状态"""

    PENDING = "pending"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScrapeResult:
    """抓取结果"""

    url: str
    data: Any = None
    status: ScrapeStatus = ScrapeStatus.PENDING
    attempts: int = 0
    validation_passes: int = 0
    content_hash: str = ""
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_valid(self) -> bool:
        return self.validation_passes >= 3


@dataclass
class ScraperConfig:
    """爬虫配置"""

    max_workers: int = 5
    validation_rounds: int = 3
    validation_interval: float = 2.0
    rate_limit: float = 5.0  # 每秒请求数
    rate_burst: int = 10
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "XiaoTie-Scraper/1.0"
    proxy: Optional[str] = None
    verify_ssl: bool = True
    headers: Dict[str, str] = field(default_factory=dict)


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, total: int = 0):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.skipped = 0
        self._callbacks: List[Callable] = []
        self._start_time = time.monotonic()

    def on_progress(self, callback: Callable):
        self._callbacks.append(callback)

    def update(self, status: str = "completed"):
        if status == "completed":
            self.completed += 1
        elif status == "failed":
            self.failed += 1
        elif status == "skipped":
            self.skipped += 1
        for cb in self._callbacks:
            cb(self)

    @property
    def processed(self) -> int:
        return self.completed + self.failed + self.skipped

    @property
    def progress(self) -> float:
        if self.total == 0:
            return 0.0
        return self.processed / self.total

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def eta(self) -> Optional[float]:
        if self.processed == 0 or self.total == 0:
            return None
        rate = self.processed / self.elapsed
        remaining = self.total - self.processed
        return remaining / rate if rate > 0 else None

    def summary(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "progress": f"{self.progress:.1%}",
            "elapsed": f"{self.elapsed:.1f}s",
            "eta": f"{self.eta:.1f}s" if self.eta else "N/A",
        }


class BaseScraper(ABC):
    """爬虫抽象基类

    提供3次验证、多线程并发、进度跟踪等核心功能。
    子类需实现 parse() 和 extract() 方法。
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self._session_config = SessionConfig(
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
            headers={
                "User-Agent": self.config.user_agent,
                **self.config.headers,
            },
            proxy=self.config.proxy,
            verify_ssl=self.config.verify_ssl,
            max_connections=self.config.max_workers,
        )
        self._session_manager = SessionManager(self._session_config)
        self._rate_limiter = RateLimiter(self.config.rate_limit, self.config.rate_burst)
        self._progress: Optional[ProgressTracker] = None
        self._results: List[ScrapeResult] = []
        self._cancelled = False

    @abstractmethod
    async def parse(self, html: str, url: str) -> Any:
        """解析 HTML 内容，返回结构化数据"""
        ...

    @abstractmethod
    async def extract(self, data: Any) -> Any:
        """从解析后的数据中提取目标字段"""
        ...

    async def fetch(self, url: str) -> str:
        """获取页面内容"""
        await self._rate_limiter.acquire()
        resp = await self._session_manager.get(url)
        async with resp:
            resp.raise_for_status()
            return await resp.text()

    async def validate(self, url: str, rounds: int = 3) -> ScrapeResult:
        """3次验证抓取：多次抓取同一URL，比较结果一致性"""
        result = ScrapeResult(url=url, started_at=datetime.now(), status=ScrapeStatus.VALIDATING)
        hashes: List[str] = []

        for i in range(rounds):
            try:
                result.attempts += 1
                html = await self.fetch(url)
                data = await self.parse(html, url)
                extracted = await self.extract(data)

                content_str = str(extracted)
                h = hashlib.sha256(content_str.encode()).hexdigest()
                hashes.append(h)

                if i > 0 and h == hashes[0]:
                    result.validation_passes += 1
                elif i == 0:
                    result.validation_passes += 1
                    result.data = extracted
                    result.content_hash = h

                if i < rounds - 1:
                    await asyncio.sleep(self.config.validation_interval)

            except Exception as e:
                result.error = str(e)

        if result.validation_passes >= rounds:
            result.status = ScrapeStatus.COMPLETED
        else:
            result.status = ScrapeStatus.FAILED
            if not result.error:
                result.error = (
                    f"Validation failed: {result.validation_passes}/{rounds} "
                    f"passes (hashes: {hashes})"
                )

        result.completed_at = datetime.now()
        return result

    async def scrape(self, url: str) -> ScrapeResult:
        """抓取单个 URL（带验证）"""
        return await self.validate(url, rounds=self.config.validation_rounds)

    async def scrape_many(self, urls: List[str]) -> List[ScrapeResult]:
        """并发抓取多个 URL"""
        self._progress = ProgressTracker(total=len(urls))
        self._results = []
        self._cancelled = False

        sem = asyncio.Semaphore(self.config.max_workers)

        async def _worker(url: str):
            if self._cancelled:
                return
            async with sem:
                try:
                    result = await self.scrape(url)
                    self._results.append(result)
                    status = "completed" if result.status == ScrapeStatus.COMPLETED else "failed"
                    self._progress.update(status)
                except Exception:
                    self._progress.update("failed")

        tasks = [asyncio.create_task(_worker(u)) for u in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        return self._results

    def cancel(self):
        """取消正在进行的抓取"""
        self._cancelled = True

    @property
    def progress(self) -> Optional[ProgressTracker]:
        return self._progress

    @property
    def session_stats(self) -> Dict[str, int]:
        return self._session_manager.stats

    async def close(self):
        await self._session_manager.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
