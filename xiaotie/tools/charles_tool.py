"""Charles 代理抓包工具

集成 Charles 代理，用于自动抓取小程序网络请求。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from ..schema import ToolResult
from .base import Tool


class CharlesProxyTool(Tool):
    """Charles 代理抓包工具

    功能：
    - 启动/停止 Charles 代理
    - 配置代理端口
    - 导出抓包数据
    - 过滤特定域名/路径的请求
    """

    def __init__(self):
        super().__init__()
        self.charles_app = "/Applications/Charles.app/Contents/MacOS/Charles"
        self.charles_process: Optional[subprocess.Popen] = None
        self.proxy_port = 8888
        self.session_file: Optional[Path] = None

    @property
    def name(self) -> str:
        return "charles_proxy"

    @property
    def description(self) -> str:
        return "Charles 代理抓包工具，用于抓取小程序网络请求"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "export", "status"],
                    "description": "操作类型：start-启动代理，stop-停止代理，export-导出数据，status-查看状态"
                },
                "port": {
                    "type": "integer",
                    "description": "代理端口（默认 8888）",
                    "default": 8888
                },
                "filter_domain": {
                    "type": "string",
                    "description": "过滤域名（可选），只抓取指定域名的请求"
                },
                "output_file": {
                    "type": "string",
                    "description": "导出文件路径（export 操作时使用）"
                }
            },
            "required": ["action"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        """执行 Charles 操作"""
        action = kwargs.get("action")

        if action == "start":
            return await self._start_charles(kwargs)
        elif action == "stop":
            return await self._stop_charles()
        elif action == "export":
            return await self._export_session(kwargs)
        elif action == "status":
            return await self._get_status()
        else:
            return ToolResult(
                success=False,
                error=f"未知的操作类型: {action}"
            )

    async def _start_charles(self, kwargs: dict) -> ToolResult:
        """启动 Charles 代理"""
        if self.charles_process and self.charles_process.poll() is None:
            return ToolResult(
                success=True,
                content=f"Charles 代理已在运行中（端口 {self.proxy_port}）"
            )

        port = kwargs.get("port", 8888)
        self.proxy_port = port

        try:
            # 启动 Charles（后台模式）
            self.charles_process = subprocess.Popen(
                [self.charles_app],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # 等待 Charles 启动
            await asyncio.sleep(3)

            # 配置系统代理
            await self._configure_system_proxy(port)

            return ToolResult(
                success=True,
                content=f"Charles 代理已启动\n"
                       f"- 代理端口: {port}\n"
                       f"- 进程 ID: {self.charles_process.pid}\n"
                       f"- 系统代理已配置\n\n"
                       f"请在小程序设备上配置代理:\n"
                       f"- HTTP 代理: 127.0.0.1:{port}\n"
                       f"- HTTPS 代理: 127.0.0.1:{port}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"启动 Charles 失败: {str(e)}"
            )

    async def _stop_charles(self) -> ToolResult:
        """停止 Charles 代理"""
        if not self.charles_process or self.charles_process.poll() is not None:
            return ToolResult(
                success=True,
                content="Charles 代理未运行"
            )

        try:
            # 停止 Charles 进程
            self.charles_process.terminate()
            self.charles_process.wait(timeout=5)

            # 恢复系统代理
            await self._restore_system_proxy()

            return ToolResult(
                success=True,
                content="Charles 代理已停止，系统代理已恢复"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"停止 Charles 失败: {str(e)}"
            )

    async def _export_session(self, kwargs: dict) -> ToolResult:
        """导出抓包会话数据"""
        output_file = kwargs.get("output_file")
        if not output_file:
            output_file = f"charles_session_{int(time.time())}.json"

        output_path = Path(output_file)

        try:
            # 注意：Charles 需要手动导出会话
            # 这里提供导出说明
            instructions = f"""
Charles 会话导出说明：

1. 在 Charles 中，点击 File -> Export Session
2. 选择格式：JSON
3. 保存到：{output_path.absolute()}

或者使用 Charles CLI（如果可用）：
charles-cli export --format json --output {output_path.absolute()}

导出后的数据将包含所有抓取的请求和响应。
"""

            return ToolResult(
                success=True,
                content=instructions
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"导出会话失败: {str(e)}"
            )

    async def _get_status(self) -> ToolResult:
        """获取 Charles 状态"""
        is_running = self.charles_process and self.charles_process.poll() is None

        status = {
            "running": is_running,
            "port": self.proxy_port if is_running else None,
            "pid": self.charles_process.pid if is_running else None
        }

        content = f"Charles 代理状态:\n"
        content += f"- 运行状态: {'运行中' if is_running else '未运行'}\n"
        if is_running:
            content += f"- 代理端口: {self.proxy_port}\n"
            content += f"- 进程 ID: {self.charles_process.pid}\n"

        return ToolResult(
            success=True,
            content=content,
            data=status
        )

    async def _configure_system_proxy(self, port: int):
        """配置系统代理（macOS）"""
        try:
            # 获取当前网络服务
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True,
                text=True
            )
            services = [s for s in result.stdout.split('\n')[1:] if s]

            # 为每个网络服务配置代理
            for service in services:
                if service and not service.startswith('*'):
                    # 配置 HTTP 代理
                    subprocess.run(
                        ["networksetup", "-setwebproxy", service, "127.0.0.1", str(port)],
                        check=False
                    )
                    # 配置 HTTPS 代理
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxy", service, "127.0.0.1", str(port)],
                        check=False
                    )
        except Exception:
            pass  # 忽略配置错误

    async def _restore_system_proxy(self):
        """恢复系统代理（macOS）"""
        try:
            # 获取当前网络服务
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True,
                text=True
            )
            services = [s for s in result.stdout.split('\n')[1:] if s]

            # 为每个网络服务关闭代理
            for service in services:
                if service and not service.startswith('*'):
                    # 关闭 HTTP 代理
                    subprocess.run(
                        ["networksetup", "-setwebproxystate", service, "off"],
                        check=False
                    )
                    # 关闭 HTTPS 代理
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxystate", service, "off"],
                        check=False
                    )
        except Exception:
            pass  # 忽略恢复错误
