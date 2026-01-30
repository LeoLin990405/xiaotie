"""任务 Agent

轻量级 Agent，用于执行子任务。
学习自 OpenCode 的 agent-tool 设计。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from ..schema import Message, ToolResult

if TYPE_CHECKING:
    pass


@dataclass
class TaskAgentConfig:
    """任务 Agent 配置"""

    # 父 Agent ID
    parent_id: str

    # 任务提示词
    prompt: str

    # 允许的工具列表
    allowed_tools: list[str] = field(
        default_factory=lambda: [
            "read_file",
            "glob",
            "grep",
            "list_dir",
        ]
    )

    # 最大迭代次数
    max_iterations: int = 10

    # 超时时间 (秒)
    timeout: float = 300.0


@dataclass
class TaskAgentResult:
    """任务 Agent 执行结果"""

    success: bool
    content: str
    error: Optional[str] = None
    iterations: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)


class TaskAgent:
    """任务 Agent

    轻量级 Agent，用于执行探索性任务。
    特点：
    - 只读工具集
    - 无状态执行
    - 单次响应
    - 成本追踪
    """

    def __init__(
        self,
        config: TaskAgentConfig,
        llm_client: Any,
        tools: list[Any],
    ):
        self.id = str(uuid4())
        self.config = config
        self.llm_client = llm_client
        self.tools = self._filter_tools(tools)
        self._cancelled = False

    def _filter_tools(self, tools: list[Any]) -> list[Any]:
        """过滤工具，只保留允许的工具"""
        if not self.config.allowed_tools:
            return tools

        allowed = set(self.config.allowed_tools)
        return [t for t in tools if t.name in allowed]

    async def run(self) -> TaskAgentResult:
        """执行任务

        Returns:
            TaskAgentResult: 执行结果
        """
        if self._cancelled:
            return TaskAgentResult(
                success=False,
                content="",
                error="任务已取消",
            )

        try:
            result = await asyncio.wait_for(
                self._execute(),
                timeout=self.config.timeout,
            )
            return result
        except asyncio.TimeoutError:
            return TaskAgentResult(
                success=False,
                content="",
                error=f"任务超时 ({self.config.timeout}秒)",
            )
        except Exception as e:
            return TaskAgentResult(
                success=False,
                content="",
                error=f"执行失败: {e}",
            )

    async def _execute(self) -> TaskAgentResult:
        """内部执行逻辑"""
        messages = [
            Message(
                role="system",
                content=self._build_system_prompt(),
            ),
            Message(
                role="user",
                content=self.config.prompt,
            ),
        ]

        iterations = 0
        total_tokens = {"prompt": 0, "completion": 0}

        while iterations < self.config.max_iterations:
            if self._cancelled:
                return TaskAgentResult(
                    success=False,
                    content="",
                    error="任务已取消",
                    iterations=iterations,
                    token_usage=total_tokens,
                )

            iterations += 1

            # 调用 LLM
            response = await self.llm_client.chat(
                messages=messages,
                tools=self._get_tool_definitions(),
            )

            # 更新 token 统计
            if response.usage:
                total_tokens["prompt"] += response.usage.prompt_tokens
                total_tokens["completion"] += response.usage.completion_tokens

            # 检查是否有工具调用
            if response.tool_calls:
                # 执行工具
                tool_results = await self._execute_tools(response.tool_calls)

                # 添加助手消息
                messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                # 添加工具结果消息
                for tc, result in zip(response.tool_calls, tool_results):
                    messages.append(
                        Message(
                            role="tool",
                            content=result.content if result.success else f"错误: {result.error}",
                            tool_call_id=tc.id,
                        )
                    )
            else:
                # 没有工具调用，返回最终结果
                return TaskAgentResult(
                    success=True,
                    content=response.content,
                    iterations=iterations,
                    token_usage=total_tokens,
                )

        # 达到最大迭代次数
        return TaskAgentResult(
            success=True,
            content=messages[-1].content if messages else "",
            iterations=iterations,
            token_usage=total_tokens,
        )

    async def _execute_tools(self, tool_calls: list) -> list[ToolResult]:
        """执行工具调用"""
        results = []

        for tc in tool_calls:
            tool = self._find_tool(tc.function.name)
            if tool is None:
                results.append(
                    ToolResult(
                        success=False,
                        error=f"未知工具: {tc.function.name}",
                    )
                )
                continue

            try:
                result = await tool.execute(**tc.function.arguments)
                results.append(result)
            except Exception as e:
                results.append(
                    ToolResult(
                        success=False,
                        error=f"工具执行失败: {e}",
                    )
                )

        return results

    def _find_tool(self, name: str) -> Optional[Any]:
        """查找工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def _get_tool_definitions(self) -> list[dict]:
        """获取工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self.tools
        ]

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专注于代码探索和搜索的 AI 助手。

你的任务是根据用户的请求，使用提供的工具来搜索和分析代码。

重要规则：
1. 你只能读取和分析代码，不能修改任何文件
2. 使用 glob 工具查找文件
3. 使用 grep 工具搜索代码内容
4. 使用 read_file 工具读取文件内容
5. 完成任务后，提供清晰、简洁的总结

请高效地完成任务，避免不必要的工具调用。"""

    def cancel(self) -> None:
        """取消任务"""
        self._cancelled = True
