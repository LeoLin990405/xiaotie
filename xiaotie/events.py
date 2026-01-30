"""事件系统

参考 OpenCode 的 Pub/Sub 设计：
- 非阻塞事件发布
- 类型安全的事件订阅
- 上下文感知的自动清理
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar


class EventType(Enum):
    """事件类型"""

    # Agent 事件
    AGENT_START = "agent_start"
    AGENT_STEP = "agent_step"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    AGENT_CANCEL = "agent_cancel"

    # 消息事件
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_COMPLETE = "message_complete"

    # 思考事件
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_COMPLETE = "thinking_complete"

    # 工具事件
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_COMPLETE = "tool_complete"
    TOOL_ERROR = "tool_error"

    # Token 事件
    TOKEN_UPDATE = "token_update"


@dataclass
class Event:
    """事件基类"""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStartEvent(Event):
    """Agent 开始事件"""

    type: EventType = EventType.AGENT_START
    user_input: str = ""


@dataclass
class AgentStepEvent(Event):
    """Agent 步骤事件"""

    type: EventType = EventType.AGENT_STEP
    step: int = 0
    total_steps: int = 0


@dataclass
class MessageDeltaEvent(Event):
    """消息增量事件"""

    type: EventType = EventType.MESSAGE_DELTA
    content: str = ""
    role: str = "assistant"


@dataclass
class ThinkingDeltaEvent(Event):
    """思考增量事件"""

    type: EventType = EventType.THINKING_DELTA
    content: str = ""


@dataclass
class ToolStartEvent(Event):
    """工具开始事件"""

    type: EventType = EventType.TOOL_START
    tool_name: str = ""
    tool_id: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCompleteEvent(Event):
    """工具完成事件"""

    type: EventType = EventType.TOOL_COMPLETE
    tool_name: str = ""
    tool_id: str = ""
    success: bool = True
    result: str = ""
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class TokenUpdateEvent(Event):
    """Token 更新事件"""

    type: EventType = EventType.TOKEN_UPDATE
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


T = TypeVar("T", bound=Event)


class EventBroker(Generic[T]):
    """事件代理 - 非阻塞发布/订阅"""

    def __init__(self, buffer_size: int = 64):
        self._subscribers: Dict[EventType, List[asyncio.Queue]] = {}
        self._buffer_size = buffer_size
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        event_types: List[EventType],
        cancel_event: Optional[asyncio.Event] = None,
    ) -> asyncio.Queue:
        """订阅事件类型"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._buffer_size)

        async with self._lock:
            for event_type in event_types:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(queue)

        # 如果提供了取消事件，设置自动清理
        if cancel_event:
            asyncio.create_task(self._auto_cleanup(queue, event_types, cancel_event))

        return queue

    async def _auto_cleanup(
        self,
        queue: asyncio.Queue,
        event_types: List[EventType],
        cancel_event: asyncio.Event,
    ):
        """自动清理订阅"""
        await cancel_event.wait()
        await self.unsubscribe(queue, event_types)

    async def unsubscribe(
        self,
        queue: asyncio.Queue,
        event_types: List[EventType],
    ):
        """取消订阅"""
        async with self._lock:
            for event_type in event_types:
                if event_type in self._subscribers:
                    try:
                        self._subscribers[event_type].remove(queue)
                    except ValueError:
                        pass

    async def publish(self, event: T):
        """发布事件（非阻塞）"""
        if event.type not in self._subscribers:
            return

        for queue in self._subscribers[event.type]:
            try:
                # 非阻塞放入，如果队列满则丢弃
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 队列满，丢弃旧事件
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def publish_sync(self, event: T):
        """同步发布事件（用于非异步上下文）"""
        if event.type not in self._subscribers:
            return

        for queue in self._subscribers[event.type]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


# 全局事件代理
_global_broker: Optional[EventBroker] = None


def get_event_broker() -> EventBroker:
    """获取全局事件代理"""
    global _global_broker
    if _global_broker is None:
        _global_broker = EventBroker()
    return _global_broker


def set_event_broker(broker: EventBroker):
    """设置全局事件代理"""
    global _global_broker
    _global_broker = broker
