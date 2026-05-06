"""内置代理服务器工具

基于 mitmproxy 的代理服务器工具，集成到 xiaotie Agent 框架。
支持启动/停止代理、查看状态、导出数据、分析流量、过滤小程序请求。

功能概述:
    - start: 启动内置 mitmproxy 代理服务器
    - stop: 停止代理服务器
    - status: 查看代理运行状态和捕获统计
    - export: 导出捕获的流量数据（JSON/HAR 格式）
    - analyze: 分析捕获的流量，生成统计报告
    - filter_miniapp: 过滤微信小程序相关请求

依赖:
    - mitmproxy: pip install 'xiaotie[proxy]'
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from ..schema import ToolResult
from .base import Tool

logger = logging.getLogger(__name__)


class ProxyServerTool(Tool):
    """内置代理服务器工具

    基于 mitmproxy 的代理服务器，无需外部应用（如 Charles）。
    直接在 xiaotie 进程内运行，通过 Agent 调用。

    Actions:
        - start: 启动代理服务器
        - stop: 停止代理服务器
        - status: 查看运行状态
        - export: 导出捕获数据
        - analyze: 分析流量统计
        - filter_miniapp: 过滤小程序请求
    """

    def __init__(
        self,
        proxy_port: int = 8080,
        enable_https: bool = True,
        cert_path: Optional[str] = None,
        storage_path: Optional[str] = None,
    ):
        super().__init__()
        self._proxy_port = proxy_port
        self._enable_https = enable_https
        self._cert_path = cert_path
        self._storage_path = storage_path
        self._server = None  # lazy init
        self._storage = None  # lazy init

    def _ensure_server(self):
        """延迟初始化代理服务器和存储"""
        if self._server is None:
            from ..proxy import ProxyServer

            self._server = ProxyServer(
                port=self._proxy_port,
                enable_ssl=self._enable_https,
                cert_dir=self._cert_path,
            )
            self._storage = self._server.storage

    @property
    def name(self) -> str:
        return "proxy_server"

    @property
    def description(self) -> str:
        return (
            "内置代理服务器工具（基于 mitmproxy），用于捕获和分析网络流量。"
            "支持启动/停止代理、导出数据（JSON/HAR）、分析流量统计、过滤小程序请求。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "start",
                        "stop",
                        "status",
                        "export",
                        "analyze",
                        "filter_miniapp",
                    ],
                    "description": (
                        "操作类型：start-启动代理，stop-停止代理，"
                        "status-查看状态，export-导出数据，"
                        "analyze-分析流量，filter_miniapp-过滤小程序请求"
                    ),
                },
                "port": {
                    "type": "integer",
                    "description": "代理端口（默认 8080）",
                    "default": 8080,
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "har"],
                    "description": "导出格式：json 或 har（默认 json）",
                    "default": "json",
                },
                "output_file": {
                    "type": "string",
                    "description": "导出文件路径（export 操作时使用）",
                },
                "filter_domain": {
                    "type": "string",
                    "description": "过滤域名（可选）",
                },
                "filter_path": {
                    "type": "string",
                    "description": "过滤路径前缀（可选）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """执行代理服务器操作"""
        action = kwargs.get("action")
        dispatch = {
            "start": self._action_start,
            "stop": self._action_stop,
            "status": self._action_status,
            "export": self._action_export,
            "analyze": self._action_analyze,
            "filter_miniapp": self._action_filter_miniapp,
        }
        handler = dispatch.get(action)
        if handler is None:
            return ToolResult(success=False, error=f"未知操作: {action}")
        try:
            return await handler(kwargs)
        except Exception as e:
            logger.exception("代理操作 '%s' 异常", action)
            return ToolResult(success=False, error=f"操作 {action} 异常: {e}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _action_start(self, kwargs: dict) -> ToolResult:
        """启动代理服务器"""
        self._ensure_server()

        if self._server.is_running:
            return ToolResult(
                success=True,
                content=f"代理服务器已在运行中（端口 {self._server.port}）",
            )

        port = kwargs.get("port", self._proxy_port)
        self._server.port = port

        try:
            info = await self._server.start()
            cert_dir = info.get("cert_dir", "")
            return ToolResult(
                success=True,
                content=(
                    f"代理服务器已启动\n"
                    f"- 监听端口: {port}\n"
                    f"- HTTPS 拦截: {'启用' if self._enable_https else '禁用'}\n"
                    f"- 证书目录: {cert_dir}\n\n"
                    f"请在目标设备上配置代理:\n"
                    f"- HTTP/HTTPS 代理: 127.0.0.1:{port}\n"
                    f"- 如需 HTTPS 拦截，请安装 CA 证书 (访问 http://mitm.it)"
                ),
            )
        except (RuntimeError, ImportError) as e:
            return ToolResult(success=False, error=str(e))

    async def _action_stop(self, _kwargs: dict) -> ToolResult:
        """停止代理服务器"""
        self._ensure_server()

        if not self._server.is_running:
            return ToolResult(success=True, content="代理服务器未运行")

        await self._server.stop()
        return ToolResult(success=True, content="代理服务器已停止")

    async def _action_status(self, _kwargs: dict) -> ToolResult:
        """查看代理状态"""
        self._ensure_server()

        status = self._server.get_status()
        lines = ["代理服务器状态:"]
        lines.append(f"- 运行状态: {'运行中' if status['running'] else '未运行'}")
        lines.append(f"- 监听端口: {status['port']}")
        lines.append(f"- HTTPS 拦截: {'启用' if status.get('ssl_enabled', False) else '禁用'}")
        lines.append(f"- 已捕获请求: {status['captured_count']} 条")
        if "uptime_seconds" in status:
            mins, secs = divmod(status["uptime_seconds"], 60)
            lines.append(f"- 运行时间: {mins}分{secs}秒")

        if self._storage and self._storage.count > 0:
            stats = self._storage.get_stats()
            lines.append("\n存储统计:")
            lines.append(f"- 存储记录: {stats['total']} 条")
            lines.append(f"- 总响应大小: {stats.get('total_response_size_kb', 0)} KB")

        return ToolResult(success=True, content="\n".join(lines))

    async def _action_export(self, kwargs: dict) -> ToolResult:
        """导出捕获的数据"""
        self._ensure_server()

        fmt = kwargs.get("format", "json")
        output_file = kwargs.get("output_file")

        if not output_file:
            output_file = f"proxy_capture_{int(time.time())}.{fmt}"
        output_path = Path(output_file).resolve()

        # 从 server 获取捕获的流量
        if self._storage.count == 0:
            return ToolResult(
                success=True,
                content="没有捕获到任何流量数据，请确保代理已启动且有流量通过",
            )

        try:
            exported_path = self._server.export(output_path, fmt=fmt)
            return ToolResult(
                success=True,
                content=(
                    f"已导出 {self._storage.count} 条请求\n"
                    f"- 格式: {fmt.upper()}\n"
                    f"- 文件: {exported_path}"
                ),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"导出失败: {e}")

    async def _action_analyze(self, kwargs: dict) -> ToolResult:
        """分析捕获的流量"""
        self._ensure_server()

        if self._storage.count == 0:
            return ToolResult(
                success=True,
                content="没有捕获到流量数据",
            )

        stats = self._storage.get_stats()

        lines = [
            "=== 代理流量分析报告 ===",
            f"总请求数: {stats['total']}",
            f"总响应大小: {stats.get('total_response_size_kb', 0)} KB",
            f"平均响应时间: {stats.get('avg_duration_ms', 0)} ms",
            "",
            "--- 域名分布 (Top 15) ---",
        ]
        for domain, count in list(stats.get("domains", {}).items())[:15]:
            lines.append(f"  {domain}: {count}")

        lines.append("\n--- HTTP 方法 ---")
        for method, count in stats.get("methods", {}).items():
            lines.append(f"  {method}: {count}")

        lines.append("\n--- 状态码分布 ---")
        for status, count in stats.get("status_codes", {}).items():
            lines.append(f"  {status}: {count}")

        # 端点列表
        entries = self._storage.get_all()
        endpoints = sorted(set(f"{e.method} {e.host}{e.path}" for e in entries))
        lines.append(f"\n--- API 端点 ({len(endpoints)} 个, 前 30) ---")
        for ep in endpoints[:30]:
            lines.append(f"  {ep}")
        if len(endpoints) > 30:
            lines.append(f"  ... 还有 {len(endpoints) - 30} 个端点")

        return ToolResult(success=True, content="\n".join(lines))

    async def _action_filter_miniapp(self, kwargs: dict) -> ToolResult:
        """过滤小程序请求"""
        self._ensure_server()

        if self._storage.count == 0:
            return ToolResult(success=True, content="没有捕获到流量数据")

        miniapp_entries = self._storage.filter_miniapp()

        if not miniapp_entries:
            return ToolResult(
                success=True,
                content="未找到微信小程序相关请求（servicewechat.com 等域名）",
            )

        lines = [
            "=== 微信小程序请求过滤结果 ===",
            f"小程序请求数: {len(miniapp_entries)} / {self._storage.count} 总请求",
            "",
        ]

        domain_group: dict[str, list] = defaultdict(list)
        for e in miniapp_entries:
            domain_group[e.host].append(e)

        for domain, group in domain_group.items():
            lines.append(f"--- {domain} ({len(group)} 请求) ---")
            for item in group[:20]:
                lines.append(f"  {item.method} {item.path}  [{item.status_code}]")
            if len(group) > 20:
                lines.append(f"  ... 还有 {len(group) - 20} 个请求")
            lines.append("")

        # 可选导出
        output_file = kwargs.get("output_file")
        if output_file:
            out = Path(output_file).resolve()
            data = [e.to_dict() for e in miniapp_entries]
            out.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            lines.append(f"过滤结果已保存到: {out}")

        return ToolResult(success=True, content="\n".join(lines))
