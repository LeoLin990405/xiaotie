"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，参考 OpenCode 设计优化。
支持多 LLM Provider、工具调用、事件驱动架构、MCP 协议。
"""

__version__ = "1.1.0"
__author__ = "Leo"


# MCP 支持 (延迟导入以避免循环依赖)
def get_mcp_module():
    """获取 MCP 模块"""
    from . import mcp

    return mcp


# LSP 支持 (延迟导入)
def get_lsp_module():
    """获取 LSP 模块"""
    from . import lsp

    return lsp


# 语义搜索支持 (延迟导入)
def get_search_module():
    """获取语义搜索模块"""
    from . import search

    return search


__all__ = [
    # Core Agent
    "Agent",
    "AgentConfig",
    "SessionState",
    # Builder API
    "AgentBuilder",
    "AgentHooks",
    "AgentSpec",
    "create_agent",
    # Core Schemas
    "LLMResponse",
    "Message",
    "ToolCall",
    "ToolResult",
    # Multi-Agent
    "MultiAgentSystem",
    "BaseAgent",
    # Lazy Loaders
    "get_mcp_module",
    "get_lsp_module",
    "get_search_module",
]
