"""多 Agent 协作模块

学习自 OpenCode 的 agent-tool 设计：
- 支持子 Agent 生成
- 任务分解与委派
- 结果聚合与合并
- 成本追踪
"""

from .agent_tool import AgentTool
from .coordinator import (
    AgentRole as CoordinatorAgentRole,
)
from .coordinator import (
    BaseAgent,
    CoordinatorAgent,
    ExecutorAgent,
    ExpertAgent,
    MultiAgentSystem,
    SupervisorAgent,
    Task,
)
from .roles import AgentRole, RoleConfig, create_default_roles
from .task_agent import TaskAgent, TaskAgentConfig

__all__ = [
    "MultiAgentSystem",
    "BaseAgent",
    "CoordinatorAgent",
    "ExpertAgent",
    "ExecutorAgent",
    "SupervisorAgent",
    "AgentRole",
    "CoordinatorAgentRole",
    "Task",
    "RoleConfig",
    "create_default_roles",
    "TaskAgent",
    "TaskAgentConfig",
    "AgentTool",
]
