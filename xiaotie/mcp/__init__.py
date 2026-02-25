"""MCP (Model Context Protocol) 支持模块

实现 MCP 协议客户端，支持连接 MCP 服务器并使用其提供的工具。
"""

from .client import MCPClient, MCPClientError
from .protocol import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolCall,
    MCPToolResult,
)
from .tools import MCPToolWrapper
from .transport import StdioTransport, TransportError

__all__ = [
    # 协议类型
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "MCPTool",
    "MCPToolCall",
    "MCPToolResult",
    # 传输层
    "StdioTransport",
    "TransportError",
    # 客户端
    "MCPClient",
    "MCPClientError",
    # 工具
    "MCPToolWrapper",
]
