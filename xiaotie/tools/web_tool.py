"""Web 搜索工具

提供网络搜索能力，使用 DuckDuckGo
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from typing import Any

from .base import Tool, ToolResult


class WebSearchTool(Tool):
    """Web 搜索工具"""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "搜索网络获取信息。适用于查找最新资料、技术文档、解决方案等。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询词",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量（默认 5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:
        """执行搜索"""
        try:
            results = await self._search_duckduckgo(query, num_results)

            if not results:
                return ToolResult(
                    success=True,
                    content="未找到相关结果",
                )

            # 格式化结果
            lines = [f"🔍 搜索结果: {query}\n"]
            for i, result in enumerate(results, 1):
                lines.append(f"{i}. **{result['title']}**")
                lines.append(f"   {result['snippet']}")
                lines.append(f"   🔗 {result['url']}\n")

            return ToolResult(success=True, content="\n".join(lines))

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"搜索失败: {e}",
            )

    async def _search_duckduckgo(self, query: str, num_results: int) -> list[dict]:
        """使用 DuckDuckGo 搜索"""
        # DuckDuckGo Instant Answer API
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

        try:
            def _fetch():
                req = urllib.request.Request(url, headers={"User-Agent": "XiaoTie/0.3.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    return json.loads(response.read().decode("utf-8"))

            data = await asyncio.to_thread(_fetch)

            results = []

            # 提取摘要
            if data.get("Abstract"):
                results.append(
                    {
                        "title": data.get("Heading", "摘要"),
                        "snippet": data["Abstract"],
                        "url": data.get("AbstractURL", ""),
                    }
                )

            # 提取相关主题
            for topic in data.get("RelatedTopics", [])[: num_results - len(results)]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(
                        {
                            "title": topic.get("Text", "")[:50],
                            "snippet": topic.get("Text", ""),
                            "url": topic.get("FirstURL", ""),
                        }
                    )

            return results[:num_results]

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            # API 失败，返回空结果
            return []


class WebFetchTool(Tool):
    """网页获取工具（带 SSRF 防护）"""

    # 禁止访问的私有/保留 IP 网段
    _BLOCKED_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),       # 回环地址
        ipaddress.ip_network("10.0.0.0/8"),         # 私有网段 A
        ipaddress.ip_network("172.16.0.0/12"),      # 私有网段 B
        ipaddress.ip_network("192.168.0.0/16"),     # 私有网段 C
        ipaddress.ip_network("169.254.0.0/16"),     # 链路本地
        ipaddress.ip_network("0.0.0.0/8"),          # 当前网络
        ipaddress.ip_network("::1/128"),            # IPv6 回环
        ipaddress.ip_network("fc00::/7"),           # IPv6 唯一本地
        ipaddress.ip_network("fe80::/10"),          # IPv6 链路本地
    ]

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "获取网页内容。可以读取网页的文本内容。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取的网页 URL",
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大返回字符数（默认 5000）",
                    "default": 5000,
                },
            },
            "required": ["url"],
        }

    def _is_private_ip(self, hostname: str) -> bool:
        """检查主机名是否解析到私有 IP"""
        try:
            # 解析所有 IP 地址
            addr_infos = socket.getaddrinfo(hostname, None)
            for addr_info in addr_infos:
                ip_str = addr_info[4][0]
                ip = ipaddress.ip_address(ip_str)
                for network in self._BLOCKED_NETWORKS:
                    if ip in network:
                        return True
        except (socket.gaierror, ValueError):
            # DNS 解析失败，拒绝请求
            return True
        return False

    def _validate_url(self, url: str) -> str | None:
        """验证 URL 安全性，返回错误信息或 None"""
        parsed = urllib.parse.urlparse(url)

        # 仅允许 http/https
        if parsed.scheme not in ("http", "https"):
            return f"不支持的协议: {parsed.scheme}，仅允许 http/https"

        hostname = parsed.hostname
        if not hostname:
            return "无效的 URL: 缺少主机名"

        # 检查是否为私有 IP
        if self._is_private_ip(hostname):
            return f"安全限制: 不允许访问内部网络地址 ({hostname})"

        return None

    async def execute(self, url: str, max_length: int = 5000) -> ToolResult:
        """获取网页内容（带 SSRF 防护）"""
        # URL 安全验证
        error = self._validate_url(url)
        if error:
            return ToolResult(success=False, error=error)

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; XiaoTie/0.3.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                # 二次检查：验证实际连接的 IP（防止 DNS rebinding）
                actual_host = urllib.parse.urlparse(response.url).hostname
                if actual_host and self._is_private_ip(actual_host):
                    return ToolResult(
                        success=False,
                        error=f"安全限制: 重定向到内部网络地址 ({actual_host})",
                    )

                content_type = response.headers.get("Content-Type", "")
                if "text" not in content_type and "html" not in content_type:
                    return ToolResult(
                        success=False,
                        error=f"不支持的内容类型: {content_type}",
                    )

                html = response.read().decode("utf-8", errors="ignore")

            # 简单的 HTML 转文本
            text = self._html_to_text(html)

            # 截断
            if len(text) > max_length:
                text = text[:max_length] + "\n\n... (内容已截断)"

            return ToolResult(
                success=True,
                content=f"网页内容 ({url}):\n\n{text}",
            )

        except urllib.error.HTTPError as e:
            return ToolResult(success=False, error=f"HTTP 错误: {e.code}")
        except urllib.error.URLError as e:
            return ToolResult(success=False, error=f"URL 错误: {e.reason}")
        except Exception as e:
            return ToolResult(success=False, error=f"获取失败: {e}")

    def _html_to_text(self, html: str) -> str:
        """简单的 HTML 转文本"""
        # 移除 script 和 style
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # 移除 HTML 注释
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # 处理常见标签
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</p>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<h[1-6][^>]*>", "\n\n## ", html, flags=re.IGNORECASE)
        html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.IGNORECASE)

        # 移除所有其他标签
        html = re.sub(r"<[^>]+>", "", html)

        # 解码 HTML 实体
        html = html.replace("&nbsp;", " ")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&amp;", "&")
        html = html.replace("&quot;", '"')

        # 清理空白
        lines = [line.strip() for line in html.split("\n")]
        lines = [line for line in lines if line]

        return "\n".join(lines)
