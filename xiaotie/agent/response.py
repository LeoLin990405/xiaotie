"""
响应处理器 - 流式/非流式 LLM 响应处理

从 Agent god class 中提取的响应处理逻辑，包括:
- 流式响应处理与事件发布
- Token 统计与预算管理
- 历史消息摘要
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from xiaotie.events import (
    Event,
    EventType,
    MessageDeltaEvent,
    ThinkingDeltaEvent,
    TokenUpdateEvent,
    get_event_broker,
)
from xiaotie.llm import LLMClient
from xiaotie.schema import LLMResponse, Message
from xiaotie.telemetry import AgentTelemetry

logger = logging.getLogger(__name__)

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False


class ResponseHandler:
    """LLM 响应处理器

    负责:
    - 流式/非流式响应的统一处理
    - Token 统计和预算管理
    - 历史消息自动摘要
    """

    def __init__(
        self,
        llm: LLMClient,
        telemetry: AgentTelemetry,
        session_id: str,
        token_limit: int = 100000,
        summary_threshold: float = 0.8,
        summary_keep_recent: int = 5,
        enable_thinking: bool = True,
        quiet: bool = False,
    ):
        self.llm = llm
        self.telemetry = telemetry
        self.session_id = session_id
        self.token_limit = token_limit
        self.summary_threshold = summary_threshold
        self.summary_keep_recent = summary_keep_recent
        self.enable_thinking = enable_thinking
        self.quiet = quiet

        self._event_broker = get_event_broker()

        # Token 统计
        self.api_total_tokens = 0
        self.api_input_tokens = 0
        self.api_output_tokens = 0

        # tiktoken 编码器
        self._encoding = None
        if _HAS_TIKTOKEN:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

        # 增量 token 缓存
        self._cached_token_count = 0
        self._cached_message_count = 0

        # 输出回调
        self.on_thinking: Optional[Callable[[str], None]] = None
        self.on_content: Optional[Callable[[str], None]] = None

    def estimate_tokens(self, messages: list[Message]) -> int:
        """估算消息的 token 数 (增量计算)"""
        current_count = len(messages)

        if current_count < self._cached_message_count:
            self._cached_token_count = 0
            self._cached_message_count = 0

        if self._encoding is None:
            new_chars = sum(
                len(str(msg.content)) + len(str(msg.thinking or ""))
                for msg in messages[self._cached_message_count :]
            )
            self._cached_token_count += new_chars // 4
        else:
            new_tokens = 0
            for msg in messages[self._cached_message_count :]:
                if isinstance(msg.content, str):
                    new_tokens += len(self._encoding.encode(msg.content))
                if msg.thinking:
                    new_tokens += len(self._encoding.encode(msg.thinking))
            self._cached_token_count += new_tokens

        self._cached_message_count = current_count
        return self._cached_token_count

    async def generate(
        self,
        messages: list[Message],
        tool_schemas: list,
        stream: bool = True,
    ) -> LLMResponse:
        """生成 LLM 响应

        Args:
            messages: 消息历史
            tool_schemas: 工具 schema 列表
            stream: 是否流式

        Returns:
            LLMResponse
        """
        tools_arg = tool_schemas if tool_schemas else None

        if stream:
            response = await self._stream_generate(messages, tools_arg)
        else:
            response = await self.llm.generate(messages=messages, tools=tools_arg)

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

        return response

    async def maybe_summarize(self, messages: list[Message]) -> list[Message]:
        """检查并在需要时摘要历史消息

        Returns:
            可能被摘要后的消息列表
        """
        estimated = self.estimate_tokens(messages)
        threshold = int(self.token_limit * self.summary_threshold)

        if estimated <= threshold and self.api_total_tokens <= threshold:
            return messages

        if not self.quiet:
            logger.info("Token 接近上限 (%d/%d), 触发摘要...", estimated, self.token_limit)

        system_msg = messages[0] if messages and messages[0].role == "system" else None
        new_messages = [system_msg] if system_msg else []

        user_messages = [m for m in messages[1:] if m.role == "user"]
        other_messages = [m for m in messages[1:] if m.role != "user"]

        keep = self.summary_keep_recent
        recent_user = user_messages[-keep:] if len(user_messages) > keep else user_messages
        old_user = user_messages[:-keep] if len(user_messages) > keep else []

        content_to_summarize = []
        for msg in old_user:
            content_to_summarize.append(f"[用户]: {msg.content[:200]}")
        for msg in other_messages[:-10]:
            if msg.content:
                content_to_summarize.append(f"[{msg.role}]: {str(msg.content)[:200]}")

        if content_to_summarize:
            summary_prompt = "请用中文简洁摘要以下对话内容（保留关键信息和决策）:\n\n" + "\n".join(
                content_to_summarize[-30:]
            )
            try:
                summary_response = await self.llm.generate(
                    [Message(role="user", content=summary_prompt)]
                )
                new_messages.append(
                    Message(role="assistant", content=f"[历史摘要]\n{summary_response.content}")
                )
            except Exception as e:
                logger.warning("摘要生成失败: %s", e)

        new_messages.extend(recent_user)
        new_messages.extend(other_messages[-10:])

        # 重置 token 缓存
        self._cached_token_count = 0
        self._cached_message_count = 0

        if not self.quiet:
            logger.info("摘要完成, 消息数: %d", len(new_messages))
        return new_messages

    async def _stream_generate(self, messages: list[Message], tools) -> LLMResponse:
        """流式生成"""
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

        def _schedule_flush():
            nonlocal _flush_task
            if _flush_task is None or _flush_task.done():
                _flush_task = asyncio.create_task(_flush_events())

        def _buffer_event(event: Event):
            _event_buffer.append(event)
            if len(_event_buffer) >= _FLUSH_SIZE:
                _schedule_flush()

        async def on_thinking(text: str):
            nonlocal thinking_started
            if self.quiet:
                return
            if not thinking_started:
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
                content_started = True
                await self._publish_event(Event(type=EventType.MESSAGE_START))
            _buffer_event(MessageDeltaEvent(content=text))
            if self.on_content:
                self.on_content(text)

        def sync_on_thinking(text: str):
            asyncio.create_task(on_thinking(text))

        def sync_on_content(text: str):
            asyncio.create_task(on_content(text))

        response = await self.llm.generate_stream(
            messages=messages,
            tools=tools,
            on_thinking=sync_on_thinking,
            on_content=sync_on_content,
            enable_thinking=self.enable_thinking,
        )

        if _flush_task is not None:
            await _flush_task
        await _flush_events()

        if thinking_started:
            await self._publish_event(Event(type=EventType.THINKING_COMPLETE))
        if content_started:
            await self._publish_event(Event(type=EventType.MESSAGE_COMPLETE))

        return response

    async def _publish_event(self, event: Event):
        event.session_id = self.session_id
        await self._event_broker.publish(event)
