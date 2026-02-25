"""
爬虫核心模块

提供网页数据抓取、稳定性验证、认证管理、数据导出等功能。
支持多线程并发、3次验证机制、异步接口。
"""

from .base_scraper import BaseScraper, ScraperConfig, ScrapeResult, ScrapeStatus
from .threading_utils import SessionManager, ThreadSafeCounter, RateLimiter
from .stability import StabilityAnalyzer, StabilityReport, ChangeMetrics
from .auth import AuthHandler, AuthMethod, AuthConfig
from .output import OutputManager, OutputFormat, SanitizeConfig

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
