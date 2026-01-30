"""MCP (Model Context Protocol) 支持模块

实现 MCP 协议客户端，支持连接 MCP 服务器并使用其提供的工具。
"""

from .protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    MCPTool,
    MCPToolCall,
    MCPToolResult,
)
from .transport import StdioTransport, TransportError
from .client import MCPClient, MCPClientError
from .tools import MCPToolWrapper

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
