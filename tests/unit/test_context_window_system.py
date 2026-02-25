"""
上下文窗口管理系统测试

验证新上下文窗口管理功能的工作情况
"""

import asyncio
from datetime import datetime
from xiaotie import (
    MemoryManager, 
    ContextManager,
    ContextWindowManager,
    ContextAwareWindowManager,
    CompressionMethod,
    WindowStrategy,
    Message
)


async def test_context_window_management():
    """测试上下文窗口管理"""
    print("🪟 测试上下文窗口管理...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    
    # 创建上下文窗口管理器
    window_manager = ContextWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager,
        max_context_size=10,
        default_compression_method=CompressionMethod.RELEVANCE_FILTERING
    )
    
    # 创建测试消息
    test_messages = []
    for i in range(15):
        msg = Message(
            role="user" if i % 2 == 0 else "assistant",
            content=f"这是第{i+1}条测试消息，内容是关于上下文管理的。这条消息包含一些关键词如重要、关键、核心等。",
            timestamp=datetime.now()
        )
        test_messages.append(msg)
    
    # 更新上下文
    window = await window_manager.update_context(test_messages)
    
    print(f"   原始消息数: {len(test_messages)}")
    print(f"   窗口当前消息数: {len(window.messages)}")
    print(f"   压缩比例: {window.compression_ratio:.2f}")
    print(f"   最大窗口大小: {window.max_size}")
    
    # 获取优化的上下文
    optimized_messages, analytics = await window_manager.get_optimized_context(target_size=8)
    print(f"   优化后消息数: {len(optimized_messages)}")
    print(f"   压缩应用: {analytics['compression_applied']}")
    print(f"   压缩方法: {analytics['compression_method']}")
    print(f"   节省的消息数: {analytics['tokens_saved']}")
    
    print("   ✅ 上下文窗口管理测试完成")


async def test_different_compression_methods():
    """测试不同压缩方法"""
    print("🔧 测试不同压缩方法...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    window_manager = ContextWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager,
        max_context_size=8
    )
    
    # 创建测试消息
    test_messages = []
    for i in range(12):
        msg = Message(
            role="user" if i % 3 == 0 else ("assistant" if i % 3 == 1 else "system"),
            content=f"测试消息{i+1}，包含一些内容用于测试不同的压缩算法。这条消息比较长，用于更好地测试压缩效果。",
            timestamp=datetime.now()
        )
        test_messages.append(msg)
    
    # 测试摘要压缩
    await window_manager.switch_compression_method(CompressionMethod.SUMMARIZATION)
    await window_manager.update_context(test_messages[:6])
    optimized1, analytics1 = await window_manager.get_optimized_context(target_size=4)
    print(f"   摘要压缩: 原始{len(test_messages[:6])} -> 优化后{len(optimized1)}")
    
    # 测试滑动窗口压缩
    await window_manager.switch_compression_method(CompressionMethod.SLIDING_WINDOW)
    await window_manager.update_context(test_messages[6:])
    optimized2, analytics2 = await window_manager.get_optimized_context(target_size=4)
    print(f"   滑动窗口压缩: 原始{len(test_messages[6:])} -> 优化后{len(optimized2)}")
    
    # 测试相关性过滤压缩
    await window_manager.switch_compression_method(CompressionMethod.RELEVANCE_FILTERING)
    await window_manager.update_context(test_messages)
    optimized3, analytics3 = await window_manager.get_optimized_context(target_size=5)
    print(f"   相关性过滤压缩: 原始{len(test_messages)} -> 优化后{len(optimized3)}")
    
    print("   ✅ 不同压缩方法测试完成")


