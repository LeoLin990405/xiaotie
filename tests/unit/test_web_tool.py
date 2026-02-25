"""WebSearchTool / WebFetchTool 单元测试

测试覆盖：
- DuckDuckGo 搜索（成功 / 空结果 / 异常）
- 网页获取
- URL 验证（SSRF 防护）
- HTML 转文本
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from xiaotie.tools.web_tool import WebFetchTool, WebSearchTool


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------

class TestWebSearchTool:

    @pytest.fixture
    def search_tool(self):
        return WebSearchTool()

    def test_properties(self, search_tool):
        assert search_tool.name == "web_search"
        assert "query" in search_tool.parameters["properties"]

    @pytest.mark.asyncio
    async def test_search_with_results(self, search_tool):
        fake_data = {
            "Abstract": "Python is a language",
            "Heading": "Python",
            "AbstractURL": "https://python.org",
            "RelatedTopics": [],
        }

        with patch.object(
            search_tool, "_search_duckduckgo", return_value=[
                {"title": "Python", "snippet": "Python is a language", "url": "https://python.org"}
            ]
        ):
            result = await search_tool.execute(query="Python")
            assert result.success is True
            assert "Python" in result.content

    @pytest.mark.asyncio
    async def test_search_no_results(self, search_tool):
        with patch.object(search_tool, "_search_duckduckgo", return_value=[]):
            result = await search_tool.execute(query="xyznonexistent")
            assert result.success is True
            assert "未找到" in result.content

    @pytest.mark.asyncio
    async def test_search_exception(self, search_tool):
        with patch.object(
            search_tool, "_search_duckduckgo", side_effect=Exception("network error")
        ):
            result = await search_tool.execute(query="test")
            assert result.success is False
            assert "搜索失败" in result.error

    @pytest.mark.asyncio
    async def test_search_num_results(self, search_tool):
        items = [
            {"title": f"R{i}", "snippet": f"s{i}", "url": f"https://example.com/{i}"}
            for i in range(3)
        ]
        with patch.object(search_tool, "_search_duckduckgo", return_value=items):
            result = await search_tool.execute(query="test", num_results=3)
            assert result.success is True
            assert "R0" in result.content
            assert "R2" in result.content


# ---------------------------------------------------------------------------
# WebFetchTool — URL 验证 / SSRF 防护
# ---------------------------------------------------------------------------

class TestWebFetchURLValidation:

    @pytest.fixture
    def fetch_tool(self):
        return WebFetchTool()

    def test_reject_ftp_scheme(self, fetch_tool):
        err = fetch_tool._validate_url("ftp://example.com/file")
        assert err is not None
        assert "不支持的协议" in err

    def test_reject_file_scheme(self, fetch_tool):
        err = fetch_tool._validate_url("file:///etc/passwd")
        assert err is not None

    def test_reject_no_hostname(self, fetch_tool):
        err = fetch_tool._validate_url("http://")
        assert err is not None
        assert "主机名" in err

    def test_accept_https(self, fetch_tool):
        with patch.object(fetch_tool, "_is_private_ip", return_value=False):
            err = fetch_tool._validate_url("https://example.com/page")
            assert err is None

    @pytest.mark.parametrize("host", [
        "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1",
        "169.254.1.1", "0.0.0.1",
    ])
    def test_reject_private_ips(self, fetch_tool, host):
        with patch("socket.getaddrinfo", return_value=[
            (2, 1, 6, "", (host, 80))
        ]):
            assert fetch_tool._is_private_ip(host) is True

    def test_accept_public_ip(self, fetch_tool):
        with patch("socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("93.184.216.34", 80))
        ]):
            assert fetch_tool._is_private_ip("example.com") is False

    def test_dns_failure_treated_as_private(self, fetch_tool):
        import socket as _socket
        with patch("socket.getaddrinfo", side_effect=_socket.gaierror("no host")):
            assert fetch_tool._is_private_ip("nonexistent.local") is True


# ---------------------------------------------------------------------------
# WebFetchTool — HTML 转文本
# ---------------------------------------------------------------------------

class TestHtmlToText:

    @pytest.fixture
    def fetch_tool(self):
        return WebFetchTool()

    def test_strip_script_and_style(self, fetch_tool):
        html = "<script>alert(1)</script><style>body{}</style><p>Hello</p>"
        text = fetch_tool._html_to_text(html)
        assert "alert" not in text
        assert "body{}" not in text
        assert "Hello" in text

    def test_br_to_newline(self, fetch_tool):
        html = "line1<br/>line2<br>line3"
        text = fetch_tool._html_to_text(html)
        assert "line1" in text
        assert "line3" in text

    def test_entity_decode(self, fetch_tool):
        html = "&lt;div&gt; &amp; &quot;test&quot;"
        text = fetch_tool._html_to_text(html)
        assert "<div>" in text
        assert '& "test"' in text


# ---------------------------------------------------------------------------
# WebFetchTool — execute
# ---------------------------------------------------------------------------

class TestWebFetchExecute:

    @pytest.fixture
    def fetch_tool(self):
        return WebFetchTool()

    @pytest.mark.asyncio
    async def test_execute_blocked_url(self, fetch_tool):
        result = await fetch_tool.execute(url="ftp://evil.com/file")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_private_ip(self, fetch_tool):
        with patch.object(fetch_tool, "_is_private_ip", return_value=True):
            result = await fetch_tool.execute(url="http://192.168.1.1/admin")
            assert result.success is False
            assert "内部网络" in result.error

    def test_tool_properties(self, fetch_tool):
        assert fetch_tool.name == "web_fetch"
        assert "url" in fetch_tool.parameters["properties"]
