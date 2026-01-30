"""Bash 命令执行工具"""

from __future__ import annotations

import asyncio
import platform
from typing import Any

from ..schema import ToolResult
from .base import Tool


class BashTool(Tool):
    """执行 Shell 命令"""

    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.shell_name = "PowerShell" if self.is_windows else "bash"

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return f"执行 {self.shell_name} 命令。用于 git、npm、docker 等终端操作。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": f"要执行的 {self.shell_name} 命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 120，最大 600",
                    "default": 120,
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: int = 120) -> ToolResult:
        try:
            # 限制超时范围
            timeout = max(1, min(timeout, 600))

            # 创建子进程
            if self.is_windows:
                process = await asyncio.create_subprocess_exec(
                    "powershell.exe", "-NoProfile", "-Command", command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"命令超时（{timeout}秒）"
                )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # 构建输出
            output = stdout_text
            if stderr_text:
                output += f"\n[stderr]:\n{stderr_text}"

            is_success = process.returncode == 0
            if not is_success:
                return ToolResult(
                    success=False,
                    content=output,
                    error=f"命令失败，退出码: {process.returncode}"
                )

            return ToolResult(success=True, content=output or "(无输出)")

        except Exception as e:
            return ToolResult(success=False, error=f"执行失败: {e}")
