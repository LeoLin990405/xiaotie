"""
自适应学习系统测试

验证新学习功能的工作情况
"""

import asyncio
from xiaotie import MemoryManager, ReflectionManager, AdaptiveLearner, LearningAgentMixin, LearningStrategy


async def test_adaptive_learning():
    """测试自适应学习功能"""
    print("🧠 测试自适应学习功能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    reflection_manager = ReflectionManager(memory_manager)
    
    # 创建自适应学习器
    learner = AdaptiveLearner(memory_manager, reflection_manager)
    
    # 添加一些学习经验
    await learner.add_experience(
        input_context="用户询问Python性能优化",
        action_taken="建议使用缓存和算法优化",
        outcome="用户表示满意并采纳建议",
        reward=0.8,
        metadata={"domain": "programming", "difficulty": "medium"}
    )
    
    await learner.add_experience(
        input_context="用户询问数据库查询优化",
        action_taken="建议建立索引和查询重写",
        outcome="建议有效，查询速度提升50%",
        reward=0.9,
        metadata={"domain": "database", "difficulty": "hard"}
    )
    
    await learner.add_experience(
        input_context="用户询问前端性能问题",
        action_taken="建议资源压缩和懒加载",
        outcome="用户反馈解决方案不够详细",
        reward=-0.3,
        metadata={"domain": "frontend", "difficulty": "easy"}
    )
    
    print("   ✅ 学习经验已添加")
    
    # 预测下一个动作
    action, confidence, strategy = await learner.predict_next_action("用户询问Python性能优化")
    print(f"   预测动作: {action}, 置信度: {confidence:.2f}, 策略: {strategy.value}")
    
    # 评估性能
    performance = await learner.evaluate_performance()
    print(f"   性能评估完成，总经验数: {performance['total_experiences']}")
    
    # 获取技能总结
    skills_summary = await learner.get_skills_summary()
    print(f"   技能总数: {skills_summary['total_skills']}, 平均熟练度: {skills_summary['average_proficiency']:.2f}")
    
    # 获取建议
    recommendations = await learner.get_recommendations()
    print(f"   学习建议数: {len(recommendations)}")
    
    print("   ✅ 自适应学习功能测试完成")


async def test_learning_agent_mixin():
    """测试学习型Agent混入功能"""
    print("🧩 测试学习型Agent混入功能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    reflection_manager = ReflectionManager(memory_manager)
    learner = AdaptiveLearner(memory_manager, reflection_manager)
    
    # 创建混入实例
    mixin = LearningAgentMixin(learner)
    
    # 从交互中学习
    await mixin.learn_from_interaction(
        user_input="如何优化Python代码性能？",
        agent_response="建议使用缓存机制、优化算法复杂度、使用合适的数据结构",
        environment_feedback="用户表示建议很有帮助",
        reward=0.7
    )
    
    print("   ✅ 交互学习完成")
    
    # 获取任务建议
    advice, confidence = await mixin.get_advice_for_task("Python性能优化")
    print(f"   任务建议: {advice}, 置信度: {confidence:.2f}")
    
    # 获取学习状态
    status = await mixin.get_learning_status()
    print(f"   学习状态获取完成，性能指标数: {len(status['performance']['algorithm_performance'])}")
    
    print("   ✅ 学习型Agent混入功能测试完成")


async def test_different_learning_strategies():
    """测试不同学习策略"""
    print("📋 测试不同学习策略...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    reflection_manager = ReflectionManager(memory_manager)
    learner = AdaptiveLearner(memory_manager, reflection_manager)
    
    # 测试强化学习策略
    learner.active_strategy = LearningStrategy.REINFORCEMENT_LEARNING
    await learner.add_experience(
        input_context="RL测试 - 简单数学问题",
        action_taken="直接给出答案",
        outcome="答案正确，用户满意",
        reward=0.9
    )
    
    print("   强化学习策略测试完成")
    
    # 测试监督学习策略
    learner.active_strategy = LearningStrategy.SUPERVISED_LEARNING
    await learner.add_experience(
        input_context="SL测试 - 代码审查",
        action_taken="指出潜在bug并提供修复建议",
        outcome="修复建议被采纳",
        reward=0.8
    )
    
    print("   监督学习策略测试完成")
    
    # 测试无监督学习策略
    learner.active_strategy = LearningStrategy.UNSUPERVISED_LEARNING
    await learner.add_experience(
        input_context="UL测试 - 模式识别",
        action_taken="识别出重复代码模式",
        outcome="模式识别准确",
        reward=0.7
    )
    
    print("   无监督学习策略测试完成")
    
    # 评估整体性能
    performance = await learner.evaluate_performance()
    print(f"   整体性能评估完成")
    
    print("   ✅ 不同学习策略测试完成")


async def test_skill_management():
    """测试技能管理功能"""
    print("🤔 测试技能管理功能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    reflection_manager = ReflectionManager(memory_manager)
    learner = AdaptiveLearner(memory_manager, reflection_manager)
    
    # 通过学习经验自动创建和更新技能
    await learner.add_experience(
        input_context="Python性能优化咨询",
        action_taken="code_optimization",
        outcome="成功优化代码性能",
        reward=0.9
    )
    
    await learner.add_experience(
        input_context="数据库查询优化咨询", 
        action_taken="database_optimization",
        outcome="查询效率提升",
        reward=0.85
    )
    
    await learner.add_experience(
        input_context="Python性能优化咨询",
        action_taken="code_optimization", 
        outcome="再次成功",
        reward=0.95
    )
    
    # 获取技能总结
    skills_summary = await learner.get_skills_summary()
    print(f"   技能总数: {skills_summary['total_skills']}")
    print(f"   平均熟练度: {skills_summary['average_proficiency']:.2f}")
    print(f"   最常使用技能: {[s[0] for s in skills_summary['most_used']]}")
    print(f"   最高熟练度技能: {[s[0] for s in skills_summary['highest_rated']]}")
    
    print("   ✅ 技能管理功能测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行自适应学习系统测试...\n")
    
    await test_adaptive_learning()
    print()
    
    await test_learning_agent_mixin()
    print()
    
    await test_different_learning_strategies()
    print()
    
    await test_skill_management()
    print()
    
    print("🎉 所有测试完成！自适应学习系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())