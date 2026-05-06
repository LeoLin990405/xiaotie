"""事件系统

参考 OpenCode 的 Pub/Sub 设计：
- 非阻塞事件发布
- 类型安全的事件订阅
- 上下文感知的自动清理
- 高效的事件传播机制
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Set, TypeVar


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

    # 会话事件
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # 系统事件
    SYSTEM_STATUS = "system_status"


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


@dataclass
class SessionStartEvent(Event):
    """会话开始事件"""

    type: EventType = EventType.SESSION_START
    session_name: str = ""


@dataclass
class SessionEndEvent(Event):
    """会话结束事件"""

    type: EventType = EventType.SESSION_END
    session_name: str = ""
    reason: str = ""


@dataclass
class SystemStatusEvent(Event):
    """系统状态事件"""

    type: EventType = EventType.SYSTEM_STATUS
    status: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


T = TypeVar("T", bound=Event)


class EventBroker(Generic[T]):
    """事件代理 - 非阻塞发布/订阅（copy-on-read 模式）"""

    def __init__(self, buffer_size: int = 128, dead_ref_threshold: int = 50):
        self._subscribers: Dict[EventType, Set[weakref.ref]] = {}
        self._buffer_size = buffer_size
        self._lock = asyncio.Lock()
        self._dead_ref_count = 0
        self._dead_ref_threshold = dead_ref_threshold

    async def subscribe(
        self,
        event_types: List[EventType],
        cancel_event: Optional[asyncio.Event] = None,
    ) -> asyncio.Queue:
        """订阅指定类型的事件。

        创建一个异步队列，接收匹配类型的事件。使用弱引用管理订阅者，
        当队列被垃圾回收时自动清理订阅。

        Args:
            event_types: 要订阅的事件类型列表，如 [EventType.TOOL_START, EventType.MESSAGE_DELTA]。
            cancel_event: 可选的取消事件。当该事件被设置时，自动取消订阅并清理资源。

        Returns:
            asyncio.Queue: 事件队列，通过 await queue.get() 接收事件。
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._buffer_size)

        async with self._lock:
            for event_type in event_types:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = set()
                self._subscribers[event_type].add(weakref.ref(queue))

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
                    dead_refs = set()
                    for ref in self._subscribers[event_type]:
                        if ref() is None or ref() is queue:
                            dead_refs.add(ref)
                    for ref in dead_refs:
                        self._subscribers[event_type].discard(ref)

    async def _batch_cleanup_dead_refs(self):
        """延迟批量清理死引用（在锁内调用）"""
        for event_type in list(self._subscribers.keys()):
            refs = self._subscribers[event_type]
            alive = {ref for ref in refs if ref() is not None}
            self._subscribers[event_type] = alive
        self._dead_ref_count = 0

    async def publish(self, event: T):
        """发布事件（copy-on-read，无锁快速路径）"""
        # 快速路径：无订阅者直接返回
        refs = self._subscribers.get(event.type)
        if not refs:
            return

        # copy-on-read：快照引用集合，无需持锁遍历
        snapshot = list(refs)

        # 分发事件到活跃队列，统计死引用
        local_dead = 0
        for ref in snapshot:
            queue = ref()
            if queue is not None:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        pass
            else:
                local_dead += 1

        # 延迟批量清理：累积死引用超过阈值时才加锁清理
        if local_dead > 0:
            self._dead_ref_count += local_dead
            if self._dead_ref_count >= self._dead_ref_threshold:
                async with self._lock:
                    await self._batch_cleanup_dead_refs()

    async def publish_batch(self, events: List[T]):
        """批量发布事件"""
        if not events:
            return

        local_dead = 0
        events_by_type: Dict[EventType, List[T]] = {}
        for event in events:
            events_by_type.setdefault(event.type, []).append(event)

        for event_type, typed_events in events_by_type.items():
            refs = self._subscribers.get(event_type)
            if not refs:
                continue

            snapshot = list(refs)
            for ref in snapshot:
                queue = ref()
                if queue is None:
                    local_dead += 1
                    continue

                for event in typed_events:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        try:
                            queue.get_nowait()
                            queue.put_nowait(event)
                        except (asyncio.QueueEmpty, asyncio.QueueFull):
                            pass

        if local_dead > 0:
            self._dead_ref_count += local_dead
            if self._dead_ref_count >= self._dead_ref_threshold:
                async with self._lock:
                    await self._batch_cleanup_dead_refs()

    def publish_sync(self, event: T):
        """同步发布事件（用于非异步上下文，copy-on-read）"""
        refs = self._subscribers.get(event.type)
        if not refs:
            return

        snapshot = list(refs)

        for ref in snapshot:
            queue = ref()
            if queue is not None:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass


# 全局事件代理
_global_broker: Optional[EventBroker] = None
_global_broker_lock = threading.Lock()


def get_event_broker() -> EventBroker:
    """获取全局事件代理（线程安全）"""
    global _global_broker
    if _global_broker is None:
        with _global_broker_lock:
            if _global_broker is None:
                _global_broker = EventBroker()
    return _global_broker


def set_event_broker(broker: EventBroker):
    """设置全局事件代理"""
    global _global_broker
    with _global_broker_lock:
        _global_broker = broker
