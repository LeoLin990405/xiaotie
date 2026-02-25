"""
小铁框架综合验证测试

验证所有功能模块协同工作的完整性
"""

import asyncio
from datetime import datetime

from xiaotie import (
    # 核心组件
    Agent,
    AgentBuilder,
    
    # 记忆系统
    MemoryManager,
    ConversationMemory,
    
    # 上下文系统
    ContextManager,
    ContextAwareAgentMixin,
    ContextWindowManager,
    
    # 决策系统
    DecisionEngine,
    DecisionAwareAgentMixin,
    DecisionOption,
    DecisionType,
    
    # 学习系统
    AdaptiveLearner,
    LearningAgentMixin,
    SkillLearningAgentMixin,
    
    # 多Agent协作
    MultiAgentSystem,
    CoordinatorAgent,
    ExpertAgent,
    
    # 多模态
    MultimodalContentManager,
    MultimodalAgentMixin,
    ModalityType,
    MediaContent,
    
    # 强化学习
    ReinforcementLearningEngine,
    RLAgentMixin,
    State,
    Action,
    
    # 知识图谱
    KnowledgeGraphManager,
    KnowledgeGraphAgentMixin,
    
    # 规划系统
    PlanningSystem,
    
    # 反思机制
    ReflectionManager
)

# 从子模块导入特定工具
from xiaotie.tools import PythonTool, BashTool


