"""Agent 工具

允许主 Agent 生成子 Agent 来执行探索性任务。
学习自 OpenCode 的 agent-tool 设计。
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from ..tools.base import Tool
from ..schema import ToolResult

if TYPE_CHECKING:
    from .coordinator import AgentCoordinator


class AgentTool(Tool):
    """Agent 工具

    允许生成子 Agent 来执行探索性任务。

    特点：
    - 子 Agent 只有只读工具集
    - 适合搜索、探索、分析任务
    - 可以并行启动多个子 Agent
    - 每次调用是无状态的
    """

    def __init__(self, coordinator: Optional["AgentCoordinator"] = None):
        self._coordinator = coordinator

    def set_coordinator(self, coordinator: "AgentCoordinator") -> None:
        """设置协调器"""
        self._coordinator = coordinator

    @property
    def name(self) -> str:
        return "agent"

    @property
    def description(self) -> str:
        return """启动一个新的 Agent 来执行探索性任务。

子 Agent 可以访问以下工具：
- read_file: 读取文件
- glob: 搜索文件
- grep: 搜索代码内容
- list_dir: 列出目录

使用场景：
- 关键词搜索（可能需要多次尝试）
- 代码探索和分析
- 查找特定模式或实现

注意事项：
- 子 Agent 不能修改文件
- 每次调用是无状态的
- 可以并行启动多个 Agent 以提高效率
- 提供详细的任务描述以获得最佳结果"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "任务描述。应该详细说明要搜索或分析的内容。",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, prompt: str) -> ToolResult:
        """执行 Agent 任务

        Args:
            prompt: 任务描述

        Returns:
            ToolResult: 执行结果
        """
        if self._coordinator is None:
            return ToolResult(
                success=False,
                error="Agent 协调器未初始化",
            )

        try:
            from .roles import AgentRole

            result = await self._coordinator.spawn_agent(
                prompt=prompt,
                role=AgentRole.TASK,
            )

            if result.success:
                return ToolResult(
                    success=True,
                    content=result.content,
                )
            else:
                return ToolResult(
                    success=False,
                    content=result.content,
                    error=result.error,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Agent 执行失败: {e}",
            )
