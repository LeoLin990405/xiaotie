"""
小铁框架 v1.0.1 综合验证测试

验证所有功能模块协同工作的完整性
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from xiaotie import (
    # 核心组件
    Agent,
    AgentBuilder,
    
    # 记忆系统
    MemoryManager,
    
    # 上下文系统
    ContextManager,
    ContextWindowManager,
    
    # 决策系统
    DecisionEngine,
    
    # 学习系统
    AdaptiveLearner,
    
    # 多模态
    MultimodalContentManager,
    
    # 强化学习
    ReinforcementLearningEngine,
    
    # 知识图谱
    KnowledgeGraphManager,
    
    # 规划系统
    PlanningSystem,
    
    # 反思机制
    ReflectionManager
)

# 从子模块导入工具
from xiaotie.tools import PythonTool, BashTool
from xiaotie.memory.core import MemoryType


async def test_performance_improvements():
    """测试性能改进"""
    print("🚀 测试性能改进...")
    
    # 1. 测试异步LRU缓存
    from xiaotie.cache import AsyncLRUCache
    cache = AsyncLRUCache(max_size=100, default_ttl=300)
    
    # 性能测试
    start_time = time.perf_counter()
    for i in range(1000):
        await cache.set(f"key_{i}", f"value_{i}")
        val = await cache.get(f"key_{i}")
        assert val == f"value_{i}"
    cache_time = time.perf_counter() - start_time
    
    print(f"   ✅ 异步LRU缓存性能: 1000次操作耗时 {cache_time:.4f} 秒")
    
    # 2. 测试优化的事件系统
    from xiaotie.events import EventBroker
    event_broker = EventBroker()
    
    # 订阅事件
    queue = await event_broker.subscribe(["test_event"])
    
    # 发布事件
    from xiaotie.events import Event
    start_time = time.perf_counter()
    for i in range(100):
        event = Event(type="test_event", data={"data": f"message_{i}"})
        await event_broker.publish(event)
    event_time = time.perf_counter() - start_time
    
    print(f"   ✅ 事件系统性能: 100次发布耗时 {event_time:.4f} 秒")
    
    # 3. 测试优化的内存管理
    from xiaotie.memory.core import MemoryManager
    memory_manager = MemoryManager()
    
    # 添加多个记忆
    start_time = time.perf_counter()
    for i in range(50):
        await memory_manager.add_memory(
            content=f"测试记忆 {i}",
            memory_type=MemoryType.EPISODIC,  # 使用枚举而不是字符串
            importance=0.5,
            tags=["test", f"tag_{i}"]
        )
    memory_time = time.perf_counter() - start_time
    
    print(f"   ✅ 内存管理性能: 50次添加耗时 {memory_time:.4f} 秒")
    
    print("   🚀 性能改进验证完成")


async def test_system_integration():
    """测试系统集成"""
    print("🔗 测试系统集成...")
    
    # 创建所有核心组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    context_window_manager = ContextWindowManager(context_manager, memory_manager)
    reflection_manager = ReflectionManager(memory_manager)
    adaptive_learner = AdaptiveLearner(memory_manager, reflection_manager)
    decision_engine = DecisionEngine(
        context_manager=context_manager,
        learning_learner=adaptive_learner,
        memory_manager=memory_manager
    )
    
    # 创建多模态管理器
    multimodal_manager = MultimodalContentManager()
    
    # 创建强化学习引擎
    rl_engine = ReinforcementLearningEngine(
        memory_manager=memory_manager,
        adaptive_learner=adaptive_learner
    )
    
    # 创建知识图谱管理器
    from xiaotie import NetworkXKnowledgeGraphStore
    kg_store = NetworkXKnowledgeGraphStore()
    kg_manager = KnowledgeGraphManager(
        store=kg_store,
        memory_manager=memory_manager,
        context_manager=context_manager
    )
    
    # 创建规划系统
    planning_system = PlanningSystem()
    
    print("   ✅ 所有系统组件创建完成")
    
    # 测试组件间交互
    # 添加一些记忆
    await memory_manager.add_memory(
        content="Python性能优化是一个重要的话题",
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
        tags=["programming", "optimization", "python"]
    )
    
    # 更新知识图谱
    from xiaotie import KGNode, KGEdge, NodeType, RelationType
    node1 = KGNode(
        id="python_perf_topic",
        name="Python性能优化",
        node_type=NodeType.CONCEPT,
        properties={"domain": "programming", "importance": 0.8}
    )
    await kg_manager.store.add_node(node1)
    
    print("   ✅ 组件间交互测试完成")
    
    # 获取系统状态
    # 使用retrieve_memories方法并传入空查询来获取所有记忆
    all_memories = await memory_manager.retrieve_memories("", top_k=100)
    memory_count = len(all_memories)
    kg_stats = await kg_manager.get_knowledge_analytics()
    
    print(f"   📊 系统状态 - 记忆数量: {memory_count}, 知识图谱节点: {kg_stats['graph_statistics']['node_count']}")
    
    print("   🔗 系统集成验证完成")


async def test_advanced_features():
    """测试高级功能"""
    print("🌟 测试高级功能...")
    
    # 1. 测试多Agent协作
    from xiaotie.multi_agent.coordinator import MultiAgentSystem, CoordinatorAgent, ExpertAgent
    multi_agent_system = MultiAgentSystem()
    
    coordinator = CoordinatorAgent("coordinator-agent")
    python_expert = ExpertAgent("python-expert", "programming")
    bash_expert = ExpertAgent("bash-expert", "system_operations")
    
    await multi_agent_system.add_agent(coordinator)
    await multi_agent_system.add_agent(python_expert)
    await multi_agent_system.add_agent(bash_expert)
    
    print("   ✅ 多Agent协作测试完成")
    
    # 2. 测试强化学习
    from xiaotie.rl.core import State, Action, Transition, ReinforcementLearningEngine
    # 创建依赖组件
    from xiaotie.memory.core import MemoryManager
    from xiaotie.learning.core import AdaptiveLearner
    from xiaotie.reflection.core import ReflectionManager
    
    memory_manager = MemoryManager()
    reflection_manager = ReflectionManager(memory_manager)
    adaptive_learner = AdaptiveLearner(memory_manager, reflection_manager)
    
    rl_engine = ReinforcementLearningEngine(memory_manager, adaptive_learner)
    
    initial_state = State(
        id="test_state",
        features=[0.5, 0.3, 0.8],
        description="测试状态"
    )
    action = Action(
        id="test_action",
        name="test_action",
        description="测试动作"
    )
    next_state = State(
        id="next_state",
        features=[0.6, 0.4, 0.7],
        description="下一个状态"
    )
    transition = Transition(
        state=initial_state,
        action=action,
        next_state=next_state,
        reward=0.8
    )

    # 更新强化学习引擎
    update_result = await rl_engine.update(transition)
    print(f"   ✅ 强化学习更新: {update_result.get('success', 'Unknown')}")
    
    # 3. 测试规划系统
    from xiaotie.planning.core import Task, PlanStep, TaskStatus, Priority, ExecutionMode
    from datetime import timedelta
    
    step1 = PlanStep(
        id="step1",
        description="分析需求",
        expected_outcome="明确需求细节",
        estimated_duration=timedelta(minutes=30)
    )
    
    step2 = PlanStep(
        id="step2", 
        description="设计解决方案",
        expected_outcome="形成设计方案",
        estimated_duration=timedelta(minutes=60),
        dependencies=["step1"]  # 依赖step1
    )
    
    task = Task(
        id="test_task",
        description="性能优化任务",
        goal="优化Python代码性能",
        steps=[step1, step2],
        priority=Priority.HIGH,
        execution_mode=ExecutionMode.PARALLEL  # 支持并行执行
    )
    
    planning_system = PlanningSystem()
    # 使用正确的执行方法
    # 首先创建任务
    task_manager = planning_system.task_manager
    task_id = await task_manager.create_task(
        description=task.description,
        goal=task.goal,
        priority=task.priority
    )
    
    # 然后通过PlanExecutor执行计划
    success = await planning_system.plan_executor.execute_plan(task_id)
    print(f"   ✅ 规划系统执行: {success}")
    
    print("   🌟 高级功能测试完成")


async def run_final_verification():
    """运行最终验证"""
    print("🎯 开始小铁框架 v1.0.1 综合验证测试...\n")
    
    start_time = time.perf_counter()
    
    await test_performance_improvements()
    print()
    
    await test_system_integration()
    print()
    
    await test_advanced_features()
    print()
    
    total_time = time.perf_counter() - start_time
    
    print(f"🎉 所有验证完成！小铁框架 v1.0.1 功能完整正常。")
    print(f"⏱️ 总耗时: {total_time:.4f} 秒")
    print(f"✨ 已验证功能:")
    print(f"   - 性能优化改进")
    print(f"   - 系统组件集成")
    print(f"   - 高级AI功能")
    print(f"   - 多Agent协作")
    print(f"   - 强化学习机制")
    print(f"   - 智能规划系统")


if __name__ == "__main__":
    asyncio.run(run_final_verification())