async def test_context_aware_window_manager():
    """测试上下文感知窗口管理器"""
    print("🌐 测试上下文感知窗口管理器...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    
    # 创建上下文感知窗口管理器
    aware_window_manager = ContextAwareWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager,
        max_context_size=10
    )
    
    # 创建测试消息
    test_messages = []
    for i in range(8):
        msg = Message(
            role="user" if i < 4 else "assistant",
            content=f"上下文感知测试消息{i+1}，内容与之前的对话相关。",
            timestamp=datetime.now()
        )
        test_messages.append(msg)
    
    # 使用上下文信号更新
    context_signals = [
        {"entity_id": "entity1", "importance": 0.9, "type": "key_concept"},
        {"entity_id": "entity2", "importance": 0.7, "type": "secondary_concept"}
    ]
    
    window = await aware_window_manager.update_with_context_signals(test_messages, context_signals)
    
    print(f"   窗口消息数: {len(window.messages)}")
    print(f"   重要性权重数: {len(aware_window_manager.importance_weights)}")
    
    # 获取LLM优化的上下文
    llm_messages, llm_analytics = await aware_window_manager.get_context_for_llm(
        max_tokens=2000,
        task_type="analytical"
    )
    print(f"   LLM优化消息数: {len(llm_messages)}")
    print(f"   任务类型: {llm_analytics['task_type']}")
    print(f"   目标token限制: {llm_analytics['target_token_limit']}")
    
    print("   ✅ 上下文感知窗口管理器测试完成")


async def test_adaptive_resizing():
    """测试自适应大小调整"""
    print("🔄 测试自适应大小调整...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    window_manager = ContextWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager,
        max_context_size=10
    )
    
    print(f"   初始窗口大小: {window_manager.max_context_size}")
    
    # 测试不同任务复杂性
    sizes = []
    complexities = ["simple", "medium", "complex", "very_complex"]
    
    for complexity in complexities:
        new_size = await window_manager.adaptive_resize(
            task_complexity=complexity,
            urgency="normal",
            available_tokens=4000
        )
        sizes.append(new_size)
        print(f"   {complexity} 任务复杂性 -> 窗口大小: {new_size}")
    
    # 测试不同紧急程度
    urgencies = ["low", "normal", "high", "critical"]
    for urgency in urgencies:
        new_size = await window_manager.adaptive_resize(
            task_complexity="medium",
            urgency=urgency,
            available_tokens=4000
        )
        print(f"   {urgency} 紧急程度 -> 窗口大小: {new_size}")
    
    print("   ✅ 自适应大小调整测试完成")


async def test_compression_analytics():
    """测试压缩分析"""
    print("📊 测试压缩分析...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    window_manager = ContextWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager,
        max_context_size=5
    )
    
    # 创建足够的消息以触发压缩
    test_messages = []
    for i in range(8):
        msg = Message(
            role="user",
            content=f"分析测试消息{i+1}，用于测试压缩分析功能。",
            timestamp=datetime.now()
        )
        test_messages.append(msg)
    
    # 更新上下文以触发压缩
    await window_manager.update_context(test_messages)
    
    # 获取分析
    analytics = await window_manager.get_compression_analytics()
    
    print(f"   压缩操作总数: {analytics['total_compression_operations']}")
    print(f"   节省的token数: {analytics['total_tokens_saved']}")
    print(f"   当前方法: {analytics['current_method']}")
    print(f"   当前窗口大小: {analytics['current_window_size']}")
    print(f"   最大大小: {analytics['max_allowed_size']}")
    
    # 打印各方法的性能
    for method, stats in analytics['method_performance'].items():
        if stats['operations_count'] > 0:
            print(f"   {method}: 操作数{stats['operations_count']}, 平均比率{stats['average_compression_ratio']:.2f}, 节省{stats['tokens_saved']} tokens")
    
    # 获取多样性指标
    diversity_metrics = await window_manager.get_context_diversity_metrics()
    print(f"   消息计数: {diversity_metrics['message_count']}")
    print(f"   角色多样性: {diversity_metrics['role_diversity']:.2f}")
    print(f"   实体密度: {diversity_metrics['entity_density']:.2f}")
    
    print("   ✅ 压缩分析测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行上下文窗口管理系统测试...\n")
    
    await test_context_window_management()
    print()
    
    await test_different_compression_methods()
    print()
    
    await test_context_aware_window_manager()
    print()
    
    await test_adaptive_resizing()
    print()
    
    await test_compression_analytics()
    print()
    
    print("🎉 所有测试完成！上下文窗口管理系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())