async def test_full_integration():
    """测试所有系统的完整集成"""
    print("🚀 开始小铁框架完整集成测试...\n")
    
    # 1. 创建核心组件
    print("1. 初始化核心组件...")
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    reflection_manager = ReflectionManager(memory_manager)
    planning_system = PlanningSystem()
    
    print("   ✅ 核心组件初始化完成")
    
    # 2. 初始化学习系统
    print("2. 初始化学习系统...")
    adaptive_learner = AdaptiveLearner(memory_manager, reflection_manager)
    print("   ✅ 学习系统初始化完成")
    
    # 3. 初始化决策系统
    print("3. 初始化决策系统...")
    decision_engine = DecisionEngine(
        context_manager=context_manager,
        learning_learner=adaptive_learner,
        memory_manager=memory_manager,
        planning_system=planning_system
    )
    print("   ✅ 决策系统初始化完成")
    
    # 4. 初始化上下文窗口管理
    print("4. 初始化上下文窗口管理...")
    context_window_manager = ContextWindowManager(
        memory_manager=memory_manager,
        context_manager=context_manager
    )
    print("   ✅ 上下文窗口管理初始化完成")
    
    # 5. 初始化多模态系统
    print("5. 初始化多模态系统...")
    multimodal_manager = MultimodalContentManager()
    print("   ✅ 多模态系统初始化完成")
    
    # 6. 初始化强化学习系统
    print("6. 初始化强化学习系统...")
    rl_engine = ReinforcementLearningEngine(
        memory_manager=memory_manager,
        adaptive_learner=adaptive_learner
    )
    print("   ✅ 强化学习系统初始化完成")
    
    # 7. 初始化知识图谱系统
    print("7. 初始化知识图谱系统...")
    from xiaotie.kg.core import NetworkXKnowledgeGraphStore as KnowledgeGraphStore
    kg_store = KnowledgeGraphStore()
    kg_manager = KnowledgeGraphManager(
        store=kg_store,
        memory_manager=memory_manager,
        context_manager=context_manager
    )
    print("   ✅ 知识图谱系统初始化完成")
    
    # 8. 创建Agent混入实例
    print("8. 创建Agent混入实例...")
    context_aware_mixin = ContextAwareAgentMixin(context_manager)  # 传入context_manager而不是context_window_manager
    decision_aware_mixin = DecisionAwareAgentMixin(decision_engine)
    learning_mixin = LearningAgentMixin(adaptive_learner)
    
    # 创建技能获取器并用于技能学习混入
    from xiaotie.skills.core import SkillAcquirer
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    skill_learning_mixin = SkillLearningAgentMixin(skill_acquirer)
    
    multimodal_mixin = MultimodalAgentMixin(multimodal_manager)
    rl_mixin = RLAgentMixin(rl_engine)
    kg_mixin = KnowledgeGraphAgentMixin(kg_manager)
    print("   ✅ Agent混入实例创建完成")
    
    # 9. 测试多Agent协作
    print("9. 测试多Agent协作...")
    multi_agent_system = MultiAgentSystem()
    coordinator = CoordinatorAgent("main-coordinator")
    coding_expert = ExpertAgent("coding-expert", "programming")
    
    await multi_agent_system.add_agent(coordinator)
    await multi_agent_system.add_agent(coding_expert)
    
    # 创建任务
    from xiaotie.multi_agent.coordinator import Task as MultiAgentTask
    task = MultiAgentTask(
        id="integration-task",
        description="综合测试任务",
        metadata={"priority": "high", "domain": "integration"}
    )
    
    coordinator.task_queue.append(task)
    await coordinator.distribute_tasks()
    print("   ✅ 多Agent协作测试完成")
    
    # 10. 测试决策系统
    print("10. 测试决策系统...")
    options = [
        DecisionOption(
            id="opt1",
            action="analyze_code",
            description="分析代码性能",
            estimated_outcome="识别性能瓶颈",
            utility=0.8,
            probability=0.7,
            cost=0.2,
            risk=0.1
        ),
        DecisionOption(
            id="opt2",
            action="refactor_code",
            description="重构代码结构",
            estimated_outcome="提高可维护性",
            utility=0.7,
            probability=0.8,
            cost=0.5,
            risk=0.3
        )
    ]
    
    chosen_option, analysis = await decision_engine.make_decision(
        options,
        context_description="性能优化决策",
        decision_type=DecisionType.SEQUENTIAL
    )
    print(f"   决策结果: {chosen_option.action} (效用: {chosen_option.utility})")
    print("   ✅ 决策系统测试完成")
    
    # 11. 测试学习系统
    print("11. 测试学习系统...")
    await learning_mixin.learn_from_interaction(
        user_input="如何优化Python代码性能？",
        agent_response="建议使用缓存和算法优化",
        environment_feedback="用户采纳了建议",
        reward=0.8
    )
    print("   ✅ 学习系统测试完成")
    
    # 12. 测试技能学习
    print("12. 测试技能学习...")
    skill_metrics = await skill_learning_mixin.practice_skill(
        skill_name="code_optimization",
        input_context="Python性能优化问题",
        expected_output="性能提升",
        actual_output="使用缓存和算法优化",
        success=True
    )
    print(f"   技能学习效果: 整体得分 {skill_metrics['overall_score']:.2f}")
    print("   ✅ 技能学习测试完成")
    
    # 13. 测试强化学习
    print("13. 测试强化学习...")
    rl_state = State(id="test_state", features=[0.5, 0.5], description="测试状态")
    rl_action = Action(id="test_action", name="test_action", description="测试动作")
    
    await rl_mixin.set_current_state(rl_state)
    next_action = await rl_mixin.get_next_action()
    reward = await rl_mixin.learn_from_interaction(
        action=next_action,
        outcome="成功执行动作",
        success=True
    )
    print(f"   强化学习奖励: {reward:.2f}")
    print("   ✅ 强化学习测试完成")
    
    # 14. 测试知识图谱
    print("14. 测试知识图谱...")
    from xiaotie.schema import Message
    message = Message(role="user", content="Machine learning algorithms are powerful tools.")
    kg_update_result = await kg_manager.update_from_message(message)
    print(f"   知识图谱更新: {kg_update_result['entities_created']} 个实体, {kg_update_result['relations_created']} 个关系")
    print("   ✅ 知识图谱测试完成")
    
    # 15. 测试上下文管理
    print("15. 测试上下文管理...")
    from xiaotie.context.core import ContextScope, ContextType
    context_result = await context_aware_mixin.process_with_context(
        input_text="关于Python性能优化的讨论",
        context_type=ContextType.CONVERSATIONAL,
        scope=ContextScope.SESSION
    )
    print(f"   上下文处理: {context_result['extracted_context']['entities_count'] if 'extracted_context' in context_result else 0} 个实体")
    print("   ✅ 上下文管理测试完成")
    
    # 16. 获取综合分析
    print("16. 获取综合分析...")
    decision_analytics = await decision_engine.get_decision_analytics()
    learning_status = await learning_mixin.get_learning_status()
    kg_analytics = await kg_manager.get_knowledge_analytics()
    
    print(f"   决策分析 - 总决策数: {decision_analytics['total_decisions']}, 成功率: {decision_analytics['success_rate']:.2f}")
    print(f"   学习状态 - 平均奖励: {learning_status.get('performance', {}).get('average_reward', 0):.2f}")
    print(f"   知识图谱 - 节点数: {kg_analytics['graph_statistics']['node_count']}, 边数: {kg_analytics['graph_statistics']['edge_count']}")
    
    print("   ✅ 综合分析完成")
    
    print("\n🎉 小铁框架完整集成测试成功！")
    print("✅ 所有系统模块协同工作正常")
    print("✅ 功能完整性验证通过")
    print("✅ 各互操作性测试通过")


async def run_comprehensive_test():
    """运行综合测试"""
    start_time = datetime.now()
    
    try:
        await test_full_integration()
    except Exception as e:
        print(f"\n❌ 综合测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n⏱️ 测试总耗时: {duration.total_seconds():.2f} 秒")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())