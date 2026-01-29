"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，参考 OpenCode 设计优化。
支持多 LLM Provider、工具调用、事件驱动架构。
"""

__version__ = "0.4.2"
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
]
