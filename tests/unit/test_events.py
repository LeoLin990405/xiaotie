"""事件系统测试"""

import asyncio

import pytest

from xiaotie.events import (
    Event,
    EventBroker,
    EventType,
    AgentStartEvent,
    MessageDeltaEvent,
    ToolCompleteEvent,
    get_event_broker,
    set_event_broker,
)


# ---------------------------------------------------------------------------
# 订阅 / 发布
# ---------------------------------------------------------------------------

class TestEventBrokerPubSub:
    async def test_subscribe_and_publish(self):
        """订阅后应能收到发布的事件"""
        broker = EventBroker()
        queue = await broker.subscribe([EventType.AGENT_START])
        event = AgentStartEvent(user_input="hello")
        await broker.publish(event)
        received = queue.get_nowait()
        assert received.type == EventType.AGENT_START
        assert received.user_input == "hello"

    async def test_multiple_event_types(self):
        """订阅多个事件类型应都能收到"""
        broker = EventBroker()
        queue = await broker.subscribe(
            [EventType.AGENT_START, EventType.MESSAGE_DELTA]
        )
        await broker.publish(AgentStartEvent(user_input="hi"))
        await broker.publish(MessageDeltaEvent(content="world"))
        assert queue.qsize() == 2

    async def test_no_event_for_unsubscribed(self):
        """未订阅的事件类型不应收到"""
        broker = EventBroker()
        queue = await broker.subscribe([EventType.AGENT_START])
        await broker.publish(MessageDeltaEvent(content="ignored"))
        assert queue.empty()

    async def test_publish_sync(self):
        """同步发布也应能送达"""
        broker = EventBroker()
        queue = await broker.subscribe([EventType.TOOL_COMPLETE])
        event = ToolCompleteEvent(tool_name="bash", success=True)
        broker.publish_sync(event)
        assert queue.qsize() == 1

    async def test_buffer_overflow_drops_old(self):
        """队列满时应丢弃旧事件并放入新事件"""
        broker = EventBroker(buffer_size=2)
        queue = await broker.subscribe([EventType.MESSAGE_DELTA])
        await broker.publish(MessageDeltaEvent(content="1"))
        await broker.publish(MessageDeltaEvent(content="2"))
        await broker.publish(MessageDeltaEvent(content="3"))
        assert queue.qsize() == 2


# ---------------------------------------------------------------------------
# 取消订阅
# ---------------------------------------------------------------------------

class TestEventBrokerUnsubscribe:
    async def test_unsubscribe_stops_delivery(self):
        """取消订阅后不应再收到事件"""
        broker = EventBroker()
        queue = await broker.subscribe([EventType.AGENT_START])
        await broker.unsubscribe(queue, [EventType.AGENT_START])
        await broker.publish(AgentStartEvent(user_input="after"))
        assert queue.empty()

    async def test_auto_cleanup_on_cancel_event(self):
        """cancel_event 触发后应自动清理订阅"""
        broker = EventBroker()
        cancel = asyncio.Event()
        queue = await broker.subscribe(
            [EventType.AGENT_START], cancel_event=cancel
        )
        cancel.set()
        await asyncio.sleep(0.05)
        await broker.publish(AgentStartEvent(user_input="after cancel"))
        assert queue.empty()


# ---------------------------------------------------------------------------
# 全局 broker
# ---------------------------------------------------------------------------

class TestGlobalBroker:
    def test_get_and_set(self):
        original = get_event_broker()
        new_broker = EventBroker(buffer_size=64)
        set_event_broker(new_broker)
        assert get_event_broker() is new_broker
        set_event_broker(original)
