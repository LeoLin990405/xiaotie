"""MCP 客户端实现

提供与 MCP 服务器交互的高级 API。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .protocol import (
    LATEST_PROTOCOL_VERSION,
    ClientCapabilities,
    Implementation,
    InitializeParams,
    InitializeResult,
    JSONRPCNotification,
    JSONRPCRequest,
    ListToolsResult,
    MCPTool,
    MCPToolResult,
)
from .transport import StdioTransport

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """MCP 客户端错误"""
    pass


class MCPClient:
    """MCP 客户端

    用于连接 MCP 服务器并调用其提供的工具。

    使用示例:
        async with MCPClient(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem"]) as client:
            tools = await client.list_tools()
            result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
    """

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Union[str, Path]] = None,
        client_name: str = "xiaotie",
        client_version: str = "0.5.0",
        timeout: float = 30.0,
    ):
        """初始化 MCP 客户端

        Args:
            command: MCP 服务器命令
            args: 命令参数
            env: 环境变量
            cwd: 工作目录
            client_name: 客户端名称
            client_version: 客户端版本
            timeout: 请求超时时间 (秒)
        """
        self._transport = StdioTransport(
            command=command,
            args=args,
            env=env,
            cwd=cwd,
        )
        self._client_info = Implementation(name=client_name, version=client_version)
        self._timeout = timeout

        # 状态
        self._initialized = False
        self._server_info: Optional[Implementation] = None
        self._server_capabilities: Optional[Dict[str, Any]] = None
        self._tools: Dict[str, MCPTool] = {}
        self._request_id = 0
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._transport.is_connected

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def server_info(self) -> Optional[Implementation]:
        """服务器信息"""
        return self._server_info

    @property
    def tools(self) -> Dict[str, MCPTool]:
        """已发现的工具"""
        return self._tools

    def _next_id(self) -> int:
        """生成下一个请求 ID"""
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """发送请求并等待响应"""
        async with self._lock:
            request_id = self._next_id()
            request = JSONRPCRequest(
                id=request_id,
                method=method,
                params=params,
            )

            await self._transport.send(request)
            response = await self._transport.receive(timeout=self._timeout)

            # 检查响应 ID
            if response.id != request_id:
                raise MCPClientError(f"响应 ID 不匹配: 期望 {request_id}, 收到 {response.id}")

            # 检查错误
            if response.error:
                raise MCPClientError(
                    f"服务器错误 [{response.error.code}]: {response.error.message}"
                )

            return response.result

    async def _send_notification(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发送通知 (不等待响应)"""
        notification = JSONRPCNotification(
            method=method,
            params=params,
        )
        await self._transport.send(notification)

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        await self._transport.connect()

    async def disconnect(self) -> None:
        """断开与 MCP 服务器的连接"""
        self._initialized = False
        self._server_info = None
        self._server_capabilities = None
        self._tools.clear()
        await self._transport.disconnect()

    async def initialize(self) -> InitializeResult:
        """初始化 MCP 会话

        执行 MCP 协议握手，协商能力。
        """
        if not self.is_connected:
            raise MCPClientError("未连接到服务器")

        if self._initialized:
            logger.warning("已经初始化，跳过")
            return InitializeResult(
                protocolVersion=LATEST_PROTOCOL_VERSION,
                capabilities=self._server_capabilities or {},
                serverInfo=self._server_info or Implementation(name="unknown", version="0.0.0"),
            )

        # 发送初始化请求
        params = InitializeParams(
            protocolVersion=LATEST_PROTOCOL_VERSION,
            capabilities=ClientCapabilities(),
            clientInfo=self._client_info,
        )

        result = await self._send_request("initialize", params.model_dump())

        # 解析结果
        init_result = InitializeResult(**result)
        self._server_info = init_result.serverInfo
        self._server_capabilities = init_result.capabilities.model_dump() if init_result.capabilities else {}

        logger.info(
            f"MCP 初始化成功: {init_result.serverInfo.name} v{init_result.serverInfo.version}"
        )

        # 发送 initialized 通知
        await self._send_notification("notifications/initialized")

        self._initialized = True
        return init_result

    async def list_tools(self, cursor: Optional[str] = None) -> List[MCPTool]:
        """获取服务器提供的工具列表

        Args:
            cursor: 分页游标

        Returns:
            工具列表
        """
        if not self._initialized:
            raise MCPClientError("未初始化，请先调用 initialize()")

        params = {}
        if cursor:
            params["cursor"] = cursor

        result = await self._send_request("tools/list", params if params else None)

        # 解析结果
        list_result = ListToolsResult(**result)

        # 缓存工具
        for tool in list_result.tools:
            self._tools[tool.name] = tool

        logger.info(f"发现 {len(list_result.tools)} 个工具")

        return list_result.tools

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> MCPToolResult:
        """调用工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self._initialized:
            raise MCPClientError("未初始化，请先调用 initialize()")

        params = {"name": name}
        if arguments:
            params["arguments"] = arguments

        result = await self._send_request("tools/call", params)

        # 解析结果
        tool_result = MCPToolResult(**result)

        return tool_result

    async def __aenter__(self) -> "MCPClient":
        """异步上下文管理器入口"""
        await self.connect()
        await self.initialize()
        await self.list_tools()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()


class MCPClientManager:
    """MCP 客户端管理器

    管理多个 MCP 服务器连接。
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}

    @property
    def clients(self) -> Dict[str, MCPClient]:
        """所有客户端"""
        return self._clients

    def get_all_tools(self) -> Dict[str, tuple[str, MCPTool]]:
        """获取所有服务器的工具

        Returns:
            Dict[tool_name, (server_name, tool)]
        """
        all_tools: Dict[str, tuple[str, MCPTool]] = {}
        for server_name, client in self._clients.items():
            for tool_name, tool in client.tools.items():
                # 使用 server_name:tool_name 格���避免冲突
                full_name = f"{server_name}:{tool_name}"
                all_tools[full_name] = (server_name, tool)
        return all_tools

    async def add_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Union[str, Path]] = None,
    ) -> MCPClient:
        """添加并连接 MCP 服务器

        Args:
            name: 服务器名称 (用于标识)
            command: 服务器命令
            args: 命令参数
            env: 环境变量
            cwd: 工作目录

        Returns:
            MCPClient 实例
        """
        if name in self._clients:
            logger.warning(f"服务器 '{name}' 已存在，将替换")
            await self.remove_server(name)

        client = MCPClient(
            command=command,
            args=args,
            env=env,
            cwd=cwd,
        )

        await client.connect()
        await client.initialize()
        await client.list_tools()

        self._clients[name] = client
        logger.info(f"已添加 MCP 服务器: {name}")

        return client

    async def remove_server(self, name: str) -> None:
        """移除 MCP 服务器

        Args:
            name: 服务器名称
        """
        if name not in self._clients:
            return

        client = self._clients.pop(name)
        await client.disconnect()
        logger.info(f"已移除 MCP 服务器: {name}")

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> MCPToolResult:
        """调用指定服务器的工具

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if server_name not in self._clients:
            raise MCPClientError(f"服务器 '{server_name}' 不存在")

        return await self._clients[server_name].call_tool(tool_name, arguments)

    async def disconnect_all(self) -> None:
        """断开所有服务器连接"""
        for name in list(self._clients.keys()):
            await self.remove_server(name)

    async def __aenter__(self) -> "MCPClientManager":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.disconnect_all()
