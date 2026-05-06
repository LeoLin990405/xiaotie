"""Charles 代理抓包工具

集成 Charles 代理，用于自动抓取小程序网络请求。
支持自动会话导出、请求分析、小程序请求过滤。

功能概述:
    - 启动/停止 Charles Proxy 应用（自动检测安装路径）
    - 自动配置/恢复 macOS 系统代理
    - 通过 AppleScript 自动导出会话数据（JSON/HAR 格式）
    - 分析抓包数据，生成统计报告
    - 过滤微信小程序相关请求
    - 支持按域名/路径过滤

平台支持:
    - macOS: 完整支持（系统代理自动配置 + AppleScript 自动导出）
    - Linux: 支持启动/停止，自动设置 http_proxy/https_proxy 环境变量
    - Windows: 支持启动/停止，Charles 自行管理代理注册

依赖:
    - Charles Proxy 已安装
    - macOS 上使用 networksetup 配置代理
    - Linux 上通过环境变量配置代理

使用示例::

    from xiaotie.tools.charles_tool import CharlesProxyTool

    tool = CharlesProxyTool()

    # 启动代理
    result = await tool.execute(action="start", port=8888)

    # 查看状态
    result = await tool.execute(action="status")

    # 导出数据
    result = await tool.execute(action="export", output_file="data.json")

    # 分析会话
    result = await tool.execute(action="analyze", session_file="data.json")

    # 过滤小程序请求
    result = await tool.execute(action="filter_miniapp", session_file="data.json")

    # 停止代理
    result = await tool.execute(action="stop")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from ..schema import ToolResult
from .base import Tool

logger = logging.getLogger(__name__)


class CharlesProxyTool(Tool):
    """Charles 代理抓包工具

    自动化控制 Charles Proxy，用于抓取和分析小程序网络请求。
    继承自 :class:`Tool` 基类，可直接注册到 xiaotie Agent 中使用。

    功能:
        - ``start``: 启动 Charles 代理并自动配置系统代理
        - ``stop``: 停止 Charles 代理并恢复系统代理
        - ``export``: 导出抓包数据（支持 JSON/HAR 格式）
        - ``status``: 查看 Charles 运行状态
        - ``analyze``: 分析会话数据，生成统计报告
        - ``filter_miniapp``: 过滤微信小程序相关请求

    Attributes:
        charles_app (str): Charles 可执行文件路径，自动检测或手动指定。
        charles_process (subprocess.Popen | None): Charles 进程句柄。
        proxy_port (int): 代理端口号，默认 8888。
        session_file (Path | None): 最近导出的会话文件路径。
        MINIAPP_DOMAINS (tuple): 微信小程序相关域名列表。
        MAX_RETRY (int): 操作重试次数，默认 3。
        RETRY_DELAY (int): 重试间隔秒数，默认 2。

    Args:
        charles_path: Charles 可执行文件路径。为 None 时自动检测。
        proxy_port: 默认代理端口，默认 8888。

    Example::

        # 直接使用
        tool = CharlesProxyTool()
        result = await tool.execute(action="start", port=8888)

        # 在 Agent 中使用
        from xiaotie import create_agent
        agent = create_agent(provider="anthropic", tools=[CharlesProxyTool()])
        await agent.run("启动 Charles 代理")

        # 自定义 Charles 路径
        tool = CharlesProxyTool(charles_path="/opt/charles/bin/charles")
    """

    # 微信小程序相关域名
    MINIAPP_DOMAINS = (
        "servicewechat.com",
        "weixin.qq.com",
        "wx.qq.com",
        "qlogo.cn",
        "weixinbridge.com",
        "wxaapi.weixin.qq.com",
    )

    MAX_RETRY = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, charles_path: Optional[str] = None, proxy_port: int = 8888):
        super().__init__()
        self.charles_app = charles_path or self._detect_charles_path()
        self.charles_process: Optional[subprocess.Popen] = None
        self.proxy_port = proxy_port
        self.session_file: Optional[Path] = None

    @staticmethod
    def _detect_charles_path() -> str:
        """Auto-detect Charles binary across platforms.

        Checks common installation paths for macOS, Windows, and Linux.
        Falls back to PATH lookup if standard locations don't exist.

        Returns:
            str: Path to the Charles executable.
        """
        system = platform.system()
        candidates: list[str] = []
        if system == "Darwin":
            candidates = [
                "/Applications/Charles.app/Contents/MacOS/Charles",
                str(Path.home() / "Applications/Charles.app/Contents/MacOS/Charles"),
            ]
        elif system == "Windows":
            for base in (
                Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
                Path(os.environ.get("LOCALAPPDATA", "")),
            ):
                candidates.append(str(base / "Charles" / "Charles.exe"))
        else:  # Linux
            candidates = ["/usr/bin/charles", "/usr/local/bin/charles"]

        for c in candidates:
            if Path(c).exists():
                return c

        # Fallback: try PATH
        found = shutil.which("charles")
        if found:
            return found

        # Return platform default even if not found (will error at start)
        return candidates[0] if candidates else "charles"

    @property
    def name(self) -> str:
        return "charles_proxy"

    @property
    def description(self) -> str:
        return "Charles 代理抓包工具，用于抓取小程序网络请求，支持自动导出、分析和过滤"

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
                        "export",
                        "status",
                        "analyze",
                        "filter_miniapp",
                    ],
                    "description": (
                        "操作类型：start-启动代理，stop-停止代理，"
                        "export-导出数据，status-查看状态，"
                        "analyze-分析会话，filter_miniapp-过滤小程序请求"
                    ),
                },
                "port": {
                    "type": "integer",
                    "description": "代理端口（默认 8888）",
                    "default": 8888,
                },
                "filter_domain": {
                    "type": "string",
                    "description": "过滤域名（可选），只抓取指定域名的请求",
                },
                "filter_path": {
                    "type": "string",
                    "description": "过滤路径前缀（可选），只匹配指定路径的请求",
                },
                "output_file": {
                    "type": "string",
                    "description": "导出文件路径（export 操作时使用）",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "har"],
                    "description": "导出格式：json 或 har（默认 json）",
                    "default": "json",
                },
                "session_file": {
                    "type": "string",
                    "description": "会话文件路径（analyze/filter_miniapp 操作时使用）",
                },
            },
            "required": ["action"],
        }

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute(self, **kwargs) -> ToolResult:
        """执行 Charles 操作

        根据 ``action`` 参数分发到对应的处理方法。

        Args:
            **kwargs: 关键字参数，必须包含 ``action``。
                action (str): 操作类型，可选值:
                    - ``"start"``: 启动 Charles 代理
                    - ``"stop"``: 停止 Charles 代理
                    - ``"export"``: 导出抓包数据
                    - ``"status"``: 查看运行状态
                    - ``"analyze"``: 分析会话数据
                    - ``"filter_miniapp"``: 过滤小程序请求
                port (int, optional): 代理端口，默认 8888。仅 start 使用。
                filter_domain (str, optional): 过滤域名。
                filter_path (str, optional): 过滤路径前缀。
                output_file (str, optional): 导出文件路径。
                format (str, optional): 导出格式，``"json"`` 或 ``"har"``。
                session_file (str, optional): 会话文件路径，analyze/filter_miniapp 使用。

        Returns:
            ToolResult: 包含 success、content、error 字段的结果对象。

        Example::

            result = await tool.execute(action="start", port=8888)
            if result.success:
                print(result.content)
            else:
                print(f"Error: {result.error}")
        """
        action = kwargs.get("action")
        dispatch = {
            "start": self._start_charles,
            "stop": self._stop_charles,
            "export": self._export_session,
            "status": self._get_status,
            "analyze": self._analyze_session,
            "filter_miniapp": self._filter_miniapp_requests,
        }
        handler = dispatch.get(action)
        if handler is None:
            return ToolResult(success=False, error=f"未知的操作类型: {action}")
        try:
            return await handler(kwargs)
        except Exception as e:
            logger.exception("Charles 操作 '%s' 异常", action)
            return ToolResult(success=False, error=f"操作 {action} 异常: {e}")

    # ------------------------------------------------------------------
    # Helpers: retry wrapper
    # ------------------------------------------------------------------

    async def _retry(self, coro_fn, *args, retries: int = MAX_RETRY, **kw):
        """通用异步重试包装器

        在操作失败时自动重试，每次重试间隔 RETRY_DELAY 秒。

        Args:
            coro_fn: 要重试的异步函数。
            *args: 传递给 coro_fn 的位置参数。
            retries: 最大重试次数，默认 MAX_RETRY。
            **kw: 传递给 coro_fn 的关键字参数。

        Returns:
            coro_fn 的返回值。

        Raises:
            Exception: 所有重试均失败后，抛出最后一次的异常。
        """
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                return await coro_fn(*args, **kw)
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "重试 %d/%d 失败: %s",
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    await asyncio.sleep(self.RETRY_DELAY)
        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    async def _start_charles(self, kwargs: dict) -> ToolResult:
        """启动 Charles 代理

        启动 Charles 应用进程，等待就绪后自动配置系统代理。
        如果 Charles 已在运行，直接返回成功。

        Args:
            kwargs: 参数字典，支持:
                - port (int): 代理端口，默认 8888

        Returns:
            ToolResult: 成功时 content 包含代理信息和配置说明。
        """
        if self.charles_process and self.charles_process.poll() is None:
            return ToolResult(
                success=True,
                content=f"Charles 代理已在运行中（端口 {self.proxy_port}）",
            )

        port = kwargs.get("port", 8888)
        self.proxy_port = port

        try:
            self.charles_process = subprocess.Popen(
                [self.charles_app],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Poll for process readiness instead of fixed sleep
            for _ in range(6):
                await asyncio.sleep(0.5)
                if self.charles_process.poll() is not None:
                    return ToolResult(
                        success=False,
                        error="Charles 进程启动后立即退出，请检查安装",
                    )
            await self._configure_system_proxy(port)

            logger.info("Charles 代理已启动，端口 %d, PID %d", port, self.charles_process.pid)
            return ToolResult(
                success=True,
                content=(
                    f"Charles 代理已启动\n"
                    f"- 代理端口: {port}\n"
                    f"- 进程 ID: {self.charles_process.pid}\n"
                    f"- 系统代理已配置\n\n"
                    f"请在小程序设备上配置代理:\n"
                    f"- HTTP 代理: 127.0.0.1:{port}\n"
                    f"- HTTPS 代理: 127.0.0.1:{port}"
                ),
            )
        except FileNotFoundError:
            logger.error("Charles 应用未找到: %s", self.charles_app)
            return ToolResult(
                success=False,
                error=f"Charles 应用未找到: {self.charles_app}，请确认已安装 Charles",
            )
        except Exception as e:
            logger.error("启动 Charles 失败: %s", e)
            return ToolResult(success=False, error=f"启动 Charles 失败: {e}")

    async def _stop_charles(self, _kwargs: dict | None = None) -> ToolResult:
        """停止 Charles 代理

        终止 Charles 进程并恢复系统代理设置。
        如果进程未在 5 秒内退出，会强制终止。

        Args:
            _kwargs: 未使用，保持接口一致。

        Returns:
            ToolResult: 成功时 content 确认代理已停止。
        """
        if not self.charles_process or self.charles_process.poll() is not None:
            return ToolResult(success=True, content="Charles 代理未运行")

        try:
            self.charles_process.terminate()
            try:
                self.charles_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Charles 未在 5s 内退出，强制终止")
                self.charles_process.kill()
                self.charles_process.wait(timeout=3)

            await self._restore_system_proxy()
            logger.info("Charles 代理已停止")
            return ToolResult(success=True, content="Charles 代理已停止，系统代理已恢复")
        except Exception as e:
            logger.error("停止 Charles 失败: %s", e)
            return ToolResult(success=False, error=f"停止 Charles 失败: {e}")

    # ------------------------------------------------------------------
    # Export (auto via AppleScript + fallback)
    # ------------------------------------------------------------------

    async def _export_session(self, kwargs: dict) -> ToolResult:
        """自动导出 Charles 会话数据

        优先尝试通过 AppleScript 自动导出，失败时回退到手动导出说明。
        支持 JSON 和 HAR 两种格式，可选按域名过滤。

        Args:
            kwargs: 参数字典，支持:
                - format (str): 导出格式，``"json"`` 或 ``"har"``，默认 ``"json"``
                - output_file (str): 输出文件路径，默认自动生成带时间戳的文件名
                - filter_domain (str): 过滤域名，仅保留匹配的请求

        Returns:
            ToolResult: 成功时 content 包含导出路径或手动导出说明。
        """
        fmt = kwargs.get("format", "json")
        output_file = kwargs.get("output_file")
        filter_domain = kwargs.get("filter_domain")

        if not output_file:
            output_file = f"charles_session_{int(time.time())}.{fmt}"
        output_path = Path(output_file).resolve()

        # 尝试通过 AppleScript 自动导出
        try:
            exported = await self._applescript_export(output_path, fmt)
            if exported:
                data = self._load_session_file(output_path)
                if data and filter_domain:
                    data = self._filter_by_domain(data, filter_domain)
                    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                self.session_file = output_path
                logger.info("会话已自动导出到 %s", output_path)
                return ToolResult(
                    success=True,
                    content=f"会话已自动导出到: {output_path}\n格式: {fmt.upper()}",
                )
        except Exception as e:
            logger.warning("AppleScript 自动导出失败，回退到手动说明: %s", e)

        # 回退：给出手动导出说明
        ext_map = {"json": "JSON Session File (*.chlsj)", "har": "HTTP Archive (*.har)"}
        return ToolResult(
            success=True,
            content=(
                f"自动导出未成功，请手动导出:\n"
                f"1. Charles -> File -> Export Session...\n"
                f"2. 格式选择: {ext_map.get(fmt, fmt)}\n"
                f"3. 保存到: {output_path}\n\n"
                f"导出后可使用 analyze 操作分析数据。"
            ),
        )

    async def _applescript_export(self, output_path: Path, fmt: str) -> bool:
        """通过 AppleScript 驱动 Charles 导出会话

        仅在 macOS 上可用。激活 Charles 窗口，模拟菜单操作导出会话文件。

        Args:
            output_path: 导出文件的绝对路径。
            fmt: 导出格式，``"json"`` 或 ``"har"``。

        Returns:
            bool: 导出文件是否成功创建。

        Raises:
            RuntimeError: AppleScript 执行失败时抛出。
        """
        script = f'''
        tell application "Charles"
            activate
            delay 0.5
        end tell
        tell application "System Events"
            tell process "Charles"
                click menu item "Export Session..." of menu "File" of menu bar 1
                delay 1
                -- 设置保存路径
                keystroke "g" using {{command down, shift down}}
                delay 0.5
                keystroke "{output_path}"
                delay 0.3
                keystroke return
                delay 0.5
                keystroke return
            end tell
        end tell
        '''
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())
        # 等待文件写入
        for _ in range(10):
            if output_path.exists() and output_path.stat().st_size > 0:
                return True
            await asyncio.sleep(0.5)
        return output_path.exists()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def _get_status(self, _kwargs: dict | None = None) -> ToolResult:
        """获取 Charles 运行状态

        返回 Charles 进程是否运行、代理端口、进程 ID 和最近导出文件等信息。

        Args:
            _kwargs: 未使用，保持接口一致。

        Returns:
            ToolResult: content 包含格式化的状态信息。
        """
        is_running = self.charles_process and self.charles_process.poll() is None

        lines = ["Charles 代理状态:"]
        lines.append(f"- 运行状态: {'运行中' if is_running else '未运行'}")
        if is_running:
            lines.append(f"- 代理端口: {self.proxy_port}")
            lines.append(f"- 进程 ID: {self.charles_process.pid}")
        if self.session_file:
            lines.append(f"- 最近导出: {self.session_file}")

        return ToolResult(success=True, content="\n".join(lines))

    # ------------------------------------------------------------------
    # Analyze session
    # ------------------------------------------------------------------

    async def _analyze_session(self, kwargs: dict) -> ToolResult:
        """分析抓取的会话数据，生成统计报告

        读取 Charles 导出的 JSON/HAR 文件，统计域名分布、HTTP 方法、
        状态码分布和 API 端点列表。

        Args:
            kwargs: 参数字典，支持:
                - session_file (str): 会话文件路径。未指定时使用最近导出的文件。

        Returns:
            ToolResult: content 包含格式化的分析报告。
        """
        session_path = self._resolve_session_path(kwargs)
        if session_path is None:
            return ToolResult(
                success=False,
                error="未指定 session_file，且没有最近导出的会话文件",
            )

        data = self._load_session_file(session_path)
        if data is None:
            return ToolResult(success=False, error=f"无法加载会话文件: {session_path}")

        entries = self._extract_entries(data)
        if not entries:
            return ToolResult(success=True, content="会话中没有请求记录")

        # 统计
        domain_counter: Counter = Counter()
        method_counter: Counter = Counter()
        status_counter: Counter = Counter()
        endpoints: list[str] = []
        total_size = 0

        for entry in entries:
            url = entry.get("url") or entry.get("host", "")
            parsed = urlparse(url) if url.startswith("http") else None
            domain = parsed.netloc if parsed else entry.get("host", "unknown")
            path = parsed.path if parsed else entry.get("path", "/")
            method = entry.get("method", "GET")
            status = entry.get("status") or entry.get("responseCode", 0)
            size = (
                entry.get("sizes", {}).get("response", 0)
                if isinstance(entry.get("sizes"), dict)
                else 0
            )

            domain_counter[domain] += 1
            method_counter[method] += 1
            status_counter[str(status)] += 1
            endpoints.append(f"{method} {domain}{path}")
            total_size += size

        unique_endpoints = sorted(set(endpoints))

        report_lines = [
            "=== Charles 会话分析报告 ===",
            f"文件: {session_path.name}",
            f"总请求数: {len(entries)}",
            f"唯一端点数: {len(unique_endpoints)}",
            f"总响应大小: {total_size / 1024:.1f} KB",
            "",
            "--- 域名分布 ---",
        ]
        for domain, count in domain_counter.most_common(15):
            report_lines.append(f"  {domain}: {count}")

        report_lines.append("\n--- HTTP 方法 ---")
        for method, count in method_counter.most_common():
            report_lines.append(f"  {method}: {count}")

        report_lines.append("\n--- 状态码分布 ---")
        for status, count in status_counter.most_common():
            report_lines.append(f"  {status}: {count}")

        report_lines.append("\n--- API 端点列表 (前 30) ---")
        for ep in unique_endpoints[:30]:
            report_lines.append(f"  {ep}")
        if len(unique_endpoints) > 30:
            report_lines.append(f"  ... 还有 {len(unique_endpoints) - 30} 个端点")

        return ToolResult(success=True, content="\n".join(report_lines))

    # ------------------------------------------------------------------
    # Filter miniapp requests
    # ------------------------------------------------------------------

    async def _filter_miniapp_requests(self, kwargs: dict) -> ToolResult:
        """过滤并解析微信小程序相关请求

        从会话数据中筛选 servicewechat.com、weixin.qq.com 等
        微信小程序相关域名的请求，按域名分组展示。

        Args:
            kwargs: 参数字典，支持:
                - session_file (str): 会话文件路径。未指定时使用最近导出的文件。
                - output_file (str): 可选，将过滤结果保存到指定文件。

        Returns:
            ToolResult: content 包含按域名分组的小程序请求列表。
        """
        session_path = self._resolve_session_path(kwargs)
        if session_path is None:
            return ToolResult(
                success=False,
                error="未指定 session_file，且没有最近导出的会话文件",
            )

        data = self._load_session_file(session_path)
        if data is None:
            return ToolResult(success=False, error=f"无法加载会话文件: {session_path}")

        entries = self._extract_entries(data)
        miniapp_entries = []
        api_calls: list[dict[str, Any]] = []

        for entry in entries:
            url = entry.get("url") or entry.get("host", "")
            if not any(d in url for d in self.MINIAPP_DOMAINS):
                continue
            miniapp_entries.append(entry)

            parsed = urlparse(url) if url.startswith("http") else None
            api_calls.append(
                {
                    "method": entry.get("method", "GET"),
                    "domain": parsed.netloc if parsed else entry.get("host", ""),
                    "path": parsed.path if parsed else entry.get("path", "/"),
                    "status": entry.get("status") or entry.get("responseCode", 0),
                    "url": url,
                }
            )

        if not miniapp_entries:
            return ToolResult(
                success=True,
                content="未找到微信小程序相关请求（servicewechat.com 等域名）",
            )

        lines = [
            "=== 微信小程序请求过滤结果 ===",
            f"小程序请求数: {len(miniapp_entries)} / {len(entries)} 总请求",
            "",
        ]

        domain_group: dict[str, list] = defaultdict(list)
        for call in api_calls:
            domain_group[call["domain"]].append(call)

        for domain, calls in domain_group.items():
            lines.append(f"--- {domain} ({len(calls)} 请求) ---")
            for c in calls[:20]:
                lines.append(f"  {c['method']} {c['path']}  [{c['status']}]")
            if len(calls) > 20:
                lines.append(f"  ... 还有 {len(calls) - 20} 个请求")
            lines.append("")

        # 可选：保存过滤结果
        output_file = kwargs.get("output_file")
        if output_file:
            out = Path(output_file).resolve()
            out.write_text(json.dumps(api_calls, ensure_ascii=False, indent=2))
            lines.append(f"过滤结果已保存到: {out}")

        return ToolResult(success=True, content="\n".join(lines))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_session_path(self, kwargs: dict) -> Path | None:
        """解析会话文件路径

        优先使用 kwargs 中的 session_file，其次使用最近导出的文件。

        Args:
            kwargs: 参数字典，可包含 session_file 键。

        Returns:
            Path | None: 解析后的绝对路径，或 None（无可用文件）。
        """
        sf = kwargs.get("session_file")
        if sf:
            return Path(sf).resolve()
        if self.session_file and self.session_file.exists():
            return self.session_file
        return None

    @staticmethod
    def _load_session_file(path: Path) -> Any | None:
        """安全加载 JSON/HAR 会话文件

        Args:
            path: 会话文件路径。

        Returns:
            解析后的 JSON 数据，或 None（加载失败）。
        """
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("加载会话文件失败 %s: %s", path, e)
            return None

    @staticmethod
    def _extract_entries(data: Any) -> list[dict]:
        """从 JSON 或 HAR 数据中提取请求条目

        兼容多种 Charles 导出格式：HAR (log.entries)、JSON 数组、
        单个请求对象等。

        Args:
            data: 解析后的 JSON 数据。

        Returns:
            请求条目列表。
        """
        if isinstance(data, dict) and "log" in data:
            return data["log"].get("entries", [])
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        if isinstance(data, dict):
            return [data]
        return []

    @staticmethod
    def _filter_by_domain(data: Any, domain: str) -> list[dict]:
        """按域名过滤条目

        Args:
            data: 解析后的 JSON 数据。
            domain: 目标域名（子串匹配）。

        Returns:
            匹配域名的请求条目列表。
        """
        entries = CharlesProxyTool._extract_entries(data)
        return [e for e in entries if domain in (e.get("url") or e.get("host", ""))]

    # ------------------------------------------------------------------
    # System proxy helpers (cross-platform)
    # ------------------------------------------------------------------

    async def _configure_system_proxy(self, port: int):
        """配置系统代理（跨平台）

        - macOS: 通过 networksetup 配置所有网络服务的 HTTP/HTTPS 代理
        - Linux: 设置 http_proxy/https_proxy 环境变量
        - Windows: Charles 自行管理代理注册，此处跳过

        Args:
            port: 代理端口号。
        """
        system = platform.system()
        try:
            if system == "Darwin":
                services = await self._get_network_services()
                for svc in services:
                    subprocess.run(
                        ["networksetup", "-setwebproxy", svc, "127.0.0.1", str(port)],
                        check=False,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxy", svc, "127.0.0.1", str(port)],
                        check=False,
                        capture_output=True,
                    )
            elif system == "Linux":
                os.environ["http_proxy"] = f"http://127.0.0.1:{port}"
                os.environ["https_proxy"] = f"http://127.0.0.1:{port}"
            # Windows: Charles handles its own proxy registration
            logger.info("系统代理已配置，端口 %d (平台: %s)", port, system)
        except Exception as e:
            logger.warning("配置系统代理失败: %s", e)

    async def _restore_system_proxy(self):
        """恢复系统代理（跨平台）

        - macOS: 关闭所有网络服务的 HTTP/HTTPS 代理
        - Linux: 清除 http_proxy/https_proxy 环境变量
        - Windows: Charles 自行管理，此处跳过
        """
        system = platform.system()
        try:
            if system == "Darwin":
                services = await self._get_network_services()
                for svc in services:
                    subprocess.run(
                        ["networksetup", "-setwebproxystate", svc, "off"],
                        check=False,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxystate", svc, "off"],
                        check=False,
                        capture_output=True,
                    )
            elif system == "Linux":
                os.environ.pop("http_proxy", None)
                os.environ.pop("https_proxy", None)
            logger.info("系统代理已恢复 (平台: %s)", system)
        except Exception as e:
            logger.warning("恢复系统代理失败: %s", e)

    @staticmethod
    async def _get_network_services() -> list[str]:
        """获取 macOS 网络服务列表

        调用 networksetup -listallnetworkservices 获取所有活跃的网络服务名称。
        过滤掉以 ``*`` 开头的禁用服务。

        Returns:
            活跃网络服务名称列表。
        """
        result = subprocess.run(
            ["networksetup", "-listallnetworkservices"],
            capture_output=True,
            text=True,
        )
        return [s for s in result.stdout.split("\n")[1:] if s and not s.startswith("*")]
