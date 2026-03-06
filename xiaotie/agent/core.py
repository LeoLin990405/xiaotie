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
import re
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Optional

try:
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from xiaotie.events import (
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
from xiaotie.llm import LLMClient
from xiaotie.permissions import PermissionManager
from xiaotie.schema import LLMResponse, Message
from xiaotie.telemetry import AgentTelemetry
from xiaotie.tools import Tool
from .config import AgentConfig
from .state import SessionState, _session_state

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
        """初始化 Agent。

        Args:
            llm_client: LLM 客户端实例，用于与大语言模型通信。
            system_prompt: 系统提示词，定义 Agent 的角色和行为。
            tools: 可用工具列表，每个工具需实现 Tool 接口。
            max_steps: 单次运行的最大步数，防止无限循环。默认 50。
            token_limit: Token 上限，超过阈值时触发自动摘要。默认 100000。
            workspace_dir: 工作目录路径，文件操作的根目录。默认当前目录。
            stream: 是否启用流式输出。默认 True。
            enable_thinking: 是否启用深度思考模式（GLM-4.7 等支持）。默认 True。
            quiet: 安静模式，仅输出最终结果。默认 False。
            parallel_tools: 是否并行执行多个工具调用。默认 True。
            session_id: 会话 ID，用于并发控制。默认自动生成。
        """
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
            cache_enabled=True,  # 默认启用缓存
            cache_ttl=3600,      # 默认1小时TTL
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

        # 增量 token 估算缓存
        self._cached_token_count = 0
        self._cached_message_count = 0

        # 事件代理
        self._event_broker = get_event_broker()
        self.telemetry = AgentTelemetry(session_id=self.session_id)
        self.permission_manager = PermissionManager(
            auto_approve_low_risk=True,
            auto_approve_medium_risk=True,
            interactive=not quiet,
            require_double_confirm_high_risk=True,
        )

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
        """估算当前消息的 token 数（增量计算，仅编码新增消息）"""
        current_count = len(self.messages)

        # 如果消息被截断（如摘要后），重置缓存
        if current_count < self._cached_message_count:
            self._cached_token_count = 0
            self._cached_message_count = 0

        if self._encoding is None:
            # 没有 tiktoken，按字符估算（增量）
            new_chars = sum(
                len(str(msg.content)) + len(str(msg.thinking or ""))
                for msg in self.messages[self._cached_message_count:]
            )
            self._cached_token_count += new_chars // 4
            self._cached_message_count = current_count
            return self._cached_token_count

        # 仅编码新增消息
        new_tokens = 0
        for msg in self.messages[self._cached_message_count:]:
            if isinstance(msg.content, str):
                new_tokens += len(self._encoding.encode(msg.content))
            if msg.thinking:
                new_tokens += len(self._encoding.encode(msg.thinking))

        self._cached_token_count += new_tokens
        self._cached_message_count = current_count
        return self._cached_token_count

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
        self.telemetry.record_run_start()

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
        provider = getattr(self.llm, "provider", "unknown")
        provider_name = getattr(provider, "value", str(provider))
        model_name = getattr(getattr(self.llm, "_client", None), "model", None) or getattr(
            self.llm, "model", "unknown"
        )
        for step in range(self.config.max_steps):
            # 检查取消
            if self._check_cancelled():
                self._cleanup_incomplete_messages()
                await self._publish_event(Event(type=EventType.AGENT_CANCEL))
                self.telemetry.record_run_end("cancelled")
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
            llm_start = time.perf_counter()
            try:
                if self.config.stream:
                    response = await self._stream_generate(tool_schemas)
                else:
                    response = await self.llm.generate(
                        messages=self.messages,
                        tools=tool_schemas if tool_schemas else None,
                    )
            except Exception as e:
                self.telemetry.record_llm_call(
                    provider=provider_name,
                    model=model_name,
                    latency_sec=time.perf_counter() - llm_start,
                    success=False,
                )
                await self._publish_event(Event(type=EventType.AGENT_ERROR, data={"error": str(e)}))
                self.telemetry.record_run_end("error")
                return f"❌ LLM 调用失败: {e}"
            self.telemetry.record_llm_call(
                provider=provider_name,
                model=model_name,
                latency_sec=time.perf_counter() - llm_start,
                success=True,
            )

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
                self.telemetry.record_run_end("success")
                return response.content

            # 执行工具调用
            if self.config.parallel_tools and len(response.tool_calls) > 1:
                tool_results = await self._execute_tools_parallel(response.tool_calls)
            else:
                tool_results = await self._execute_tools_sequential(response.tool_calls)

            # 检查取消（工具执行后）
            if self._check_cancelled():
                self._cleanup_incomplete_messages()
                self.telemetry.record_run_end("cancelled")
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

        self.telemetry.record_run_end("error")
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
        provider = getattr(self.llm, "provider", "unknown")
        provider_name = getattr(provider, "value", str(provider))
        model_name = getattr(getattr(self.llm, "_client", None), "model", None) or getattr(
            self.llm, "model", "unknown"
        )
        risk_level = self.permission_manager.get_risk_level(function_name, arguments).value
        tool_origin = self._resolve_tool_origin(function_name)

        # 发布工具开始事件
        await self._publish_event(
            ToolStartEvent(
                tool_name=function_name,
                tool_id=tool_call_id,
                arguments=arguments,
                data={
                    "audit": {
                        "caller": "agent",
                        "provider": provider_name,
                        "model": model_name,
                        "tool_origin": tool_origin,
                        "risk_level": risk_level,
                        "arguments_summary": self._summarize_arguments(arguments),
                    }
                },
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
            self.telemetry.record_tool_call(tool_name=function_name, latency_sec=0.0, success=False)
            return (tool_call_id, function_name, result_content)

        allowed, reason = await self.permission_manager.check_permission(function_name, arguments)
        if not allowed:
            result_content = f"权限拒绝: {reason}"
            await self._publish_event(
                ToolCompleteEvent(
                    tool_name=function_name,
                    tool_id=tool_call_id,
                    success=False,
                    error=result_content,
                    data={
                        "audit": {
                            "caller": "agent",
                            "provider": provider_name,
                            "model": model_name,
                            "tool_origin": tool_origin,
                            "risk_level": risk_level,
                            "decision": "denied",
                            "reason": reason,
                        }
                    },
                )
            )
            self.telemetry.record_tool_call(tool_name=function_name, latency_sec=0.0, success=False)
            return (tool_call_id, function_name, result_content)

        start_time = time.perf_counter()
        try:
            result = await tool.execute(**arguments)
            elapsed = time.perf_counter() - start_time

            if result.success:
                result_content = result.content
                result_content, blocked, block_reason = self._filter_sensitive_output(result_content)
                if blocked:
                    result_content = f"⚠️ 输出已拦截: {block_reason}"
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
                        success=not blocked,
                        result=result_content[:500],
                        error=block_reason if blocked else None,
                        duration=elapsed,
                        data={
                            "audit": {
                                "caller": "agent",
                                "provider": provider_name,
                                "model": model_name,
                                "tool_origin": tool_origin,
                                "risk_level": risk_level,
                                "decision": "allowed",
                                "sensitive_blocked": blocked,
                            }
                        },
                    )
                )
                self.telemetry.record_tool_call(
                    tool_name=function_name, latency_sec=elapsed, success=not blocked
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
                        data={
                            "audit": {
                                "caller": "agent",
                                "provider": provider_name,
                                "model": model_name,
                                "tool_origin": tool_origin,
                                "risk_level": risk_level,
                                "decision": "allowed",
                            }
                        },
                    )
                )
                self.telemetry.record_tool_call(
                    tool_name=function_name, latency_sec=elapsed, success=False
                )

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            result_content = f"执行异常: {e}"
            if not self.quiet:
                print(f"   ❌ {result_content}")

            await self._publish_event(
                ToolCompleteEvent(
                    tool_name=function_name,
                    tool_id=tool_call_id,
                    success=False,
                    error=str(e),
                    data={
                        "audit": {
                            "caller": "agent",
                            "provider": provider_name,
                            "model": model_name,
                            "tool_origin": tool_origin,
                            "risk_level": risk_level,
                            "decision": "allowed",
                        }
                    },
                )
            )
            self.telemetry.record_tool_call(tool_name=function_name, latency_sec=elapsed, success=False)

        return (tool_call_id, function_name, result_content)

    async def _stream_generate(self, tool_schemas: list) -> LLMResponse:
        """流式生成响应"""
        thinking_started = False
        content_started = False
        _event_buffer: list[Event] = []
        _FLUSH_SIZE = 10
        _flush_task: Optional[asyncio.Task] = None
        _flush_lock = asyncio.Lock()

        async def _flush_events():
            async with _flush_lock:
                if not _event_buffer:
                    return
                to_publish = list(_event_buffer)
                _event_buffer.clear()
                flush_start = time.perf_counter()
                for evt in to_publish:
                    evt.session_id = self.session_id
                await self._event_broker.publish_batch(to_publish)
                self.telemetry.record_stream_flush(
                    event_count=len(to_publish),
                    latency_sec=time.perf_counter() - flush_start,
                )
                self.telemetry.record_stream_queue_depth(len(_event_buffer))

        def _schedule_flush():
            nonlocal _flush_task
            if _flush_task is None or _flush_task.done():
                _flush_task = asyncio.create_task(_flush_events())

        def _buffer_event(event: Event):
            _event_buffer.append(event)
            self.telemetry.record_stream_queue_depth(len(_event_buffer))
            if len(_event_buffer) >= _FLUSH_SIZE:
                _schedule_flush()

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

            _buffer_event(ThinkingDeltaEvent(content=text))
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

            if not self.on_content:
                print(text, end="", flush=True)
            _buffer_event(MessageDeltaEvent(content=text))
            if self.on_content:
                self.on_content(text)

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

        if _flush_task is not None:
            await _flush_task
        await _flush_events()

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
        self._cached_token_count = 0
        self._cached_message_count = 0

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
            "telemetry": self.telemetry.snapshot(),
            "permission": self.permission_manager.get_stats(),
        }

    def _filter_sensitive_output(self, output: str) -> tuple[str, bool, str]:
        if not isinstance(output, str) or not output:
            return output, False, ""
        patterns = [
            (r"AKIA[0-9A-Z]{16}", "检测到疑似 AWS Access Key"),
            (r"(?i)api[_-]?key\s*[:=]\s*[^\s]+", "检测到疑似 API Key"),
            (r"(?i)secret[_-]?key\s*[:=]\s*[^\s]+", "检测到疑似 Secret Key"),
            (r"(?i)password\s*[:=]\s*[^\s]+", "检测到疑似密码字段"),
            (r"(?i)token\s*[:=]\s*[^\s]+", "检测到疑似 Token 字段"),
            (r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----", "检测到私钥内容"),
        ]
        for pattern, reason in patterns:
            if re.search(pattern, output):
                return "", True, reason
        return output, False, ""

    def _summarize_arguments(self, arguments: Dict) -> Dict:
        summary = {}
        for key, value in arguments.items():
            value_str = str(value)
            summary[key] = value_str[:120] + "..." if len(value_str) > 120 else value_str
        return summary

    def _resolve_tool_origin(self, function_name: str) -> str:
        tool = self.tools.get(function_name)
        if tool is None:
            return "unknown"
        module = tool.__class__.__module__
        if module.startswith("xiaotie.mcp."):
            return "mcp"
        if function_name in {"web_search", "web_fetch"}:
            return "external_api"
        return "internal"
