"""MCP 工具包装器

将 MCP 工具包装为小铁 Tool 接口，使其可以被 Agent 使用。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..schema import ToolResult
from ..tools.base import Tool
from .protocol import MCPTool, MCPToolResult, TextContent
from .client import MCPClient, MCPClientManager, MCPClientError

logger = logging.getLogger(__name__)


class MCPToolWrapper(Tool):
    """MCP 工具包装器

    将 MCP 工具包装为小铁 Tool 接口。
    """

    def __init__(
        self,
        mcp_tool: MCPTool,
        client: MCPClient,
        server_name: str = "mcp",
    ):
        """初始化 MCP 工具包装器

        Args:
            mcp_tool: MCP 工具定义
            client: MCP 客户端
            server_name: 服务器名称 (用于工具名称前缀)
        """
        self._mcp_tool = mcp_tool
        self._client = client
        self._server_name = server_name

    @property
    def name(self) -> str:
        """工具名称 (带服务器前缀)"""
        return f"mcp_{self._server_name}_{self._mcp_tool.name}"

    @property
    def description(self) -> str:
        """工具描述"""
        desc = self._mcp_tool.description or f"MCP 工具: {self._mcp_tool.name}"
        return f"[MCP:{self._server_name}] {desc}"

    @property
    def parameters(self) -> Dict[str, Any]:
        """参数 JSON Schema"""
        return self._mcp_tool.inputSchema

    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        try:
            # 调用 MCP 工具
            result = await self._client.call_tool(
                name=self._mcp_tool.name,
                arguments=kwargs if kwargs else None,
            )

            # 转换结果
            return self._convert_result(result)

        except MCPClientError as e:
            logger.error(f"MCP 工具调用失败: {e}")
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            logger.exception(f"MCP 工具执行异常: {e}")
            return ToolResult(success=False, error=f"执行异常: {e}")

    def _convert_result(self, mcp_result: MCPToolResult) -> ToolResult:
        """转换 MCP 结果为 ToolResult"""
        if mcp_result.isError:
            # 提取错误信息
            error_text = self._extract_text(mcp_result)
            return ToolResult(success=False, error=error_text or "未知错误")

        # 提取文本内容
        content = self._extract_text(mcp_result)
        return ToolResult(success=True, content=content)

    def _extract_text(self, mcp_result: MCPToolResult) -> str:
        """从 MCP 结果中提取文本"""
        texts = []
        for item in mcp_result.content:
            if isinstance(item, TextContent):
                texts.append(item.text)
            elif isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif hasattr(item, "text"):
                texts.append(item.text)
        return "\n".join(texts) if texts else ""


def create_mcp_tools(
    client: MCPClient,
    server_name: str = "mcp",
) -> list[MCPToolWrapper]:
    """从 MCP 客户端创建工具列表

    Args:
        client: MCP 客户端
        server_name: 服务器名称

    Returns:
        MCPToolWrapper 列表
    """
    tools = []
    for mcp_tool in client.tools.values():
        wrapper = MCPToolWrapper(
            mcp_tool=mcp_tool,
            client=client,
            server_name=server_name,
        )
        tools.append(wrapper)
        logger.debug(f"创建 MCP 工具: {wrapper.name}")

    return tools


async def create_mcp_tools_from_config(
    servers: Dict[str, Dict[str, Any]],
) -> tuple[MCPClientManager, list[MCPToolWrapper]]:
    """从配置创建 MCP 工具

    Args:
        servers: 服务器配置字典
            {
                "server_name": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    "env": {"KEY": "value"},
                    "cwd": "/path/to/dir"
                }
            }

    Returns:
        (MCPClientManager, 工具列表)
    """
    manager = MCPClientManager()
    all_tools: list[MCPToolWrapper] = []

    for server_name, config in servers.items():
        try:
            client = await manager.add_server(
                name=server_name,
                command=config["command"],
                args=config.get("args"),
                env=config.get("env"),
                cwd=config.get("cwd"),
            )

            tools = create_mcp_tools(client, server_name)
            all_tools.extend(tools)

            logger.info(f"从 MCP 服务器 '{server_name}' 加载了 {len(tools)} 个工具")

        except Exception as e:
            logger.error(f"连接 MCP 服务器 '{server_name}' 失败: {e}")

    return manager, all_tools
