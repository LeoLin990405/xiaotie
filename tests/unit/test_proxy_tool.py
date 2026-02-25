"""ProxyServerTool 与 Storage - 单元测试

测试覆盖：
- CapturedRequest 数据类
- RequestStorage (SessionStorage)
  - 添加/获取/清空记录
  - 过滤功能（域名/路径/方法/状态码）
  - 小程序域名过滤
  - JSON/HAR 导出
  - 统计摘要
  - 最大条目限制
- ProxyServerTool
  - 初始化与属性
  - 所有 6 个 actions
  - 与 Agent 集成（schema）
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.proxy.storage import (
    CapturedRequest,
    RequestStorage,
    SessionStorage,
)
from xiaotie.schema import ToolResult


# ============================================================
# CapturedRequest 测试
# ============================================================


class TestCapturedRequest:

    def test_default_values(self):
        req = CapturedRequest(url="https://example.com/api")
        assert req.url == "https://example.com/api"
        assert req.method == "GET"
        assert req.host == ""
        assert req.path == "/"
        assert req.scheme == "https"
        assert req.port == 443
        assert req.status_code == 0
        assert req.request_body == b""
        assert req.response_body == b""

    def test_custom_values(self):
        req = CapturedRequest(
            url="https://api.example.com/v1/users",
            method="POST", host="api.example.com", path="/v1/users",
            status_code=201, duration_ms=150.5,
        )
        assert req.method == "POST"
        assert req.status_code == 201
        assert req.duration_ms == 150.5

    def test_to_dict(self):
        req = CapturedRequest(
            url="https://example.com",
            request_body=b"hello", response_body=b"world",
        )
        d = req.to_dict()
        assert d["request_body"] == "hello"
        assert d["response_body"] == "world"

    def test_to_dict_non_utf8(self):
        req = CapturedRequest(url="https://example.com", request_body=b"\xff\xfe")
        d = req.to_dict()
        assert isinstance(d["request_body"], str)

    def test_timestamp_auto_set(self):
        before = time.time()
        req = CapturedRequest(url="https://example.com")
        after = time.time()
        assert before <= req.timestamp <= after


# ============================================================
# RequestStorage 测试
# ============================================================


class TestRequestStorage:

    def _make(self, **kw) -> CapturedRequest:
        defaults = {"url": "https://example.com", "host": "example.com", "status_code": 200}
        defaults.update(kw)
        return CapturedRequest(**defaults)

    def test_init_empty(self):
        s = RequestStorage()
        assert s.count == 0

    def test_add_and_count(self):
        s = RequestStorage()
        s.add(self._make())
        assert s.count == 1

    def test_max_entries_eviction(self):
        s = RequestStorage(max_entries=3)
        for i in range(5):
            s.add(self._make(url=f"https://example.com/{i}"))
        assert s.count == 3
        urls = [e.url for e in s.get_all()]
        assert "https://example.com/0" not in urls
        assert "https://example.com/4" in urls

    def test_clear(self):
        s = RequestStorage()
        s.add(self._make())
        s.clear()
        assert s.count == 0

    def test_get_all_returns_copy(self):
        s = RequestStorage()
        s.add(self._make())
        all_entries = s.get_all()
        all_entries.clear()
        assert s.count == 1


class TestRequestStorageFilter:

    def _populate(self) -> RequestStorage:
        s = RequestStorage()
        entries = [
            CapturedRequest(url="https://api.example.com/v1/users", method="GET",
                          host="api.example.com", path="/v1/users", status_code=200),
            CapturedRequest(url="https://api.example.com/v1/posts", method="POST",
                          host="api.example.com", path="/v1/posts", status_code=201),
            CapturedRequest(url="https://other.com/data", method="GET",
                          host="other.com", path="/data", status_code=404),
            CapturedRequest(url="https://servicewechat.com/api", method="POST",
                          host="servicewechat.com", path="/api", status_code=200),
        ]
        for e in entries:
            s.add(e)
        return s

    def test_filter_by_domain(self):
        s = self._populate()
        assert len(s.filter(domain="example.com")) == 2

    def test_filter_by_path_prefix(self):
        s = self._populate()
        assert len(s.filter(path_prefix="/v1/")) == 2

    def test_filter_by_method(self):
        s = self._populate()
        assert len(s.filter(method="POST")) == 2

    def test_filter_by_status_code(self):
        s = self._populate()
        assert len(s.filter(status_code=200)) == 2

    def test_filter_by_min_status(self):
        s = self._populate()
        assert len(s.filter(min_status=400)) == 1

    def test_filter_combined(self):
        s = self._populate()
        assert len(s.filter(domain="example.com", method="GET")) == 1

    def test_filter_no_match(self):
        s = self._populate()
        assert len(s.filter(domain="nonexistent.com")) == 0


class TestRequestStorageMiniApp:

    def test_filter_miniapp(self):
        s = RequestStorage()
        s.add(CapturedRequest(url="https://servicewechat.com/api", host="servicewechat.com"))
        s.add(CapturedRequest(url="https://google.com", host="google.com"))
        s.add(CapturedRequest(url="https://weixin.qq.com/api", host="weixin.qq.com"))
        assert len(s.filter_miniapp()) == 2

    def test_filter_miniapp_empty(self):
        s = RequestStorage()
        s.add(CapturedRequest(url="https://google.com", host="google.com"))
        assert len(s.filter_miniapp()) == 0


class TestRequestStorageExport:

    def _make_storage(self) -> RequestStorage:
        s = RequestStorage()
        s.add(CapturedRequest(
            url="https://api.example.com/v1", method="GET",
            host="api.example.com", path="/v1", status_code=200,
            request_headers={"Accept": "application/json"},
            response_headers={"Content-Type": "application/json"},
            response_size=100, duration_ms=50.0, timestamp=1700000000.0,
        ))
        return s

    def test_export_json(self, tmp_path):
        s = self._make_storage()
        out = tmp_path / "export.json"
        s.export_json(out)
        data = json.loads(out.read_text())
        assert len(data) == 1
        assert data[0]["url"] == "https://api.example.com/v1"

    def test_export_har(self, tmp_path):
        s = self._make_storage()
        out = tmp_path / "export.har"
        s.export_har(out)
        data = json.loads(out.read_text())
        assert data["log"]["version"] == "1.2"
        assert len(data["log"]["entries"]) == 1

    def test_export_json_empty(self, tmp_path):
        s = RequestStorage()
        out = tmp_path / "empty.json"
        s.export_json(out)
        assert json.loads(out.read_text()) == []


class TestRequestStorageStats:

    def test_stats_empty(self):
        assert RequestStorage().get_stats()["total"] == 0

    def test_stats_with_data(self):
        s = RequestStorage()
        s.add(CapturedRequest(url="https://a.com/1", host="a.com", method="GET",
                             status_code=200, response_size=1024, duration_ms=50.0))
        s.add(CapturedRequest(url="https://b.com/1", host="b.com", method="POST",
                             status_code=404, response_size=512, duration_ms=30.0))
        stats = s.get_stats()
        assert stats["total"] == 2
        assert "a.com" in stats["domains"]


class TestSessionStorageAlias:

    def test_alias(self):
        assert SessionStorage is RequestStorage


# ============================================================
# ProxyServerTool 测试
# ============================================================


class TestProxyServerToolInit:
    """测试 ProxyServerTool 初始化"""

    def test_init(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        tool = ProxyServerTool()
        assert tool._proxy_port == 8080
        assert tool._enable_https is True
        assert tool._server is None

    def test_init_custom(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        tool = ProxyServerTool(proxy_port=9090, enable_https=False)
        assert tool._proxy_port == 9090
        assert tool._enable_https is False

    def test_name(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        assert ProxyServerTool().name == "proxy_server"

    def test_description(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        desc = ProxyServerTool().description
        assert "代理" in desc or "proxy" in desc.lower()

    def test_parameters_schema(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        params = ProxyServerTool().parameters
        assert params["type"] == "object"
        assert "action" in params["properties"]
        actions = params["properties"]["action"]["enum"]
        assert "start" in actions
        assert "stop" in actions
        assert "status" in actions
        assert "export" in actions
        assert "analyze" in actions
        assert "filter_miniapp" in actions

    def test_to_schema(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        schema = ProxyServerTool().to_schema()
        assert schema["name"] == "proxy_server"
        assert "input_schema" in schema

    def test_to_openai_schema(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        schema = ProxyServerTool().to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "proxy_server"

    def test_is_tool_subclass(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        from xiaotie.tools.base import Tool
        assert issubclass(ProxyServerTool, Tool)


class TestProxyServerToolActions:
    """测试 ProxyServerTool 的 6 个 actions"""

    def _make_tool_with_mock_server(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        tool = ProxyServerTool()

        mock_server = MagicMock()
        mock_server.port = 8080
        mock_server.is_running = False
        mock_server.storage = RequestStorage()
        mock_server.get_status.return_value = {
            "running": False, "port": 8080, "ssl_enabled": True,
            "miniapp_only": False, "captured_count": 0,
        }
        mock_server.start = AsyncMock(return_value={
            "status": "started", "port": 8080, "cert_dir": "/tmp/certs",
        })
        mock_server.stop = AsyncMock(return_value={"status": "stopped"})
        mock_server.export = MagicMock(return_value=Path("/tmp/export.json"))

        tool._server = mock_server
        tool._storage = mock_server.storage
        return tool

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        tool = ProxyServerTool()
        result = await tool.execute(action="invalid")
        assert result.success is False
        assert "未知" in result.error

    @pytest.mark.asyncio
    async def test_action_status(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="status")
        assert result.success is True
        assert "状态" in result.content

    @pytest.mark.asyncio
    async def test_action_start(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="start")
        assert result.success is True
        assert "启动" in result.content

    @pytest.mark.asyncio
    async def test_action_start_already_running(self):
        tool = self._make_tool_with_mock_server()
        tool._server.is_running = True
        result = await tool.execute(action="start")
        assert result.success is True
        assert "已在运行" in result.content

    @pytest.mark.asyncio
    async def test_action_stop(self):
        tool = self._make_tool_with_mock_server()
        tool._server.is_running = True
        result = await tool.execute(action="stop")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_action_stop_not_running(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="stop")
        assert result.success is True
        assert "未运行" in result.content

    @pytest.mark.asyncio
    async def test_action_export_no_data(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="export")
        assert result.success is True
        assert "没有" in result.content

    @pytest.mark.asyncio
    async def test_action_export_with_data(self, tmp_path):
        tool = self._make_tool_with_mock_server()
        tool._storage.add(CapturedRequest(
            url="https://example.com", host="example.com", status_code=200,
        ))
        out = str(tmp_path / "test.json")
        result = await tool.execute(action="export", output_file=out)
        assert result.success is True
        assert "导出" in result.content or "已导出" in result.content

    @pytest.mark.asyncio
    async def test_action_analyze_no_data(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="analyze")
        assert result.success is True
        assert "没有" in result.content

    @pytest.mark.asyncio
    async def test_action_analyze_with_data(self):
        tool = self._make_tool_with_mock_server()
        tool._storage.add(CapturedRequest(
            url="https://api.example.com/v1", host="api.example.com",
            method="GET", status_code=200, response_size=1024, duration_ms=50.0,
        ))
        result = await tool.execute(action="analyze")
        assert result.success is True
        assert "分析" in result.content or "报告" in result.content

    @pytest.mark.asyncio
    async def test_action_filter_miniapp_no_data(self):
        tool = self._make_tool_with_mock_server()
        result = await tool.execute(action="filter_miniapp")
        assert result.success is True
        assert "没有" in result.content

    @pytest.mark.asyncio
    async def test_action_filter_miniapp_with_data(self):
        tool = self._make_tool_with_mock_server()
        tool._storage.add(CapturedRequest(
            url="https://servicewechat.com/api", host="servicewechat.com",
            method="POST", status_code=200,
        ))
        tool._storage.add(CapturedRequest(
            url="https://google.com", host="google.com",
            method="GET", status_code=200,
        ))
        result = await tool.execute(action="filter_miniapp")
        assert result.success is True
        assert "servicewechat" in result.content or "小程序" in result.content

    @pytest.mark.asyncio
    async def test_action_filter_miniapp_no_matches(self):
        tool = self._make_tool_with_mock_server()
        tool._storage.add(CapturedRequest(
            url="https://google.com", host="google.com", status_code=200,
        ))
        result = await tool.execute(action="filter_miniapp")
        assert result.success is True
        assert "未找到" in result.content

    @pytest.mark.asyncio
    async def test_execution_stats(self):
        tool = self._make_tool_with_mock_server()
        stats = tool.get_execution_stats()
        assert stats["call_count"] == 0
