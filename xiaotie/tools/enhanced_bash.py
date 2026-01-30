"""增强版 Bash 工具

参考 Claude Code 的设计：
- 持久化 Shell 会话
- 命令风险分类
- 注入过滤
- 审计日志
"""

from __future__ import annotations

import asyncio
import os
import platform
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import Tool
from ..schema import ToolResult


@dataclass
class CommandLog:
    """命令日志"""
    command: str
    output: str
    exit_code: int
    duration: float
    timestamp: float = field(default_factory=time.time)


class PersistentShell:
    """持久化 Shell 会话"""

    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or os.getcwd()
        self.is_windows = platform.system() == "Windows"
        self._process: Optional[asyncio.subprocess.Process] = None
        self._env: Dict[str, str] = dict(os.environ)
        self._history: List[CommandLog] = []
        self._lock = asyncio.Lock()

    async def start(self):
        """启动 Shell 进程"""
        if self._process is not None:
            return

        if self.is_windows:
            self._process = await asyncio.create_subprocess_exec(
                "powershell.exe", "-NoProfile", "-NoLogo",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=self._env,
            )
        else:
            self._process = await asyncio.create_subprocess_exec(
                "/bin/bash", "--norc", "--noprofile",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=self._env,
            )

    async def stop(self):
        """停止 Shell 进程"""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None

    async def execute(
        self,
        command: str,
        timeout: int = 120,
    ) -> Tuple[int, str, str]:
        """执行命令

        Returns:
            (exit_code, stdout, stderr)
        """
        async with self._lock:
            if self._process is None:
                await self.start()

            start_time = time.time()

            # 使用标记来分隔输出
            marker = f"__XIAOTIE_END_{int(time.time() * 1000)}__"

            if self.is_windows:
                full_command = f"{command}\necho {marker}\n$LASTEXITCODE\n"
            else:
                full_command = f"{command}\necho {marker}\necho $?\n"

            try:
                self._process.stdin.write(full_command.encode())
                await self._process.stdin.drain()

                # 读取输出直到标记
                output_lines = []
                exit_code = 0

                async def read_until_marker():
                    nonlocal exit_code
                    while True:
                        line = await asyncio.wait_for(
                            self._process.stdout.readline(),
                            timeout=timeout
                        )
                        if not line:
                            break
                        line_str = line.decode("utf-8", errors="replace").rstrip()
                        if marker in line_str:
                            # 下一行是退出码
                            exit_line = await self._process.stdout.readline()
                            try:
                                exit_code = int(exit_line.decode().strip())
                            except ValueError:
                                exit_code = 0
                            break
                        output_lines.append(line_str)

                await asyncio.wait_for(read_until_marker(), timeout=timeout)

                stdout = "\n".join(output_lines)
                stderr = ""

                # 记录日志
                duration = time.time() - start_time
                self._history.append(CommandLog(
                    command=command,
                    output=stdout,
                    exit_code=exit_code,
                    duration=duration,
                ))

                return exit_code, stdout, stderr

            except asyncio.TimeoutError:
                # 超时，重启 Shell
                await self.stop()
                return -1, "", f"命令超时（{timeout}秒）"

    def get_history(self, limit: int = 10) -> List[CommandLog]:
        """获取命令历史"""
        return self._history[-limit:]

    def set_env(self, key: str, value: str):
        """设置环境变量"""
        self._env[key] = value

    def get_cwd(self) -> str:
        """获取当前工作目录"""
        return self.working_dir


# 命令注入检测模式
INJECTION_PATTERNS = [
    r"`[^`]+`",           # 反引号命令替换
    r"\$\([^)]+\)",       # $() 命令替换
    r";\s*[a-z]",         # 分号后跟命令
    r"\|\s*[a-z]",        # 管道后跟命令（可能是恶意的）
    r"&&\s*rm\s",         # && 后跟 rm
    r"\|\|\s*rm\s",       # || 后跟 rm
]


def check_injection(command: str) -> List[str]:
    """检查命令注入

    Returns:
        检测到的可疑模式列表
    """
    suspicious = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            suspicious.append(pattern)
    return suspicious


class EnhancedBashTool(Tool):
    """增强版 Bash 工具"""

    def __init__(
        self,
        working_dir: Optional[str] = None,
        persistent: bool = True,
        check_injection: bool = True,
    ):
        self.working_dir = working_dir or os.getcwd()
        self.persistent = persistent
        self.check_injection_enabled = check_injection
        self.is_windows = platform.system() == "Windows"
        self.shell_name = "PowerShell" if self.is_windows else "bash"

        # 持久化 Shell
        self._shell: Optional[PersistentShell] = None
        if persistent:
            self._shell = PersistentShell(working_dir)

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return f"""执行 {self.shell_name} 命令。

特性：
- 持久化会话：工作目录和环境变量在命令间保持
- 安全检查：检测潜在的命令注入
- 超时控制：默认 120 秒，最大 600 秒

注意：
- 避免使用交互式命令（如 vim, less）
- 长时间运行的命令请设置合适的 timeout
- 危险命令（rm -rf, sudo 等）需要用户确认"""

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
                "working_dir": {
                    "type": "string",
                    "description": "工作目录（可选，默认使用当前目录）",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        timeout: int = 120,
        working_dir: Optional[str] = None,
    ) -> ToolResult:
        # 限制超时范围
        timeout = max(1, min(timeout, 600))

        # 检查命令注入
        if self.check_injection_enabled:
            suspicious = check_injection(command)
            if suspicious:
                return ToolResult(
                    success=False,
                    error=f"检测到可疑命令模式: {suspicious}。如果这是预期行为，请确认后重试。"
                )

        try:
            if self.persistent and self._shell:
                # 使用持久化 Shell
                exit_code, stdout, stderr = await self._shell.execute(command, timeout)
            else:
                # 使用一次性进程
                exit_code, stdout, stderr = await self._execute_oneshot(
                    command, timeout, working_dir
                )

            # 构建输出
            output = stdout
            if stderr:
                output += f"\n[stderr]:\n{stderr}"

            if exit_code != 0:
                return ToolResult(
                    success=False,
                    content=output,
                    error=f"命令失败，退出码: {exit_code}"
                )

            return ToolResult(success=True, content=output or "(无输出)")

        except Exception as e:
            return ToolResult(success=False, error=f"执行失败: {e}")

    async def _execute_oneshot(
        self,
        command: str,
        timeout: int,
        working_dir: Optional[str],
    ) -> Tuple[int, str, str]:
        """一次性执行命令"""
        cwd = working_dir or self.working_dir

        if self.is_windows:
            process = await asyncio.create_subprocess_exec(
                "powershell.exe", "-NoProfile", "-Command", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return -1, "", f"命令超时（{timeout}秒）"

        return (
            process.returncode,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    def get_history(self, limit: int = 10) -> List[CommandLog]:
        """获取命令历史"""
        if self._shell:
            return self._shell.get_history(limit)
        return []

    async def cleanup(self):
        """清理资源"""
        if self._shell:
            await self._shell.stop()
