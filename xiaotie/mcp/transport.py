"""MCP 传输层实现

支持 Stdio 传输协议，用于与本地 MCP 服务器通信。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Union

from .protocol import JSONRPCNotification, JSONRPCRequest, JSONRPCResponse

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """传输层错误"""

    pass


class Transport(ABC):
    """传输层抽象基类"""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送消息"""
        pass

    @abstractmethod
    async def receive(self) -> JSONRPCResponse:
        """接收消息"""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """是否已连接"""
        pass


# 默认继承的环境变量
DEFAULT_INHERITED_ENV_VARS = (
    ["HOME", "LOGNAME", "PATH", "SHELL", "TERM", "USER"]
    if sys.platform != "win32"
    else [
        "APPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PROCESSOR_ARCHITECTURE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "USERNAME",
        "USERPROFILE",
    ]
)

# 进程终止超时
PROCESS_TERMINATION_TIMEOUT = 2.0


def get_default_environment() -> Dict[str, str]:
    """获取默认环境变量"""
    env: Dict[str, str] = {}
    for key in DEFAULT_INHERITED_ENV_VARS:
        value = os.environ.get(key)
        if value is not None and not value.startswith("()"):
            env[key] = value
    return env


class StdioTransport(Transport):
    """Stdio 传输实现

    通过子进程的 stdin/stdout 与 MCP 服务器通信。
    """

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Union[str, Path]] = None,
        encoding: str = "utf-8",
    ):
        """初始化 Stdio 传输

        Args:
            command: 服务器命令
            args: 命令参数
            env: 环境变量 (会与默认环境变量合并)
            cwd: 工作目录
            encoding: 编码
        """
        self.command = command
        self.args = args or []
        self.env = {**get_default_environment(), **(env or {})}
        self.cwd = cwd
        self.encoding = encoding

        self._process: Optional[asyncio.subprocess.Process] = None
        self._read_buffer = ""
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._process is not None and self._process.returncode is None

    async def connect(self) -> None:
        """启动子进程并建立连接"""
        if self.is_connected:
            return

        try:
            # 构建完整命令
            cmd = [self.command] + self.args

            logger.debug(f"启动 MCP 服务器: {' '.join(cmd)}")

            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
            )

            logger.info(f"MCP 服务器已启动 (PID: {self._process.pid})")

        except FileNotFoundError:
            raise TransportError(f"找不到命令: {self.command}")
        except PermissionError:
            raise TransportError(f"没有执行权限: {self.command}")
        except Exception as e:
            raise TransportError(f"启动服务器失败: {e}")

    async def disconnect(self) -> None:
        """断开连接并终止子进程"""
        if self._process is None:
            return

        try:
            # 关闭 stdin
            if self._process.stdin:
                self._process.stdin.close()
                await self._process.stdin.wait_closed()

            # 等待进程退出
            try:
                await asyncio.wait_for(self._process.wait(), timeout=PROCESS_TERMINATION_TIMEOUT)
            except asyncio.TimeoutError:
                # 超时则强制终止
                logger.warning("MCP 服务器未响应，强制终止")
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    self._process.kill()

            logger.info("MCP 服务器已断开")

        except ProcessLookupError:
            pass
        finally:
            self._process = None
            self._read_buffer = ""

    async def send(self, message: Union[JSONRPCRequest, JSONRPCNotification]) -> None:
        """发送 JSON-RPC 消息"""
        if not self.is_connected or self._process.stdin is None:
            raise TransportError("未连接到服务器")

        try:
            # 序列化消息
            json_str = message.model_dump_json(exclude_none=True)
            data = (json_str + "\n").encode(self.encoding)

            logger.debug(f"发送: {json_str[:200]}...")

            # 写入 stdin
            self._process.stdin.write(data)
            await self._process.stdin.drain()

        except Exception as e:
            raise TransportError(f"发送消息失败: {e}")

    async def receive(self, timeout: Optional[float] = 30.0) -> JSONRPCResponse:
        """接收 JSON-RPC 响应"""
        if not self.is_connected or self._process.stdout is None:
            raise TransportError("未连接到服务器")

        async with self._lock:
            try:
                # 读取直到获得完整的一行
                while "\n" not in self._read_buffer:
                    if timeout:
                        chunk = await asyncio.wait_for(
                            self._process.stdout.read(4096), timeout=timeout
                        )
                    else:
                        chunk = await self._process.stdout.read(4096)

                    if not chunk:
                        raise TransportError("服务器连接已关闭")

                    self._read_buffer += chunk.decode(self.encoding)

                # 提取第一行
                line, self._read_buffer = self._read_buffer.split("\n", 1)

                logger.debug(f"接收: {line[:200]}...")

                # 解析 JSON-RPC 响应
                data = json.loads(line)
                return JSONRPCResponse(**data)

            except asyncio.TimeoutError:
                raise TransportError("接收响应超时")
            except json.JSONDecodeError as e:
                raise TransportError(f"JSON 解析失败: {e}")
            except Exception as e:
                raise TransportError(f"接收消息失败: {e}")

    async def read_stderr(self) -> str:
        """读取 stderr 输出 (用于调试)"""
        if not self.is_connected or self._process.stderr is None:
            return ""

        try:
            # 非阻塞读取
            data = await asyncio.wait_for(self._process.stderr.read(4096), timeout=0.1)
            return data.decode(self.encoding) if data else ""
        except asyncio.TimeoutError:
            return ""

    async def __aenter__(self) -> "StdioTransport":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()
