"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，参考 OpenCode 设计优化。
支持多 LLM Provider、工具调用、事件驱动架构、MCP 协议。
"""

__version__ = "0.9.0-dev"
__author__ = "Leo"

from .agent import Agent, AgentConfig, SessionState
from .builder import AgentBuilder, AgentHooks, AgentSpec, create_agent
from .custom_commands import (
    CustomCommand,
    CustomCommandExecutor,
    CustomCommandManager,
)
from .events import (
    AgentStartEvent,
    AgentStepEvent,
    Event,
    EventBroker,
    EventType,
    MessageDeltaEvent,
    ThinkingDeltaEvent,
    TokenUpdateEvent,
    ToolCompleteEvent,
    ToolStartEvent,
    get_event_broker,
    set_event_broker,
)
from .feedback import (
    FeedbackConfig,
    FeedbackLoop,
    LintResult,
    TestResult,
)
from .permissions import (
    PermissionManager,
    PermissionRequest,
    PermissionRule,
    RiskLevel,
)
from .profiles import (
    ProfileConfig,
    ProfileManager,
    create_preset_profiles,
)
from .schema import LLMResponse, Message, ToolCall, ToolResult


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
    # Agent
    "Agent",
    "AgentConfig",
    "SessionState",
    # Builder
    "AgentBuilder",
    "AgentSpec",
    "AgentHooks",
    "create_agent",
    # Schema
    "Message",
    "ToolCall",
    "LLMResponse",
    "ToolResult",
    # Events
    "EventBroker",
    "EventType",
    "Event",
    "AgentStartEvent",
    "AgentStepEvent",
    "MessageDeltaEvent",
    "ThinkingDeltaEvent",
    "ToolStartEvent",
    "ToolCompleteEvent",
    "TokenUpdateEvent",
    "get_event_broker",
    "set_event_broker",
    # Permissions
    "PermissionManager",
    "PermissionRequest",
    "RiskLevel",
    "PermissionRule",
    # Feedback
    "FeedbackLoop",
    "FeedbackConfig",
    "LintResult",
    "TestResult",
    # Profiles
    "ProfileManager",
    "ProfileConfig",
    "create_preset_profiles",
    # Custom Commands
    "CustomCommandManager",
    "CustomCommandExecutor",
    "CustomCommand",
    # MCP
    "get_mcp_module",
    # LSP
    "get_lsp_module",
    # Search
    "get_search_module",
]
