"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，参考 OpenCode 设计优化。
支持多 LLM Provider、工具调用、事件驱动架构、MCP 协议。
"""

__version__ = "0.5.1"
__author__ = "Leo"

from .agent import Agent, AgentConfig, SessionState
from .schema import Message, ToolCall, LLMResponse, ToolResult
from .events import (
    EventBroker, EventType, Event,
    AgentStartEvent, AgentStepEvent,
    MessageDeltaEvent, ThinkingDeltaEvent,
    ToolStartEvent, ToolCompleteEvent, TokenUpdateEvent,
    get_event_broker, set_event_broker,
)
from .permissions import (
    PermissionManager, PermissionRequest,
    RiskLevel, PermissionRule,
)
from .feedback import (
    FeedbackLoop, FeedbackConfig,
    LintResult, TestResult,
)
from .profiles import (
    ProfileManager, ProfileConfig,
    create_preset_profiles,
)
from .custom_commands import (
    CustomCommandManager, CustomCommandExecutor,
    CustomCommand,
)

# MCP 支持 (延迟导入以避免循环依赖)
def get_mcp_module():
    """获取 MCP 模块"""
    from . import mcp
    return mcp

__all__ = [
    # Agent
    "Agent",
    "AgentConfig",
    "SessionState",
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
]
