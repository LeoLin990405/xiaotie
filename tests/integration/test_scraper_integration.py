"""爬虫模块集成测试

测试覆盖：
- 模块导入与注册
- BaseScraper + StabilityAnalyzer 联合工作
- AuthHandler + SessionManager 集成
- OutputManager 端到端导出
- ScraperTool 完整工作流
- 边界条件
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.scraper.stability import StabilityAnalyzer, StabilityLevel


# ============================================================
# 模块导入集成测试
# ============================================================


class TestModuleImports:
    """测试模块导入和注册"""

    def test_scraper_package_exports(self):
        from xiaotie.scraper import (
            BaseScraper,
            ScraperConfig,
            ScrapeResult,
            ScrapeStatus,
        )
        assert BaseScraper is not None
        assert ScraperConfig is not None
        assert ScrapeResult is not None
        assert ScrapeStatus is not None

    def test_threading_exports(self):
        from xiaotie.scraper import (
            SessionManager,
            ThreadSafeCounter,
            RateLimiter,
        )
        assert SessionManager is not None
        assert ThreadSafeCounter is not None
        assert RateLimiter is not None

    def test_stability_exports(self):
        from xiaotie.scraper import (
            StabilityAnalyzer,
            StabilityReport,
            ChangeMetrics,
        )
        assert StabilityAnalyzer is not None
        assert StabilityReport is not None
        assert ChangeMetrics is not None

    def test_auth_exports(self):
        from xiaotie.scraper import AuthHandler, AuthMethod, AuthConfig
        assert AuthHandler is not None
        assert AuthMethod is not None
        assert AuthConfig is not None

    def test_output_exports(self):
        from xiaotie.scraper import OutputManager, OutputFormat, SanitizeConfig
        assert OutputManager is not None
        assert OutputFormat is not None
        assert SanitizeConfig is not None

    def test_scraper_tool_importable(self):
        from xiaotie.tools.scraper_tool import ScraperTool
        assert ScraperTool is not None

    def test_scraper_tool_is_tool_subclass(self):
        from xiaotie.tools.scraper_tool import ScraperTool
        from xiaotie.tools.base import Tool
        assert issubclass(ScraperTool, Tool)


# ============================================================
# StabilityAnalyzer 端到端测试
# ============================================================


class TestStabilityEndToEnd:
    """测试 StabilityAnalyzer 完整工作流"""

    def test_record_analyze_cycle(self):
        analyzer = StabilityAnalyzer()

        # 记录多次稳定数据
        for _ in range(5):
            analyzer.record("https://api.example.com/data", {
                "title": "Product A",
                "price": 99.99,
                "stock": 100,
            })

        report = analyzer.analyze("https://api.example.com/data")
        assert report.overall_level == StabilityLevel.STABLE
        assert report.sample_count == 5
        assert "title" in report.metrics
        assert "price" in report.metrics
        assert report.metrics["title"].change_count == 0

    def test_mixed_stability_analysis(self):
        analyzer = StabilityAnalyzer()

        for i in range(10):
            analyzer.record("https://example.com/page", {
                "static_title": "Always Same",
                "dynamic_counter": i,
                "timestamp": f"2024-01-{i+1:02d}",
            })

        report = analyzer.analyze("https://example.com/page")
        assert report.metrics["static_title"].change_count == 0
        assert report.metrics["dynamic_counter"].change_count == 9
        assert report.metrics["static_title"].stability_level == StabilityLevel.STABLE
        assert report.metrics["dynamic_counter"].stability_level == StabilityLevel.VOLATILE

    def test_multi_url_analysis(self):
        analyzer = StabilityAnalyzer()

        for _ in range(3):
            analyzer.record("https://a.com", {"x": 1})
            analyzer.record("https://b.com", {"y": "changing"})

        # 修改 b.com 的数据
        analyzer.record("https://b.com", {"y": "different"})

        reports = analyzer.analyze_all()
        assert "https://a.com" in reports
        assert "https://b.com" in reports
        assert reports["https://a.com"].overall_level == StabilityLevel.STABLE

    def test_summary_report_format(self):
        analyzer = StabilityAnalyzer()
        analyzer.record("https://example.com", {"field": "value"})
        analyzer.record("https://example.com", {"field": "value"})

        report = analyzer.analyze("https://example.com")
        summary = report.summary()

        assert "url" in summary
        assert "overall_stability" in summary
        assert "sample_count" in summary
        assert "fields" in summary
        assert "generated_at" in summary


# ============================================================
# OutputManager 端到端测试
# ============================================================


class TestOutputEndToEnd:
    """测试 OutputManager 完整导出流程"""

    def test_json_export_with_sanitize(self, tmp_path):
        from xiaotie.scraper.output import OutputManager, SanitizeConfig

        config = SanitizeConfig(enabled=True, mask_email=True, mask_phone=True)
        om = OutputManager(sanitize_config=config)

        records = [
            {"name": "张三", "email": "zhangsan@example.com", "phone": "13812345678"},
            {"name": "李四", "email": "lisi@test.com", "phone": "13987654321"},
        ]

        path = tmp_path / "sanitized.json"
        om.export_to_file(records, str(path))

        data = json.loads(path.read_text())
        assert len(data) == 2
        assert "zhangsan@example.com" not in json.dumps(data)
        assert "13812345678" not in json.dumps(data)

    def test_csv_export_with_transformer(self, tmp_path):
        from xiaotie.scraper.output import OutputManager

        om = OutputManager()
        om.add_transformer(lambda r: {**r, "processed": True})

        records = [{"name": "Test", "value": "123"}]
        path = tmp_path / "transformed.csv"
        om.export_to_file(records, str(path))

        content = path.read_text()
        assert "processed" in content
        assert "True" in content

    def test_all_formats_export(self, tmp_path):
        from xiaotie.scraper.output import OutputManager, OutputFormat

        om = OutputManager()
        records = [{"id": 1, "name": "Test"}]

        # JSON
        json_path = tmp_path / "data.json"
        om.export_to_file(records, str(json_path))
        assert json.loads(json_path.read_text())[0]["id"] == 1

        # CSV
        csv_path = tmp_path / "data.csv"
        om.export_to_file(records, str(csv_path))
        assert "id" in csv_path.read_text()

        # JSONL
        jsonl_path = tmp_path / "data.jsonl"
        om.export_to_file(records, str(jsonl_path))
        assert json.loads(jsonl_path.read_text().strip())["id"] == 1


# ============================================================
# Auth + Session 集成测试
# ============================================================


class TestAuthSessionIntegration:
    """测试认证与会话管理集成"""

    def test_bearer_headers_applied(self):
        from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod

        config = AuthConfig(
            method=AuthMethod.BEARER,
            token="test-token",
        )
        handler = AuthHandler(config)

        kwargs = {"headers": {"Accept": "application/json"}}
        result = handler.apply_to_kwargs(kwargs)

        assert result["headers"]["Authorization"] == "Bearer test-token"
        assert result["headers"]["Accept"] == "application/json"

    def test_custom_header_applied(self):
        from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod

        config = AuthConfig(
            method=AuthMethod.CUSTOM_HEADER,
            custom_headers={"X-Api-Key": "key123"},
        )
        handler = AuthHandler(config)

        kwargs = {}
        result = handler.apply_to_kwargs(kwargs)
        assert result["headers"]["X-Api-Key"] == "key123"

    def test_cookie_auth_applied(self):
        from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod

        config = AuthConfig(
            method=AuthMethod.COOKIE,
            cookies={"session_id": "abc123", "csrf": "xyz"},
        )
        handler = AuthHandler(config)

        kwargs = {}
        result = handler.apply_to_kwargs(kwargs)
        assert result["cookies"]["session_id"] == "abc123"
        assert result["cookies"]["csrf"] == "xyz"

    def test_md5_signature_applied(self):
        from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod

        config = AuthConfig(
            method=AuthMethod.MD5_SIGNATURE,
            md5_secret="test-secret",
        )
        handler = AuthHandler(config)

        kwargs = {"params": {"key": "value"}}
        result = handler.apply_to_kwargs(kwargs)
        assert "sign" in result["params"]
        assert "timestamp" in result["params"]


# ============================================================
# ScraperTool 集成测试
# ============================================================


class TestScraperToolIntegration:
    """测试 ScraperTool 完整工作流"""

    @pytest.mark.asyncio
    async def test_create_list_cycle(self, tmp_path):
        from xiaotie.tools.scraper_tool import ScraperTool

        scraper_dir = tmp_path / "scrapers"
        tool = ScraperTool(scraper_dir=str(scraper_dir))

        # 创建爬虫
        result = await tool.execute(
            action="create_scraper",
            name="test_shop",
            url="https://shop.example.com",
        )
        assert result.success is True

        # 列出爬虫
        result = await tool.execute(action="list_scrapers")
        assert result.success is True
        assert "test_shop" in result.content

    @pytest.mark.asyncio
    async def test_export_json_fallback(self, tmp_path):
        from xiaotie.tools.scraper_tool import ScraperTool

        tool = ScraperTool()
        tool._last_results = [
            {"title": "Product A", "price": 99},
            {"title": "Product B", "price": 199},
        ]

        output_file = str(tmp_path / "export.json")
        result = await tool.execute(
            action="export", format="json", output_file=output_file
        )
        assert result.success is True
        assert "导出" in result.content or "已导出" in result.content


# ============================================================
# 边界条件测试
# ============================================================


class TestEdgeCases:

    def test_stability_single_snapshot(self):
        analyzer = StabilityAnalyzer()
        analyzer.record("https://example.com", {"x": 1})
        report = analyzer.analyze("https://example.com")
        assert report.sample_count == 1
        assert report.overall_level == StabilityLevel.STABLE

    def test_output_empty_records(self, tmp_path):
        from xiaotie.scraper.output import OutputManager

        om = OutputManager()
        path = tmp_path / "empty.json"
        om.export_to_file([], str(path))
        assert json.loads(path.read_text()) == []

    def test_output_unicode_data(self, tmp_path):
        from xiaotie.scraper.output import OutputManager

        om = OutputManager()
        records = [{"name": "你好世界", "emoji": "🎉"}]
        path = tmp_path / "unicode.json"
        om.export_to_file(records, str(path))
        data = json.loads(path.read_text())
        assert data[0]["name"] == "你好世界"

    def test_thread_safe_counter_concurrent(self):
        from xiaotie.scraper.threading_utils import ThreadSafeCounter
        import threading

        counter = ThreadSafeCounter()
        errors = []

        def increment_and_check():
            for _ in range(1000):
                counter.increment()

        threads = [threading.Thread(target=increment_and_check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.value == 5000

    def test_auth_all_methods_produce_valid_headers(self):
        from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod

        for method in AuthMethod:
            config = AuthConfig(method=method)
            handler = AuthHandler(config)
            headers = handler.get_headers()
            assert isinstance(headers, dict)
