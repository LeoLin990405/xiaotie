"""
智能决策引擎测试

验证新决策功能的工作情况
"""

import asyncio
from xiaotie import (
    MemoryManager, 
    ContextManager, 
    AdaptiveLearner, 
    PlanningSystem,
    DecisionEngine,
    DecisionAwareAgentMixin,
    DecisionOption,
    DecisionType,
    DecisionStrategy
)


async def test_decision_engine():
    """测试决策引擎"""
    print("🤖 测试决策引擎...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    learning_learner = AdaptiveLearner(memory_manager, None)  # ReflectionManager将在实际使用中传入
    planning_system = PlanningSystem()
    
    # 创建决策引擎
    decision_engine = DecisionEngine(
        context_manager=context_manager,
        learning_learner=learning_learner,
        memory_manager=memory_manager,
        planning_system=planning_system
    )
    
    # 创建决策选项
    option1 = DecisionOption(
        id="opt1",
        action="使用缓存优化性能",
        description="实现缓存机制以提高系统性能",
        estimated_outcome="性能提升约30%",
        utility=0.8,
        probability=0.7,
        cost=0.3,
        risk=0.2
    )
    
    option2 = DecisionOption(
        id="opt2",
        action="重构代码结构",
        description="重构代码以提高可维护性",
        estimated_outcome="可维护性提升，性能略有改善",
        utility=0.6,
        probability=0.8,
        cost=0.6,
        risk=0.4
    )
    
    option3 = DecisionOption(
        id="opt3",
        action="添加新功能",
        description="添加新功能以满足用户需求",
        estimated_outcome="用户满意度提升",
        utility=0.9,
        probability=0.5,
        cost=0.7,
        risk=0.6
    )
    
    options = [option1, option2, option3]
    
    # 做出决策
    chosen_option, analysis = await decision_engine.make_decision(
        options,
        context_description="系统性能优化需求",
        decision_type=DecisionType.PROACTIVE
    )
    
    print(f"   选择的选项: {chosen_option.action}")
    print(f"   选项效用: {chosen_option.utility}")
    print(f"   评估的选项数: {len(analysis['evaluations'])}")
    print(f"   决策ID: {analysis['decision_id']}")
    
    # 评估决策影响
    decision_id = analysis['decision_id']
    impact_result = await decision_engine.evaluate_decision_impact(
        decision_id,
        actual_outcome="性能提升了25%，用户反馈良好",
        feedback="优化效果明显，建议推广到其他模块",
        reward=0.75
    )
    
    print(f"   决策影响评估完成: 实际效用 {impact_result['realized_utility']}")
    
    # 获取决策分析
    analytics = await decision_engine.get_decision_analytics()
    print(f"   总决策数: {analytics['total_decisions']}")
    print(f"   平均效用: {analytics['average_utility']:.2f}")
    print(f"   成功率: {analytics['success_rate']:.2f}")
    
    print("   ✅ 决策引擎测试完成")


async def test_decision_policies():
    """测试不同决策策略"""
    print("📋 测试不同决策策略...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    learning_learner = AdaptiveLearner(memory_manager, None)
    
    decision_engine = DecisionEngine(context_manager, learning_learner, memory_manager)
    
    # 创建选项
    options = [
        DecisionOption(
            id="safe_opt",
            action="保守策略",
            description="采用保守的安全策略",
            estimated_outcome="安全稳定的收益",
            utility=0.6,
            probability=0.9,
            cost=0.2,
            risk=0.1
        ),
        DecisionOption(
            id="risky_opt",
            action="激进策略", 
            description="采用高风险高回报策略",
            estimated_outcome="高回报但伴随高风险",
            utility=0.9,
            probability=0.4,
            cost=0.3,
            risk=0.8
        )
    ]
    
    # 测试基于效用的策略
    chosen1, _ = await decision_engine.make_decision(
        options,
        context_description="风险厌恶场景",
        strategy=DecisionStrategy.UTILITY_BASED
    )
    print(f"   效用基础策略选择: {chosen1.action}")
    
    # 测试概率型策略
    chosen2, _ = await decision_engine.make_decision(
        options,
        context_description="概率优化场景", 
        strategy=DecisionStrategy.PROBABILISTIC
    )
    print(f"   概率型策略选择: {chosen2.action}")
    
    # 测试规则基础策略
    await decision_engine.add_decision_rule("high_risk", "safe_opt", priority=10)
    await decision_engine.add_decision_rule("opportunity", "risky_opt", priority=8)
    
    chosen3, _ = await decision_engine.make_decision(
        options,
        context_description="高风险场景",
        strategy=DecisionStrategy.RULE_BASED
    )
    print(f"   规则基础策略选择: {chosen3.action}")
    
    print("   ✅ 决策策略测试完成")


async def test_decision_aware_agent():
    """测试决策感知Agent"""
    print("🧠 测试决策感知Agent...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    learning_learner = AdaptiveLearner(memory_manager, None)
    decision_engine = DecisionEngine(context_manager, learning_learner, memory_manager)
    
    # 创建Agent混入
    agent_mixin = DecisionAwareAgentMixin(decision_engine)
    
    # 建议最佳选项
    possible_actions = [
        "优化数据库查询",
        "实现缓存机制", 
        "重构代码结构",
        "添加监控功能"
    ]
    
    best_action, confidence = await agent_mixin.suggest_best_option(
        possible_actions,
        "系统性能优化需求"
    )
    
    print(f"   建议动作: {best_action}")
    print(f"   置信度: {confidence:.2f}")
    
    # 获取决策洞察
    insights = await agent_mixin.get_decision_insights()
    print(f"   决策分析中的决策数: {insights['analytics']['total_decisions']}")
    print(f"   活跃策略: {insights['active_policy']}")
    
    # 添加决策指导方针
    await agent_mixin.add_decision_guideline(
        condition="performance_issue",
        recommended_action="optimize_database_query",
        priority=5
    )
    
    print("   ✅ 决策感知Agent测试完成")


async def test_complex_decision_scenario():
    """测试复杂决策场景"""
    print("🔄 测试复杂决策场景...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    learning_learner = AdaptiveLearner(memory_manager, None)
    decision_engine = DecisionEngine(context_manager, learning_learner, memory_manager)
    
    # 模拟复杂决策场景：产品功能优先级
    features = [
        ("用户认证系统", 0.9, 0.6, 0.8, 0.3),
        ("数据分析仪表板", 0.8, 0.7, 0.6, 0.5),
        ("移动端适配", 0.95, 0.5, 0.9, 0.7),
        ("API性能优化", 0.7, 0.8, 0.4, 0.2),
        ("错误监控系统", 0.6, 0.9, 0.3, 0.1)
    ]
    
    options = []
    for i, (name, utility, prob, cost, risk) in enumerate(features):
        option = DecisionOption(
            id=f"feature_{i}",
            action=name,
            description=f"实现{name}功能",
            estimated_outcome=f"提升用户体验和系统稳定性",
            utility=utility,
            probability=prob,
            cost=cost,
            risk=risk
        )
        options.append(option)
    
    # 做出决策
    chosen, analysis = await decision_engine.make_decision(
        options,
        context_description="产品功能优先级排序 - 需要考虑用户价值、实现难度和风险",
        decision_type=DecisionType.HIERARCHICAL
    )
    
    print(f"   优先级最高的功能: {chosen.action}")
    print(f"   功能效用: {chosen.utility}")
    print(f"   考虑了 {len(analysis['evaluations'])} 个功能选项")
    
    # 模拟执行结果
    decision_id = analysis['decision_id']
    await decision_engine.evaluate_decision_impact(
        decision_id,
        actual_outcome=f"{chosen.action}功能成功上线，用户反馈积极",
        feedback="功能实现质量高，用户满意度显著提升",
        reward=0.85
    )
    
    # 检查决策分析更新
    updated_analytics = await decision_engine.get_decision_analytics()
    print(f"   更新后总决策数: {updated_analytics['total_decisions']}")
    print(f"   更新后平均效用: {updated_analytics['average_utility']:.2f}")
    
    print("   ✅ 复杂决策场景测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行智能决策引擎测试...\n")
    
    await test_decision_engine()
    print()
    
    await test_decision_policies()
    print()
    
    await test_decision_aware_agent()
    print()
    
    await test_complex_decision_scenario()
    print()
    
    print("🎉 所有测试完成！智能决策引擎功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())