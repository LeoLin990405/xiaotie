"""MCP 协议类型定义

基于 JSON-RPC 2.0 和 MCP 规范实现。
参考: https://modelcontextprotocol.io/specification/
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# =============================================================================
# JSON-RPC 2.0 基础类型
# =============================================================================


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 请求"""

    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCNotification(BaseModel):
    """JSON-RPC 2.0 通知 (无 id)"""

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 错误"""

    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 响应"""

    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int, None] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


# =============================================================================
# MCP 协议版本
# =============================================================================

LATEST_PROTOCOL_VERSION = "2025-03-26"


# =============================================================================
# MCP 实现信息
# =============================================================================


class Implementation(BaseModel):
    """客户端/服务器实现信息"""

    name: str
    version: str


# =============================================================================
# MCP 能力 (Capabilities)
# =============================================================================


class ToolsCapability(BaseModel):
    """工具能力"""

    listChanged: bool = False


class ResourcesCapability(BaseModel):
    """资源能力"""

    subscribe: bool = False
    listChanged: bool = False


class PromptsCapability(BaseModel):
    """提示能力"""

    listChanged: bool = False


class LoggingCapability(BaseModel):
    """日志能力"""

    pass


class SamplingCapability(BaseModel):
    """采样能力"""

    pass


class ElicitationCapability(BaseModel):
    """引出能力"""

    pass


class ClientCapabilities(BaseModel):
    """客户端能力"""

    sampling: Optional[SamplingCapability] = None
    elicitation: Optional[ElicitationCapability] = None
    experimental: Optional[Dict[str, Any]] = None


class ServerCapabilities(BaseModel):
    """服务器能力"""

    tools: Optional[ToolsCapability] = None
    resources: Optional[ResourcesCapability] = None
    prompts: Optional[PromptsCapability] = None
    logging: Optional[LoggingCapability] = None
    experimental: Optional[Dict[str, Any]] = None


# =============================================================================
# MCP 初始化
# =============================================================================


class InitializeParams(BaseModel):
    """初始化请求参数"""

    protocolVersion: str = LATEST_PROTOCOL_VERSION
    capabilities: ClientCapabilities = Field(default_factory=ClientCapabilities)
    clientInfo: Implementation


class InitializeResult(BaseModel):
    """初始化响应结果"""

    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: Implementation
    instructions: Optional[str] = None


# =============================================================================
# MCP 工具类型
# =============================================================================


class MCPTool(BaseModel):
    """MCP 工具定义"""

    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
        }
    )
    # 可选字段
    title: Optional[str] = None
    outputSchema: Optional[Dict[str, Any]] = None


class ListToolsResult(BaseModel):
    """工具列表响应"""

    tools: List[MCPTool]
    nextCursor: Optional[str] = None


# =============================================================================
# MCP 工具调用
# =============================================================================


class MCPToolCall(BaseModel):
    """工具调用参数"""

    name: str
    arguments: Optional[Dict[str, Any]] = None


class TextContent(BaseModel):
    """文本内容"""

    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    """图片内容"""

    type: Literal["image"] = "image"
    data: str  # base64 编码
    mimeType: str


class ResourceContent(BaseModel):
    """资源内容"""

    type: Literal["resource"] = "resource"
    resource: Dict[str, Any]


# 内容类型联合
ContentType = Union[TextContent, ImageContent, ResourceContent]


class MCPToolResult(BaseModel):
    """工具调用结果"""

    content: List[ContentType] = Field(default_factory=list)
    isError: bool = False


# =============================================================================
# MCP 资源类型 (可选，为未来扩展准备)
# =============================================================================


class MCPResource(BaseModel):
    """MCP 资源定义"""

    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = None


class ListResourcesResult(BaseModel):
    """资源列表响应"""

    resources: List[MCPResource]
    nextCursor: Optional[str] = None


# =============================================================================
# MCP 提示类型 (可选，为未来扩展准备)
# =============================================================================


class MCPPromptArgument(BaseModel):
    """提示参数"""

    name: str
    description: Optional[str] = None
    required: bool = False


class MCPPrompt(BaseModel):
    """MCP 提示定义"""

    name: str
    description: Optional[str] = None
    arguments: Optional[List[MCPPromptArgument]] = None


class ListPromptsResult(BaseModel):
    """提示列表响应"""

    prompts: List[MCPPrompt]
    nextCursor: Optional[str] = None
