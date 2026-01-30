"""多 Agent 协作模块

学习自 OpenCode 的 agent-tool 设计：
- 支持子 Agent 生成
- 任务分解与委派
- 结果聚合与合并
- 成本追踪
"""

from .coordinator import AgentCoordinator, TaskResult
from .roles import AgentRole, RoleConfig, create_default_roles
from .task_agent import TaskAgent, TaskAgentConfig
from .agent_tool import AgentTool

__all__ = [
    "AgentCoordinator",
    "TaskResult",
    "AgentRole",
    "RoleConfig",
    "create_default_roles",
    "TaskAgent",
    "TaskAgentConfig",
    "AgentTool",
]
