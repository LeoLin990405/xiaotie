"""
性能基准测试脚本

用于测试小铁框架的性能改进
"""

import asyncio
import time
from pathlib import Path

from xiaotie import Agent, AsyncLRUCache, get_global_cache
from xiaotie.events import EventBroker, EventType
from xiaotie.llm import LLMClient
from xiaotie.tools import ReadTool, WriteTool, BashTool, PythonTool


async def test_cache_performance():
    """测试缓存性能"""
    print("🧪 测试缓存性能...")
    
    cache = AsyncLRUCache(max_size=100, default_ttl=3600)
    
    # 测试大量数据的存取性能
    start_time = time.time()
    
    # 存入1000个项目
    for i in range(1000):
        await cache.set(f"key_{i}", f"value_{i}")
    
    # 读取1000个项目
    for i in range(1000):
        val = await cache.get(f"key_{i}")
        assert val == f"value_{i}"
    
    end_time = time.time()
    print(f"   ✅ 缓存性能测试完成，耗时: {end_time - start_time:.2f}s")


async def test_event_system_performance():
    """测试事件系统性能"""
    print("🧪 测试事件系统性能...")
    
    broker = EventBroker(buffer_size=128)
    
    # 订阅消息事件
    queue = await broker.subscribe([EventType.MESSAGE_DELTA])
    
    start_time = time.time()
    
    # 发布1000个事件
    for i in range(1000):
        await broker.publish(EventType.MESSAGE_DELTA, f"test message {i}")
    
    # 接收事件
    received = 0
    for _ in range(1000):
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.1)
            received += 1
        except asyncio.TimeoutError:
            break
    
    end_time = time.time()
    print(f"   ✅ 事件系统性能测试完成，发送: 1000, 接收: {received}, 耗时: {end_time - start_time:.2f}s")


async def test_agent_creation_performance():
    """测试Agent创建性能"""
    print("🧪 测试Agent创建性能...")
    
    # 模拟LLM客户端
    class MockLLMClient:
        async def generate(self, messages, tools=None):
            from xiaotie.schema import LLMResponse, Message
            return LLMResponse(content="Mock response", messages=[Message(role="assistant", content="Mock response")])
        
        async def generate_stream(self, messages, tools=None, on_thinking=None, on_content=None, enable_thinking=True):
            from xiaotie.schema import LLMResponse, Message
            if on_content:
                on_content("Mock streaming response")
            return LLMResponse(content="Mock streaming response", messages=[Message(role="assistant", content="Mock streaming response")])
    
    start_time = time.time()
    
    # 创建并运行多个Agent实例
    for i in range(10):
        agent = Agent(
            llm_client=MockLLMClient(),
            system_prompt="You are a test assistant.",
            tools=[PythonTool()],
            max_steps=5,
        )
        
        # 运行简单任务
        result = await agent.run(f"Calculate {i} + {i}")
    
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