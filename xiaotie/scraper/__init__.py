"""
爬虫核心模块

提供网页数据抓取、稳定性验证、认证管理、数据导出等功能。
支持多线程并发、3次验证机制、异步接口。
"""

from .auth import AuthConfig, AuthHandler, AuthMethod
from .base_scraper import BaseScraper, ScraperConfig, ScrapeResult, ScrapeStatus
from .output import OutputFormat, OutputManager, SanitizeConfig
from .stability import ChangeMetrics, StabilityAnalyzer, StabilityReport
from .threading_utils import RateLimiter, SessionManager, ThreadSafeCounter

__all__ = [
    # Base Scraper
    "BaseScraper",
    "ScraperConfig",
    "ScrapeResult",
    "ScrapeStatus",
    # Threading
    "SessionManager",
    "ThreadSafeCounter",
    "RateLimiter",
    # Stability
    "StabilityAnalyzer",
    "StabilityReport",
    "ChangeMetrics",
    # Auth
    "AuthHandler",
    "AuthMethod",
    "AuthConfig",
    # Output
    "OutputManager",
    "OutputFormat",
    "SanitizeConfig",
]
