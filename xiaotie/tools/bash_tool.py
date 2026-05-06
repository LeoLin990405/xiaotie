"""Bash 命令执行工具"""

from __future__ import annotations

import asyncio
import platform
import re
from typing import Any

from ..schema import ToolResult
from .base import Tool

# Dangerous command patterns that should be blocked or require confirmation
_DANGEROUS_PATTERNS = [
    r"\brm\s+-[rf]*\s+/\s",  # rm -rf /
    r"\bsudo\s+",  # sudo
    r"\bdd\s+if=",  # dd disk operations
    r"\bmkfs\b",  # format filesystem
    r"curl\s.*\|\s*(ba)?sh",  # curl pipe to shell
    r"wget\s.*\|\s*(ba)?sh",  # wget pipe to shell
    r"\bbase64\s.*\|\s*(ba)?sh",  # base64 decode to shell
    r">\s*/etc/",  # redirect to /etc
    r">\s*/dev/sd",  # redirect to block device
    r"\bnc\s+-[el]",  # netcat listen (reverse shell)
    r"python[23]?\s+-c\s+['\"].*import\s+os",  # python -c os commands
    r"\bchmod\s+[0-7]*7[0-7]*\s",  # overly permissive chmod
    r"\bkill\s+-9\s+1\b",  # kill init
    r"\bshutdown\b",  # shutdown
    r"\breboot\b",  # reboot
]


class BashTool(Tool):
    """执行 Shell 命令"""

    def __init__(self, sandbox_manager=None):
        super().__init__()
        self.is_windows = platform.system() == "Windows"
        self.shell_name = "PowerShell" if self.is_windows else "bash"
        self._sandbox = sandbox_manager  # Optional SandboxManager instance

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

    @staticmethod
    def _check_dangerous(command: str) -> str | None:
        """Return warning string if command matches a dangerous pattern, else None."""
        for pattern in _DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"Blocked dangerous command pattern: {pattern}"
        return None

    async def execute(self, command: str, timeout: int = 120) -> ToolResult:
        try:
            # Check for dangerous commands
            danger = self._check_dangerous(command)
            if danger:
                return ToolResult(success=False, error=danger)

            # 限制超时范围
            timeout = max(1, min(timeout, 600))

            # Use OS-level sandbox if available
            if self._sandbox and not self.is_windows:
                return await self._execute_sandboxed(command, timeout)

            # 创建子进程 (unsandboxed fallback)
            if self.is_windows:
                process = await asyncio.create_subprocess_exec(
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    command,
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
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(success=False, error=f"命令超时（{timeout}秒）")

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # 构建输出
            output = stdout_text
            if stderr_text:
                output += f"\n[stderr]:\n{stderr_text}"

            is_success = process.returncode == 0
            if not is_success:
                return ToolResult(
                    success=False, content=output, error=f"命令失败，退出码: {process.returncode}"
                )

            return ToolResult(success=True, content=output or "(无输出)")

        except Exception as e:
            return ToolResult(success=False, error=f"执行失败: {e}")

    async def _execute_sandboxed(self, command: str, timeout: int) -> ToolResult:
        """Execute command through the OS-level SandboxManager."""

        capabilities = self._sandbox.get_capabilities_for_tool("bash")
        result = await self._sandbox.execute_shell(
            shell_command=command,
            capabilities=capabilities,
            timeout=float(timeout),
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]:\n{result.stderr}"

        if not result.success:
            return ToolResult(
                success=False,
                content=output,
                error=f"命令失败，退出码: {result.exit_code}",
            )

        return ToolResult(success=True, content=output or "(无输出)")
