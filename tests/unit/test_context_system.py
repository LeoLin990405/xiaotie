"""
上下文感知系统测试

验证新上下文功能的工作情况
"""

import asyncio
from xiaotie import MemoryManager, TaskManager, ContextManager, ContextAwareAgentMixin, ContextType, ContextScope


async def test_context_extraction():
    """测试上下文提取功能"""
    print("🌐 测试上下文提取功能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    task_manager = TaskManager()
    
    # 创建上下文管理器
    context_manager = ContextManager(memory_manager, task_manager)
    
    # 测试文本
    text1 = "我想了解一下Python编程语言，特别是关于性能优化方面的内容。我的邮箱是user@example.com，联系电话是123-456-7890。"
    text2 = "关于数据库查询优化，我遇到了一些问题。日期是2023-05-15，时间大约是14:30。"
    
    # 提取上下文
    context1 = await context_manager.extract_context(text1, ContextType.DOMAIN, ContextScope.SESSION)
    context2 = await context_manager.extract_context(text2, ContextType.TASK, ContextScope.LOCAL)
    
    print(f"   上下文帧1包含 {len(context1.entities)} 个实体")
    print(f"   上下文帧2包含 {len(context2.entities)} 个实体")
    
    # 显示提取的实体
    for i, entity in enumerate(context1.entities[:5]):  # 显示前5个
        print(f"   实体{i+1}: {entity.name} ({entity.entity_type}) - 置信度: {entity.confidence:.2f}")
    
    print("   ✅ 上下文提取功能测试完成")


async def test_context_relevance():
    """测试上下文相关性"""
    print("🔍 测试上下文相关性...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    task_manager = TaskManager()
    context_manager = ContextManager(memory_manager, task_manager)
    
    # 添加一些上下文
    await context_manager.extract_context(
        "Python性能优化方法包括缓存、算法优化和数据结构选择",
        ContextType.TOPICAL,
        ContextScope.CONVERSATION
    )
    
    await context_manager.extract_context(
        "数据库查询优化涉及索引、查询重写和连接策略",
        ContextType.TOPICAL,
        ContextScope.CONVERSATION
    )
    
    await context_manager.extract_context(
        "前端性能优化包括资源压缩、懒加载和CDN使用",
        ContextType.TOPICAL,
        ContextScope.CONVERSATION
    )
    
    # 查询相关上下文
    relevant_contexts = await context_manager.get_relevant_context("Python性能", top_k=2)
    print(f"   找到 {len(relevant_contexts)} 个与'Python性能'相关的上下文")
    
    # 获取显著实体
    salient_entities = await context_manager.get_salient_entities(threshold=0.4)
    print(f"   找到 {len(salient_entities)} 个显著实体")
    
    for entity in salient_entities[:3]:
        print(f"   显著实体: {entity.name} ({entity.entity_type}) - 显著度: {entity.relevance:.2f}")
    
    print("   ✅ 上下文相关性测试完成")


async def test_topic_shift_detection():
    """测试话题转换检测"""
    print("🔄 测试话题转换检测...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    task_manager = TaskManager()
    context_manager = ContextManager(memory_manager, task_manager)
    
    # 模拟连续对话
    texts = [
        "我想学习Python编程，特别是面向对象编程",
        "Python的类和继承是如何工作的？",
        "数据库设计中的一致性原则是什么？",
        "如何优化SQL查询性能？"
    ]
    
    for text in texts:
        await context_manager.extract_context(text, ContextType.CONVERSATIONAL, ContextScope.SESSION)
        
        # 检查话题转换
        topic_changed, new_topic, old_topic = await context_manager.infer_topic_shift(text)
        
        if topic_changed:
            print(f"   话题转换检测: 从 '{old_topic}' 到 '{new_topic}'")
        else:
            print(f"   话题保持: '{text[:30]}...'")
    
    print("   ✅ 话题转换检测测试完成")


async def test_context_aware_agent():
    """测试上下文感知Agent"""
    print("🤖 测试上下文感知Agent...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    task_manager = TaskManager()
    context_manager = ContextManager(memory_manager, task_manager)
    
    # 创建Agent混入
    agent_mixin = ContextAwareAgentMixin(context_manager)
    
    # 处理带上下文的输入
    result1 = await agent_mixin.process_with_context(
        "请帮我优化这段Python代码的性能",
        ContextType.TASK,
        ContextScope.LOCAL
    )
    
    print(f"   原始文本长度: {len(result1['original_text'])}")
    print(f"   增强后文本长度: {len(result1['context_enhanced_text'])}")
    print(f"   提取实体数: {result1['extracted_context']['entities_count']}")
    print(f"   显著实体数: {result1['extracted_context']['salient_entities_count']}")
    
    # 获取当前上下文状态
    state = await agent_mixin.get_current_context_state()
    print(f"   活跃上下文帧数: {state['active_context_frames']}")
    print(f"   摘要中的实体数: {state['summary']['total_entities']}")
    
    # 获取任务上下文
    task_context = await agent_mixin.get_task_context("Python性能优化")
    print(f"   任务相关上下文帧数: {task_context['relevant_frames_count']}")
    print(f"   相关实体数: {len(task_context['relevant_entities'])}")
    
    print("   ✅ 上下文感知Agent测试完成")


async def test_context_summary():
    """测试上下文摘要功能"""
    print("📋 测试上下文摘要功能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    task_manager = TaskManager()
    context_manager = ContextManager(memory_manager, task_manager)
    
    # 添加多种类型的上下文
    topics = [
        ("Python编程技巧", ContextType.TOPICAL),
        ("数据库设计原则", ContextType.TOPICAL),
        ("前端开发最佳实践", ContextType.TOPICAL),
        ("系统架构设计", ContextType.TASK),
        ("性能优化策略", ContextType.TASK)
    ]
    
    for topic, ctx_type in topics:
        await context_manager.extract_context(topic, ctx_type, ContextScope.SESSION)
    
    # 获取摘要
    summary = await context_manager.get_context_summary()
    
    print(f"   总上下文帧数: {summary['total_frames']}")
    print(f"   总实体数: {summary['total_entities']}")
    print(f"   上下文类型分布: {dict(summary['context_types'])}")
    print(f"   最常见实体: {summary['most_common_entities'][:3]}")
    print(f"   活跃话题: {summary['active_topics'][:5]}")
    
    # 按作用域获取摘要
    session_summary = await context_manager.get_context_summary(ContextScope.SESSION)
    print(f"   会话级上下文帧数: {session_summary['total_frames']}")
    
    print("   ✅ 上下文摘要功能测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行上下文感知系统测试...\n")
    
    await test_context_extraction()
    print()
    
    await test_context_relevance()
    print()
    
    await test_topic_shift_detection()
    print()
    
    await test_context_aware_agent()
    print()
    
    await test_context_summary()
    print()
    
    print("🎉 所有测试完成！上下文感知系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())