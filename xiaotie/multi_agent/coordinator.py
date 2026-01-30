"""Agent 协调器

管理多个 Agent 的协作，包括：
- 任务分解
- Agent 生成
- 结果聚合
- 成本追踪
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import uuid4

from .roles import AgentRole, RoleConfig, create_default_roles
from .task_agent import TaskAgent, TaskAgentConfig


@dataclass
class TaskResult:
    """任务执行结果"""

    task_id: str
    success: bool
    content: str
    error: Optional[str] = None
    agent_id: Optional[str] = None
    iterations: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AgentTask:
    """Agent 任务"""

    id: str
    prompt: str
    role: AgentRole = AgentRole.TASK
    parent_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed, cancelled
    result: Optional[TaskResult] = None


class AgentCoordinator:
    """Agent 协调器

    负责管理多个 Agent 的协作：
    - 创建和管理子 Agent
    - 任务分配和调度
    - 结果收集和聚合
    - 成本追踪
    """

    def __init__(
        self,
        llm_client: Any,
        tools: list[Any],
        roles: Optional[dict[AgentRole, RoleConfig]] = None,
        max_concurrent_agents: int = 5,
    ):
        self.llm_client = llm_client
        self.tools = tools
        self.roles = roles or create_default_roles()
        self.max_concurrent_agents = max_concurrent_agents

        # 任务队列
        self._tasks: dict[str, AgentTask] = {}

        # 活跃的 Agent
        self._active_agents: dict[str, TaskAgent] = {}

        # 总成本追踪
        self._total_tokens = {"prompt": 0, "completion": 0}

        # 事件回调
        self._on_task_start: Optional[Callable[[AgentTask], None]] = None
        self._on_task_complete: Optional[Callable[[AgentTask], None]] = None

    def set_callbacks(
        self,
        on_task_start: Optional[Callable[[AgentTask], None]] = None,
        on_task_complete: Optional[Callable[[AgentTask], None]] = None,
    ) -> None:
        """设置事件回调"""
        self._on_task_start = on_task_start
        self._on_task_complete = on_task_complete

    async def spawn_agent(
        self,
        prompt: str,
        role: AgentRole = AgentRole.TASK,
        parent_id: Optional[str] = None,
    ) -> TaskResult:
        """生成并执行一个子 Agent

        Args:
            prompt: 任务提示词
            role: Agent 角色
            parent_id: 父 Agent ID

        Returns:
            TaskResult: 执行结果
        """
        task_id = str(uuid4())
        task = AgentTask(
            id=task_id,
            prompt=prompt,
            role=role,
            parent_id=parent_id,
        )
        self._tasks[task_id] = task

        # 获取角色配置
        role_config = self.roles.get(role, self.roles[AgentRole.TASK])

        # 创建任务 Agent 配置
        agent_config = TaskAgentConfig(
            parent_id=parent_id or "root",
            prompt=prompt,
            allowed_tools=role_config.allowed_tools or [],
            max_iterations=role_config.max_iterations,
        )

        # 创建任务 Agent
        agent = TaskAgent(
            config=agent_config,
            llm_client=self.llm_client,
            tools=self.tools,
        )
        self._active_agents[agent.id] = agent

        # 触发开始回调
        task.status = "running"
        if self._on_task_start:
            self._on_task_start(task)

        try:
            # 执行任务
            result = await agent.run()

            # 更新成本追踪
            self._total_tokens["prompt"] += result.token_usage.get("prompt", 0)
            self._total_tokens["completion"] += result.token_usage.get("completion", 0)

            # 创建任务结果
            task_result = TaskResult(
                task_id=task_id,
                success=result.success,
                content=result.content,
                error=result.error,
                agent_id=agent.id,
                iterations=result.iterations,
                token_usage=result.token_usage,
            )

            task.status = "completed" if result.success else "failed"
            task.result = task_result

        except Exception as e:
            task_result = TaskResult(
                task_id=task_id,
                success=False,
                content="",
                error=str(e),
                agent_id=agent.id,
            )
            task.status = "failed"
            task.result = task_result

        finally:
            # 清理
            del self._active_agents[agent.id]

            # 触发完成回调
            if self._on_task_complete:
                self._on_task_complete(task)

        return task_result

    async def spawn_agents_parallel(
        self,
        tasks: list[tuple[str, AgentRole]],
        parent_id: Optional[str] = None,
    ) -> list[TaskResult]:
        """并行生成多个子 Agent

        Args:
            tasks: 任务列表，每个元素是 (prompt, role) 元组
            parent_id: 父 Agent ID

        Returns:
            list[TaskResult]: 执行结果列表
        """
        # 限制并发数量
        semaphore = asyncio.Semaphore(self.max_concurrent_agents)

        async def run_with_semaphore(prompt: str, role: AgentRole) -> TaskResult:
            async with semaphore:
                return await self.spawn_agent(prompt, role, parent_id)

        # 并行执行
        coroutines = [run_with_semaphore(prompt, role) for prompt, role in tasks]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # 处理异常
        task_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_results.append(
                    TaskResult(
                        task_id=str(uuid4()),
                        success=False,
                        content="",
                        error=str(result),
                    )
                )
            else:
                task_results.append(result)

        return task_results

    def cancel_all(self) -> None:
        """取消所有活跃的 Agent"""
        for agent in self._active_agents.values():
            agent.cancel()

    def get_total_tokens(self) -> dict[str, int]:
        """获取总 token 使用量"""
        return self._total_tokens.copy()

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[AgentTask]:
        """列出所有任务"""
        return list(self._tasks.values())

    def list_active_agents(self) -> list[str]:
        """列出活跃的 Agent ID"""
        return list(self._active_agents.keys())
