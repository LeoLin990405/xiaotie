"""
小铁 Agent 核心

参考 OpenCode 设计优化：
1. 事件驱动架构 - 实时 UI 更新
2. 上下文感知取消 - 优雅中断
3. 会话状态管理 - 防止并发冲突
4. 智能历史管理 - 自动摘要
5. 工具执行优化 - 顺序/并行模式
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional

try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from .events import (
    AgentStartEvent,
    AgentStepEvent,
    Event,
    EventType,
    MessageDeltaEvent,
    ThinkingDeltaEvent,
    TokenUpdateEvent,
    ToolCompleteEvent,
    ToolStartEvent,
    get_event_broker,
)
from .llm import LLMClient
from .schema import LLMResponse, Message
from .tools import Tool


@dataclass
class AgentConfig:
    """Agent 配置"""

    max_steps: int = 50
    token_limit: int = 100000
    parallel_tools: bool = True
    enable_thinking: bool = True
    stream: bool = True
    quiet: bool = False
    # 摘要配置
    summary_threshold: float = 0.8  # 达到 token_limit 的 80% 时触发摘要
    summary_keep_recent: int = 5  # 摘要时保留最近 N 条用户消息


class SessionState:
    """会话状态管理 - 防止并发冲突"""

    def __init__(self):
        self._busy_sessions: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, session_id: str) -> bool:
        """获取会话锁"""
        async with self._lock:
            if session_id in self._busy_sessions:
                return False
            self._busy_sessions[session_id] = asyncio.Event()
            return True

    async def release(self, session_id: str):
        """释放会话锁"""
        async with self._lock:
            if session_id in self._busy_sessions:
                self._busy_sessions[session_id].set()
                del self._busy_sessions[session_id]

    def is_busy(self, session_id: str) -> bool:
        """检查会话是否忙碌"""
        return session_id in self._busy_sessions

    async def wait_for_release(self, session_id: str, timeout: float = 30.0) -> bool:
        """等待会话释放"""
        if session_id not in self._busy_sessions:
            return True
        try:
            await asyncio.wait_for(self._busy_sessions[session_id].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


# 全局会话状态
_session_state = SessionState()


class Agent:
    """小铁 Agent - 优化版"""

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[Tool],
        max_steps: int = 50,
        token_limit: int = 100000,
        workspace_dir: str = ".",
        stream: bool = True,
        enable_thinking: bool = True,
        quiet: bool = False,
        parallel_tools: bool = True,
        session_id: Optional[str] = None,
    ):
        self.llm = llm_client
        self.tools: dict[str, Tool] = {t.name: t for t in tools}
        self.workspace_dir = workspace_dir
        self.session_id = session_id or str(uuid.uuid4())[:8]

        # 配置
        self.config = AgentConfig(
            max_steps=max_steps,
            token_limit=token_limit,
            parallel_tools=parallel_tools,
            enable_thinking=enable_thinking,
            stream=stream,
            quiet=quiet,
        )

        # 兼容旧属性
        self.max_steps = max_steps
        self.token_limit = token_limit
        self.stream = stream
        self.enable_thinking = enable_thinking
        self.quiet = quiet
        self.parallel_tools = parallel_tools

        # 消息历史
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]

        # 取消控制
        self.cancel_event: Optional[asyncio.Event] = None
        self._cancelled = False

        # Token 统计
        self.api_total_tokens = 0
        self.api_input_tokens = 0
        self.api_output_tokens = 0

        # tiktoken 编码器
        self._encoding = None
        if HAS_TIKTOKEN:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

        # 事件代理
        self._event_broker = get_event_broker()

        # 输出回调（兼容旧接口）
        self.on_thinking: Optional[Callable[[str], None]] = None
        self.on_content: Optional[Callable[[str], None]] = None

    def _check_cancelled(self) -> bool:
        """检查是否被取消"""
        if self._cancelled:
            return True
        if self.cancel_event is not None and self.cancel_event.is_set():
            self._cancelled = True
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
                for msg in self.messages[last_assistant_idx + 1 :]:
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
                len(str(msg.content)) + len(str(msg.thinking or "")) for msg in self.messages
            )
            return total_chars // 4

        total = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total += len(self._encoding.encode(msg.content))
            if msg.thinking:
                total += len(self._encoding.encode(msg.thinking))
        return total

    async def _should_summarize(self) -> bool:
        """检查是否需要摘要"""
        estimated = self._estimate_tokens()
        threshold = int(self.config.token_limit * self.config.summary_threshold)
        return estimated > threshold or self.api_total_tokens > threshold

    async def _summarize_messages(self):
        """智能摘要历史消息"""
        if not await self._should_summarize():
            return

        estimated = self._estimate_tokens()
        if not self.quiet:
            print(f"⚠️ Token 接近限制 ({estimated}/{self.config.token_limit})，正在摘要...")

        # 保留 system 消息
        system_msg = self.messages[0] if self.messages[0].role == "system" else None
        new_messages = [system_msg] if system_msg else []

        # 分离用户消息和其他消息
        user_messages = []
        other_messages = []

        for msg in self.messages[1:]:
            if msg.role == "user":
                user_messages.append(msg)
            else:
                other_messages.append(msg)

        # 保留最近的用户消息
        keep_recent = self.config.summary_keep_recent
        recent_user_msgs = (
            user_messages[-keep_recent:] if len(user_messages) > keep_recent else user_messages
        )
        old_user_msgs = user_messages[:-keep_recent] if len(user_messages) > keep_recent else []

        # 收集需要摘要的内容
        content_to_summarize = []
        for msg in old_user_msgs:
            content_to_summarize.append(f"[用户]: {msg.content[:200]}")
        for msg in other_messages[:-10]:  # 保留最近 10 条其他消息
            if msg.content:
                content_to_summarize.append(f"[{msg.role}]: {str(msg.content)[:200]}")

        if content_to_summarize:
            # 生成摘要
            summary_prompt = "请用中文简洁摘要以下对话内容（保留关键信息和决策）:\n\n" + "\n".join(
                content_to_summarize[-30:]
            )
            try:
                summary_response = await self.llm.generate(
                    [Message(role="user", content=summary_prompt)]
                )
                summary = summary_response.content

                # 添加摘要消息
                new_messages.append(Message(role="assistant", content=f"[历史摘要]\n{summary}"))
            except Exception as e:
                if not self.quiet:
                    print(f"⚠️ 摘要生成失败: {e}")

        # 添加保留的用户消息
        new_messages.extend(recent_user_msgs)

        # 添加最近的其他消息
        new_messages.extend(other_messages[-10:])

        self.messages = new_messages
        if not self.quiet:
            print(f"✅ 摘要完成，消息数: {len(self.messages)}")

    async def _publish_event(self, event: Event):
        """发布事件"""
        event.session_id = self.session_id
        await self._event_broker.publish(event)

    async def run(self, user_input: Optional[str] = None) -> str:
        """运行 Agent - 主循环"""
        # 检查会话是否忙碌
        if _session_state.is_busy(self.session_id):
            return "⚠️ 会话正在处理中，请稍候"

        # 获取会话锁
        if not await _session_state.acquire(self.session_id):
            return "⚠️ 无法获取会话锁"

        self._cancelled = False

        try:
            # 添加用户输入
            if user_input:
                self.messages.append(Message(role="user", content=user_input))
                await self._publish_event(
                    AgentStartEvent(
                        user_input=user_input, data={"message_count": len(self.messages)}
                    )
                )

            return await self._run_loop()

        finally:
            # 释放会话锁
            await _session_state.release(self.session_id)

    async def _run_loop(self) -> str:
        """Agent 执行循环"""
        for step in range(self.config.max_steps):
            # 检查取消
            if self._check_cancelled():
                self._cleanup_incomplete_messages()
                await self._publish_event(Event(type=EventType.AGENT_CANCEL))
                return "⚠️ 任务已取消"

            # 发布步骤事件
            await self._publish_event(
                AgentStepEvent(
                    step=step + 1,
                    total_steps=self.config.max_steps,
                )
            )

            # Token 管理
            await self._summarize_messages()

            # 获取工具 schema
            tool_schemas = [tool.to_schema() for tool in self.tools.values()]

            # 调用 LLM
            try:
                if self.config.stream:
                    response = await self._stream_generate(tool_schemas)
                else:
                    response = await self.llm.generate(
                        messages=self.messages,
                        tools=tool_schemas if tool_schemas else None,
                    )
            except Exception as e:
                await self._publish_event(Event(type=EventType.AGENT_ERROR, data={"error": str(e)}))
                return f"❌ LLM 调用失败: {e}"

            # 更新 token 统计
            if response.usage:
                self.api_total_tokens = response.usage.total_tokens
                self.api_input_tokens = response.usage.input_tokens
                self.api_output_tokens = response.usage.output_tokens
                await self._publish_event(
                    TokenUpdateEvent(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        total_tokens=response.usage.total_tokens,
                    )
                )

            # 添加 assistant 消息
            self.messages.append(
                Message(
                    role="assistant",
                    content=response.content,
                    thinking=response.thinking,
                    tool_calls=response.tool_calls,
                )
            )

            # 如果没有工具调用，任务完成
            if not response.tool_calls:
                await self._publish_event(
                    Event(type=EventType.AGENT_COMPLETE, data={"content": response.content})
                )
                return response.content

            # 执行工具调用
            if self.config.parallel_tools and len(response.tool_calls) > 1:
                tool_results = await self._execute_tools_parallel(response.tool_calls)
            else:
                tool_results = await self._execute_tools_sequential(response.tool_calls)

            # 检查取消（工具执行后）
            if self._check_cancelled():
                self._cleanup_incomplete_messages()
                return "⚠️ 任务已取消"

            # 添加工具结果到消息历史
            for tool_call_id, function_name, result_content in tool_results:
                self.messages.append(
                    Message(
                        role="tool",
                        content=result_content,
                        tool_call_id=tool_call_id,
                        name=function_name,
                    )
                )

        return "⚠️ 达到最大步数限制"

    async def _execute_tools_sequential(self, tool_calls: list) -> list[tuple[str, str, str]]:
        """顺序执行工具调用（参考 OpenCode 设计）"""
        results = []

        for tool_call in tool_calls:
            # 检查取消
            if self._check_cancelled():
                # 标记剩余工具为已取消
                results.append((tool_call.id, tool_call.function.name, "⚠️ 已取消"))
                continue

            result = await self._execute_single_tool(tool_call)
            results.append(result)

        return results

    async def _execute_tools_parallel(self, tool_calls: list) -> list[tuple[str, str, str]]:
        """并行执行多个工具调用"""
        if self._check_cancelled():
            return []

        if not self.quiet:
            print(f"\n⚡ 并行执行 {len(tool_calls)} 个工具...")

        start_time = time.time()
        tasks = [self._execute_single_tool(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start_time

        if not self.quiet:
            print(f"   ⏱️ 完成，总耗时 {elapsed:.2f}s")

        # 处理结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tc = tool_calls[i]
                final_results.append((tc.id, tc.function.name, f"执行异常: {result}"))
            else:
                final_results.append(result)

        return final_results

    async def _execute_single_tool(self, tool_call) -> tuple[str, str, str]:
        """执行单个工具"""
        tool_call_id = tool_call.id
        function_name = tool_call.function.name
        arguments = tool_call.function.arguments

        # 发布工具开始事件
        await self._publish_event(
            ToolStartEvent(
                tool_name=function_name,
                tool_id=tool_call_id,
                arguments=arguments,
            )
        )

        # 格式化参数显示
        if not self.quiet:
            args_display = ", ".join(f"{k}={repr(v)[:50]}" for k, v in arguments.items())
            print(f"\n🔧 {function_name}({args_display})")

        tool = self.tools.get(function_name)
        if not tool:
            result_content = f"错误: 未知工具 '{function_name}'"
            if not self.quiet:
                print(f"   ❌ {result_content}")
            await self._publish_event(
                ToolCompleteEvent(
                    tool_name=function_name,
                    tool_id=tool_call_id,
                    success=False,
                    error=result_content,
                )
            )
            return (tool_call_id, function_name, result_content)

        try:
            start_time = time.time()
            result = await tool.execute(**arguments)
            elapsed = time.time() - start_time

            if result.success:
                result_content = result.content
                # 显示结果预览
                if not self.quiet:
                    preview = result_content[:100].replace("\n", " ")
                    if len(result_content) > 100:
                        preview += "..."
                    print(f"   ✅ ({elapsed:.1f}s) {preview}")

                await self._publish_event(
                    ToolCompleteEvent(
                        tool_name=function_name,
                        tool_id=tool_call_id,
                        success=True,
                        result=result_content[:500],
                        duration=elapsed,
                    )
                )
            else:
                result_content = f"错误: {result.error}"
                if not self.quiet:
                    print(f"   ❌ ({elapsed:.1f}s) {result.error}")

                await self._publish_event(
                    ToolCompleteEvent(
                        tool_name=function_name,
                        tool_id=tool_call_id,
                        success=False,
                        error=result.error,
                        duration=elapsed,
                    )
                )

        except Exception as e:
            result_content = f"执行异常: {e}"
            if not self.quiet:
                print(f"   ❌ {result_content}")

            await self._publish_event(
                ToolCompleteEvent(
                    tool_name=function_name,
                    tool_id=tool_call_id,
                    success=False,
                    error=str(e),
                )
            )

        return (tool_call_id, function_name, result_content)

    async def _stream_generate(self, tool_schemas: list) -> LLMResponse:
        """流式生成响应"""
        thinking_started = False
        content_started = False

        async def on_thinking(text: str):
            nonlocal thinking_started
            if self.quiet:
                return
            if not thinking_started:
                if not self.on_thinking:
                    # 只有在没有外部回调时才打印标题
                    print("\n💭 思考中...", flush=True)
                thinking_started = True
                await self._publish_event(Event(type=EventType.THINKING_START))

            # 发布思考增量事件
            await self._publish_event(ThinkingDeltaEvent(content=text))

            # 调用回调
            if self.on_thinking:
                self.on_thinking(text)

        async def on_content(text: str):
            nonlocal content_started
            if self.quiet:
                return
            if not content_started:
                if not self.on_content:
                    # 只有在没有外部回调时才打印标题
                    print("\n🤖 小铁:", flush=True)
                content_started = True
                await self._publish_event(Event(type=EventType.MESSAGE_START))

            # 只有在没有外部回调时才直接打印
            if not self.on_content:
                print(text, end="", flush=True)

            # 发布消息增量事件
            await self._publish_event(MessageDeltaEvent(content=text))

            # 调用回调
            if self.on_content:
                self.on_content(text)

        # 包装同步回调为异步
        def sync_on_thinking(text: str):
            asyncio.create_task(on_thinking(text))

        def sync_on_content(text: str):
            asyncio.create_task(on_content(text))

        response = await self.llm.generate_stream(
            messages=self.messages,
            tools=tool_schemas if tool_schemas else None,
            on_thinking=sync_on_thinking,
            on_content=sync_on_content,
            enable_thinking=self.config.enable_thinking,
        )

        if content_started and not self.quiet:
            print()  # 换行

        if thinking_started:
            await self._publish_event(Event(type=EventType.THINKING_COMPLETE))
        if content_started:
            await self._publish_event(Event(type=EventType.MESSAGE_COMPLETE))

        return response

    def reset(self):
        """重置 Agent 状态"""
        system_msg = (
            self.messages[0] if self.messages and self.messages[0].role == "system" else None
        )
        self.messages = [system_msg] if system_msg else []
        self.api_total_tokens = 0
        self.api_input_tokens = 0
        self.api_output_tokens = 0
        self._cancelled = False

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "estimated_tokens": self._estimate_tokens(),
            "api_total_tokens": self.api_total_tokens,
            "api_input_tokens": self.api_input_tokens,
            "api_output_tokens": self.api_output_tokens,
            "tool_count": len(self.tools),
            "parallel_tools": self.config.parallel_tools,
            "enable_thinking": self.config.enable_thinking,
        }
