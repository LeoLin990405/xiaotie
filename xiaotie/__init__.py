"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，参考 OpenCode 设计优化。
支持多 LLM Provider、工具调用、事件驱动架构、MCP 协议。
"""

__version__ = "1.1.0"
__author__ = "Leo"

from .agent import Agent, AgentConfig, SessionState
from .builder import AgentBuilder, AgentHooks, AgentSpec, create_agent
from .cache import AsyncLRUCache, get_global_cache, cache_result
from .custom_commands import (
    CustomCommand,
    CustomCommandExecutor,
    CustomCommandManager,
)
from .enhancements import (
    get_system_info,
    manage_process,
    network_operation,
    get_cache_stats,
    clear_cache,
    get_cached_system_info
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
from .logging import LoggerManager, get_logger, debug, info, warning, error, critical
from .memory.core import MemoryManager, ConversationMemory, MemoryChunk, MemoryType
from .multi_agent.coordinator import (
    MultiAgentSystem,
    BaseAgent,
    CoordinatorAgent,
    ExpertAgent,
    ExecutorAgent,
    SupervisorAgent,
    AgentRole,
    Task as MultiAgentTask
)
from .permissions import (
    PermissionManager,
    PermissionRequest,
    PermissionRule,
    RiskLevel,
)
from .planning.core import (
    PlanningSystem,
    TaskManager,
    PlanExecutor,
    Task as PlanningTask,
    TaskStatus,
    Priority,
    PlanStep
)
from .profiles import (
    ProfileConfig,
    ProfileManager,
    create_preset_profiles,
)
from .reflection.core import (
    ReflectionManager,
    ReflectiveAgentMixin,
    Reflection,
    ReflectionType
)
from .learning.core import (
    AdaptiveLearner,
    LearningAgentMixin,
    LearningStrategy,
    Skill
)
from .context.core import (
    ContextManager,
    ContextAwareAgentMixin,
    ContextType,
    ContextScope,
    ContextEntity,
    ContextFrame
)
from .context.window import (
    ContextWindowManager,
    ContextAwareWindowManager,
    CompressionMethod,
    WindowStrategy,
    ContextWindow
)
from .decision.core import (
    DecisionEngine,
    DecisionAwareAgentMixin,
    DecisionType,
    DecisionStrategy,
    DecisionOption,
    DecisionOutcome
)
from .skills.core import (
    SkillLearningAgentMixin,
    SkillAcquirer,
    SkillType,
    SkillAcquisitionMethod,
    SkillExample,
    SkillDevelopmentStage
)
from .multimodal.core import (
    MultimodalContentManager,
    MultimodalAgentMixin,
    ModalityType,
    MediaType,
    MediaContent,
    ImageAnalysisTool,
    DocumentAnalysisTool
)
from .rl.core import (
    ReinforcementLearningEngine,
    RLAgentMixin,
    RLAlgorithm,
    State,
    Action,
    Transition,
    StateRepresentation
)
from .kg.core import (
    KnowledgeGraphManager,
    KnowledgeGraphAgentMixin,
    KnowledgeGraphBuilder,
    KnowledgeGraphQueryEngine,
    NetworkXKnowledgeGraphStore,
    KGNode,
    KGEdge,
    NodeType,
    RelationType
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
    # Cache
    "AsyncLRUCache",
    "get_global_cache",
    "cache_result",
    # Logging
    "LoggerManager",
    "get_logger",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    # Enhancements
    "get_system_info",
    "manage_process",
    "network_operation",
    "get_cache_stats",
    "clear_cache",
    "get_cached_system_info",
    # Memory
    "MemoryManager",
    "ConversationMemory",
    "MemoryChunk",
    "MemoryType",
    # Multi-Agent
    "MultiAgentSystem",
    "BaseAgent",
    "CoordinatorAgent",
    "ExpertAgent",
    "ExecutorAgent",
    "SupervisorAgent",
    "AgentRole",
    "MultiAgentTask",
    # Planning
    "PlanningSystem",
    "TaskManager",
    "PlanExecutor",
    "PlanningTask",
    "TaskStatus",
    "Priority",
    "PlanStep",
    # Reflection
    "ReflectionManager",
    "ReflectiveAgentMixin",
    "Reflection",
    "ReflectionType",
    # Learning
    "AdaptiveLearner",
    "LearningAgentMixin",
    "LearningStrategy",
    "Skill",
    # Context
    "ContextManager",
    "ContextAwareAgentMixin",
    "ContextType",
    "ContextScope",
    "ContextEntity",
    "ContextFrame",
    # Context Window
    "ContextWindowManager",
    "ContextAwareWindowManager",
    "CompressionMethod",
    "WindowStrategy",
    "ContextWindow",
    # Decision
    "DecisionEngine",
    "DecisionAwareAgentMixin",
    "DecisionType",
    "DecisionStrategy",
    "DecisionOption",
    "DecisionOutcome",
    # Skills
    "SkillLearningAgentMixin",
    "SkillAcquirer",
    "SkillType",
    "SkillAcquisitionMethod",
    "SkillExample",
    "SkillDevelopmentStage",
    # Multimodal
    "MultimodalContentManager",
    "MultimodalAgentMixin",
    "ModalityType",
    "MediaType",
    "MediaContent",
    "ImageAnalysisTool",
    "DocumentAnalysisTool",
    # Reinforcement Learning
    "ReinforcementLearningEngine",
    "RLAgentMixin",
    "RLAlgorithm",
    "State",
    "Action",
    "Transition",
    "StateRepresentation",
    # Knowledge Graph
    "KnowledgeGraphManager",
    "KnowledgeGraphAgentMixin",
    "KnowledgeGraphBuilder",
    "KnowledgeGraphQueryEngine",
    "NetworkXKnowledgeGraphStore",
    "KGNode",
    "KGEdge",
    "NodeType",
    "RelationType",
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
