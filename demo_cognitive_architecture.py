"""
小铁框架 v1.1.0 综合演示

展示所有新功能和改进
"""

import asyncio
from datetime import datetime
import time

from xiaotie import (
    # 核心组件
    Agent,
    AgentBuilder,
    
    # 记忆系统
    MemoryManager,
    MemoryType,
    
    # 上下文系统
    ContextManager,
    ContextWindowManager,
    
    # 决策系统
    DecisionEngine,
    DecisionOption,
    DecisionType,
    
    # 学习系统
    AdaptiveLearner,
    
    # 多模态
    MultimodalContentManager,
    ModalityType,
    MediaContent,
    
    # 强化学习
    ReinforcementLearningEngine,
    State,
    Action,
    Transition,
    
    # 知识图谱
    KnowledgeGraphManager,
    KGNode,
    KGEdge,
    NodeType,
    RelationType,
    
    # 规划系统
    PlanningSystem,
    
    # 反思机制
    ReflectionManager,
    
    # 消息
    Message
)

# 从子模块导入工具
from xiaotie.tools import PythonTool, BashTool


async def demo_cognitive_architecture():
    """演示认知架构增强功能"""
    print("🧠 小铁框架 v1.1.0 认知架构演示\n")
    
    # 1. 创建所有核心组件
    print("1. 初始化核心认知组件...")
    start_time = time.perf_counter()
    
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
    
    init_time = time.perf_counter() - start_time
    print(f"   ✅ 组件初始化完成 (耗时: {init_time:.3f}s)")
    
    # 2. 演示学习能力
    print("\n2. 演示自适应学习能力...")
    
    # 创建学习混入
    from xiaotie.learning.core import LearningAgentMixin
    learning_mixin = LearningAgentMixin(adaptive_learner)
    
    await learning_mixin.learn_from_interaction(
        user_input="用户询问Python性能优化方法",
        agent_response="建议使用缓存、算法优化、并行处理等方法",
        environment_feedback="用户表示非常有帮助",
        reward=0.9
    )
    
    # 获取学习状态
    learning_status = await learning_mixin.get_learning_status()
    print(f"   ✅ 学习记录: {learning_status.get('total_experiences', 0)} 次交互, 平均奖励: {learning_status.get('performance_metrics', {}).get('average_reward', 0.0):.2f}")
    
    # 3. 演示决策能力
    print("\n3. 演示智能决策能力...")
    from xiaotie.decision.core import DecisionOption, DecisionType
    options = [
        DecisionOption(
            id="option1",
            action="使用缓存优化",
            description="实现缓存机制提升性能",
            estimated_outcome="性能提升约30%",
            utility=0.8,
            probability=0.7,
            cost=0.3,
            risk=0.2
        ),
        DecisionOption(
            id="option2",
            action="算法重构",
            description="重构算法提升效率",
            estimated_outcome="性能提升约50%",
            utility=0.9,
            probability=0.6,
            cost=0.7,
            risk=0.4
        )
    ]
    
    chosen_option, analysis = await decision_engine.make_decision(
        options=options,
        context_description="Python性能优化决策",
        decision_type=DecisionType.SEQUENTIAL
    )
    
    print(f"   ✅ 决策结果: {chosen_option.action} (效用: {chosen_option.utility})")
    
    # 4. 演示知识图谱能力
    print("\n4. 演示知识图谱构建与推理...")
    
    # 添加实体和关系
    node1 = KGNode(
        id="python_lang",
        name="Python",
        node_type=NodeType.ENTITY,
        properties={"type": "programming_language", "created_year": 1991, "creator": "Guido van Rossum"}
    )
    
    node2 = KGNode(
        id="performance_optimization",
        name="性能优化",
        node_type=NodeType.CONCEPT,
        properties={"domain": "computer_science", "importance": 0.8}
    )
    
    node3 = KGNode(
        id="cache_mechanism",
        name="缓存机制",
        node_type=NodeType.CONCEPT,
        properties={"category": "optimization_technique", "effectiveness": 0.7}
    )
    
    await kg_manager.store.add_node(node1)
    await kg_manager.store.add_node(node2)
    await kg_manager.store.add_node(node3)
    
    # 添加关系
    edge1 = KGEdge(
        id="python_has_concept_performance",
        source_id="python_lang",
        target_id="performance_optimization",
        relation_type=RelationType.ASSOCIATION,
        properties={"strength": 0.9, "context": "python_performance"}
    )
    
    edge2 = KGEdge(
        id="applies_technique_cache",
        source_id="performance_optimization",
        target_id="cache_mechanism",
        relation_type=RelationType.ASSOCIATION,
        properties={"applicability": 0.8, "benefit": 0.7}
    )
    
    await kg_manager.store.add_edge(edge1)
    await kg_manager.store.add_edge(edge2)
    
    # 查询知识
    related_nodes = await kg_manager.store.get_neighbors("python_lang")
    print(f"   ✅ 知识图谱: 添加了3个节点, 2个关系, Python相关节点: {len(related_nodes)} 个")
    
    # 5. 演示强化学习能力
    print("\n5. 演示强化学习能力...")
    from xiaotie.rl.core import State, Action, Transition
    state = State(
        id="perf_opt_state",
        features=[0.5, 0.7, 0.3],
        description="性能优化状态"
    )
    
    action = Action(
        id="apply_cache",
        name="apply_cache",
        description="应用缓存机制"
    )
    
    next_state = State(
        id="perf_opt_state_next",
        features=[0.6, 0.8, 0.4],
        description="应用缓存后的状态"
    )
    
    transition = Transition(
        state=state,
        action=action,
        next_state=next_state,
        reward=0.85
    )
    
    rl_result = await rl_engine.update(transition)
    print(f"   ✅ 强化学习: 状态转换奖励 {transition.reward}, 学习更新完成")
    
    # 6. 演示规划能力
    print("\n6. 演示智能规划能力...")
    from xiaotie.planning.core import Task, PlanStep, Priority, ExecutionMode
    from datetime import timedelta
    
    step1 = PlanStep(
        id="analyze_reqs",
        description="分析性能优化需求",
        expected_outcome="明确优化目标和约束",
        estimated_duration=timedelta(minutes=15)
    )
    
    step2 = PlanStep(
        id="identify_bottlenecks",
        description="识别性能瓶颈",
        expected_outcome="定位主要性能问题",
        estimated_duration=timedelta(minutes=30),
        dependencies=["analyze_reqs"]
    )
    
    step3 = PlanStep(
        id="implement_optimizations",
        description="实施优化措施",
        expected_outcome="性能提升",
        estimated_duration=timedelta(minutes=60),
        dependencies=["identify_bottlenecks"]
    )
    
    task = Task(
        id="perf_opt_task",
        description="Python性能优化任务",
        goal="提升代码执行效率30%",
        steps=[step1, step2, step3],
        priority=Priority.HIGH,
        execution_mode=ExecutionMode.SEQUENTIAL
    )
    
    # 添加任务到管理器
    task_id = await planning_system.task_manager.create_task(
        description=task.description,
        goal=task.goal,
        priority=task.priority
    )
    
    print(f"   ✅ 规划系统: 创建任务 '{task.description}', {len(task.steps)} 个步骤")
    
    # 7. 演示上下文感知
    print("\n7. 演示上下文感知能力...")
    from xiaotie.context.core import ContextScope
    context_result = await context_manager.extract_context(
        text="关于Python性能优化的讨论，特别是缓存机制的应用",
        scope=ContextScope.CONVERSATION
    )
    
    print(f"   ✅ 上下文提取: {len(context_result.entities)} 个实体, {len(context_result.relationships)} 个关系")
    
    # 8. 演示记忆管理
    print("\n8. 演示智能记忆管理...")
    await memory_manager.add_memory(
        content="Python性能优化最佳实践包括使用缓存、优化算法、减少I/O操作",
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
        tags=["python", "optimization", "best_practices"]
    )
    
    # 检索记忆
    retrieved = await memory_manager.retrieve_memories("python optimization", top_k=5)
    print(f"   ✅ 记忆管理: 存储并检索到 {len(retrieved)} 条相关记忆")
    
    # 9. 演示反思能力
    print("\n9. 演示智能反思能力...")
    await reflection_manager.record_reflection(
        reflection_type="performance_optimization",
        content="在Python性能优化过程中，发现缓存机制是最有效的手段之一，但需要注意内存使用",
        outcome="positive",
        metadata={"domain": "python", "technique": "caching", "effectiveness": 0.8}
    )
    
    insights = await reflection_manager.get_insights(reflection_type="performance_optimization", limit=5)
    print(f"   ✅ 反思系统: 记录了反思见解，获取到 {len(insights)} 条洞察")
    
    # 10. 综合能力演示
    print("\n10. 综合能力演示...")
    print("   模拟一个复杂任务：分析并优化一个Web应用的性能")
    
    # 添加更多上下文
    web_app_context = [
        Message(role="user", content="我们有一个Python Flask Web应用，响应时间很慢"),
        Message(role="assistant", content="我建议首先分析性能瓶颈，然后针对性优化"),
    ]
    
    # 使用所有系统协同工作
    context_analysis = await context_manager.extract_context(
        text="Flask应用性能分析：响应慢、数据库查询多、无缓存机制",
        scope=context_manager.scope.SESSION
    )
    
    # 在知识图谱中查找相关信息
    kg_search_results = await kg_manager.store.search_nodes("performance optimization")
    
    # 使用决策引擎选择最佳策略
    strategies = [
        DecisionOption(
            id="caching_strategy",
            action="实施缓存策略",
            description="添加Redis缓存层",
            utility=0.85,
            probability=0.7,
            cost=0.4,
            risk=0.2
        ),
        DecisionOption(
            id="db_optimization",
            action="数据库优化",
            description="优化SQL查询和索引",
            utility=0.75,
            probability=0.8,
            cost=0.6,
            risk=0.3
        )
    ]
    
    chosen_strategy, _ = await decision_engine.make_decision(strategies, "Web应用性能优化")
    
    print(f"   分析完成 - 提取上下文实体: {len(context_analysis.entities)} 个")
    print(f"   知识图谱匹配: {len(kg_search_results)} 个相关概念")
    print(f"   决策结果: {chosen_strategy.action}")
    
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    print(f"\n🎉 认知架构演示完成！")
    print(f"⏱️ 总耗时: {total_time:.3f} 秒")
    print(f"✅ 已验证功能:")
    print(f"   - 自适应学习机制")
    print(f"   - 智能决策引擎") 
    print(f"   - 知识图谱集成")
    print(f"   - 强化学习机制")
    print(f"   - 智能规划系统")
    print(f"   - 上下文感知系统")
    print(f"   - 智能记忆管理")
    print(f"   - 反思与改进机制")


async def run_demo():
    """运行演示"""
    print("🚀 开始小铁框架 v1.1.0 认知架构演示...\n")
    
    try:
        await demo_cognitive_architecture()
    except Exception as e:
        print(f"\n❌ 演示失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_demo())