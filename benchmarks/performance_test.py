"""
性能基准测试脚本

用于测试小铁框架的性能改进
"""

import asyncio
import time

from xiaotie import Agent, AsyncLRUCache
from xiaotie.events import EventBroker, EventType, MessageDeltaEvent
from xiaotie.tools import PythonTool


async def test_cache_performance():
    """测试缓存性能"""
    print("🧪 测试缓存性能...")

    max_size = 1000
    total_items = 1000
    cache = AsyncLRUCache(max_size=max_size, default_ttl=3600)

    start_time = time.time()

    for i in range(total_items):
        await cache.set(f"key_{i}", f"value_{i}")

    hits = 0
    for i in range(total_items):
        val = await cache.get(f"key_{i}")
        if val == f"value_{i}":
            hits += 1

    cache_size = await cache.size()
    assert cache_size == max_size
    assert hits == total_items

    end_time = time.time()
    print(f"   ✅ 缓存性能测试完成，耗时: {end_time - start_time:.2f}s")


async def test_event_system_performance():
    """测试事件系统性能"""
    print("🧪 测试事件系统性能...")

    total_events = 1000
    broker = EventBroker(buffer_size=total_events)
    queue = await broker.subscribe([EventType.MESSAGE_DELTA])
    start_time = time.time()
    for i in range(total_events):
        await broker.publish(MessageDeltaEvent(content=f"test message {i}"))

    received = 0
    for _ in range(total_events):
        try:
            await asyncio.wait_for(queue.get(), timeout=0.1)
            received += 1
        except asyncio.TimeoutError:
            break

    assert received == total_events
    end_time = time.time()
    print(
        f"   ✅ 事件系统性能测试完成，发送: {total_events}, 接收: {received}, 耗时: {end_time - start_time:.2f}s"
    )


async def test_agent_creation_performance():
    """测试Agent创建性能"""
    print("🧪 测试Agent创建性能...")

    class MockLLMClient:
        async def generate(self, messages, tools=None):
            from xiaotie.schema import LLMResponse, Message

            return LLMResponse(
                content="Mock response",
                messages=[Message(role="assistant", content="Mock response")],
            )

        async def generate_stream(
            self,
            messages,
            tools=None,
            on_thinking=None,
            on_content=None,
            enable_thinking=True,
        ):
            from xiaotie.schema import LLMResponse, Message

            if on_content:
                on_content("Mock streaming response")
            return LLMResponse(
                content="Mock streaming response",
                messages=[Message(role="assistant", content="Mock streaming response")],
            )

    start_time = time.time()

    for i in range(10):
        agent = Agent(
            llm_client=MockLLMClient(),
            system_prompt="You are a test assistant.",
            tools=[PythonTool()],
            max_steps=5,
        )

        result = await agent.run(f"Calculate {i} + {i}")
        assert result is not None

    end_time = time.time()
    print(f"   ✅ Agent创建性能测试完成，耗时: {end_time - start_time:.2f}s")


async def run_all_tests():
    """运行所有性能测试"""
    print("🚀 开始性能基准测试...\n")

    await test_cache_performance()
    await test_event_system_performance()
    await test_agent_creation_performance()

    print("\n✅ 所有性能测试完成！")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
