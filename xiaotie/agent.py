"""
小铁 Agent 核心

实现 Agent 执行循环：
1. 接收用户输入
2. 调用 LLM 生成响应
3. 执行工具调用
4. 循环直到任务完成
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional, List, Dict

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from .schema import Message, LLMResponse
from .llm import LLMClient
from .tools import Tool


class Agent:
    """小铁 Agent"""

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[Tool],
        max_steps: int = 50,
        token_limit: int = 100000,
        workspace_dir: str = ".",
    ):
        self.llm = llm_client
        self.tools: dict[str, Tool] = {t.name: t for t in tools}
        self.max_steps = max_steps
        self.token_limit = token_limit
        self.workspace_dir = workspace_dir

        # 消息历史
        self.messages: list[Message] = [
            Message(role="system", content=system_prompt)
        ]

        # 取消事件
        self.cancel_event: Optional[asyncio.Event] = None

        # Token 统计
        self.api_total_tokens = 0

        # tiktoken 编码器
        self._encoding = None
        if HAS_TIKTOKEN:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

    def _check_cancelled(self) -> bool:
        """检查是否被取消"""
        if self.cancel_event is not None and self.cancel_event.is_set():
            return True
        return False

    def _cleanup_incomplete_messages(self):
        """清理未完成的消息（取消时调用）"""
        # 找到最后一个 assistant 消息
        last_assistant_idx = -1
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i].role == "assistant":
                last_assistant_idx = i
                break

        # 如果有未完成的 tool 调用，删除 assistant 及其后的消息
        if last_assistant_idx >= 0:
            assistant_msg = self.messages[last_assistant_idx]
            if assistant_msg.tool_calls:
                # 检查是否所有 tool 调用都有结果
                tool_call_ids = {tc.id for tc in assistant_msg.tool_calls}
                result_ids = set()
                for msg in self.messages[last_assistant_idx + 1:]:
                    if msg.role == "tool" and msg.tool_call_id:
                        result_ids.add(msg.tool_call_id)

                if tool_call_ids != result_ids:
                    # 有未完成的调用，删除
                    self.messages = self.messages[:last_assistant_idx]

    def _estimate_tokens(self) -> int:
        """估算当前消息的 token 数"""
        if self._encoding is None:
            # 没有 tiktoken，按字符估算
            total_chars = sum(
                len(str(msg.content)) + len(str(msg.thinking or ""))
                for msg in self.messages
            )
            return total_chars // 4

        total = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total += len(self._encoding.encode(msg.content))
            if msg.thinking:
                total += len(self._encoding.encode(msg.thinking))
        return total

    async def _summarize_messages(self):
        """当 token 超限时摘要历史消息"""
        estimated = self._estimate_tokens()
        if estimated <= self.token_limit and self.api_total_tokens <= self.token_limit:
            return

        print(f"⚠️ Token 超限 ({estimated}/{self.token_limit})，正在摘要...")

        # 保留 system 消息
        system_msg = self.messages[0] if self.messages[0].role == "system" else None
        new_messages = [system_msg] if system_msg else []

        # 收集需要摘要的内容
        content_to_summarize = []
        for msg in self.messages[1:]:
            if msg.role == "user":
                # 保留用户消息
                new_messages.append(msg)
            else:
                # 收集 assistant 和 tool 消息
                if msg.content:
                    content_to_summarize.append(f"[{msg.role}]: {msg.content[:500]}")

        if content_to_summarize:
            # 生成摘要
            summary_prompt = f"请用中文简洁摘要以下对话内容（保留关键信息）:\n\n" + "\n".join(content_to_summarize[-20:])
            summary_response = await self.llm.generate([
                Message(role="user", content=summary_prompt)
            ])
            summary = summary_response.content

            # 添加摘要消息
            new_messages.append(Message(
                role="assistant",
                content=f"[历史摘要]\n{summary}"
            ))

        self.messages = new_messages
        print(f"✅ 摘要完成，消息数: {len(self.messages)}")

    async def run(self, user_input: str | None = None) -> str:
        """运行 Agent"""
        # 添加用户输入
        if user_input:
            self.messages.append(Message(role="user", content=user_input))

        for step in range(self.max_steps):
            # 检查取消
            if self._check_cancelled():
                self._cleanup_incomplete_messages()
                return "⚠️ 任务已取消"

            # Token 管理
            await self._summarize_messages()

            # 获取工具 schema
            tool_schemas = [tool.to_schema() for tool in self.tools.values()]

            # 调用 LLM
            try:
                response = await self.llm.generate(
                    messages=self.messages,
                    tools=tool_schemas if tool_schemas else None,
                )
            except Exception as e:
                return f"❌ LLM 调用失败: {e}"

            # 更新 token 统计
            if response.usage:
                self.api_total_tokens = response.usage.total_tokens

            # 显示思考过程
            if response.thinking:
                print(f"\n💭 思考:\n{response.thinking[:500]}...")

            # 显示回复
            if response.content:
                print(f"\n🤖 小铁:\n{response.content}")

            # 添加 assistant 消息
            self.messages.append(Message(
                role="assistant",
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
            ))

            # 如果没有工具调用，任务完成
            if not response.tool_calls:
                return response.content

            # 执行工具调用
            for tool_call in response.tool_calls:
                if self._check_cancelled():
                    self._cleanup_incomplete_messages()
                    return "⚠️ 任务已取消"

                tool_call_id = tool_call.id
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments

                print(f"\n🔧 调用工具: {function_name}")
                print(f"   参数: {arguments}")

                # 查找工具
                tool = self.tools.get(function_name)
                if not tool:
                    result_content = f"错误: 未知工具 '{function_name}'"
                    print(f"   ❌ {result_content}")
                else:
                    try:
                        result = await tool.execute(**arguments)
                        if result.success:
                            result_content = result.content
                            print(f"   ✅ 成功")
                        else:
                            result_content = f"错误: {result.error}"
                            print(f"   ❌ {result.error}")
                    except Exception as e:
                        result_content = f"执行异常: {e}"
                        print(f"   ❌ {result_content}")

                # 添加工具结果
                self.messages.append(Message(
                    role="tool",
                    content=result_content,
                    tool_call_id=tool_call_id,
                    name=function_name,
                ))

        return "⚠️ 达到最大步数限制"

    def reset(self):
        """重置 Agent 状态"""
        system_msg = self.messages[0] if self.messages and self.messages[0].role == "system" else None
        self.messages = [system_msg] if system_msg else []
        self.api_total_tokens = 0
