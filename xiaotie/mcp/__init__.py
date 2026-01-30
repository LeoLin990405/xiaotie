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
    # Protocol types
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "MCPTool",
    "MCPToolCall",
    "MCPToolResult",
    # Transport
    "StdioTransport",
    "TransportError",
    # Client
    "MCPClient",
    "MCPClientError",
    # Tools
    "MCPToolWrapper",
]
