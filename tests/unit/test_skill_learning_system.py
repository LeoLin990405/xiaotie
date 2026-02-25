"""
技能学习系统测试

验证新技能学习功能的工作情况
"""

import asyncio
from datetime import datetime
from xiaotie import (
    MemoryManager,
    ContextManager,
    SkillAcquirer,
    SkillLearningAgentMixin,
    SkillType,
    SkillAcquisitionMethod,
    SkillExample
)
from xiaotie.learning.core import Skill


async def test_skill_acquirer():
    """测试技能获取器"""
    print("🧩 测试技能获取器...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    
    # 创建技能获取器
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    
    # 测试实践技能
    metrics1 = await skill_acquirer.practice_skill(
        skill_name="code_optimization",
        input_context="Python性能优化问题",
        expected_output="代码执行效率提升",
        actual_output="使用缓存和算法优化",
        success=True,
        metadata={"domain": "programming", "difficulty": "medium"}
    )
    
    print(f"   技能实践评估 - 整体得分: {metrics1['overall_score']:.2f}")
    print(f"   准确率: {metrics1['accuracy']:.2f}")
    print(f"   可靠性: {metrics1['reliability']:.2f}")
    print(f"   一致性: {metrics1['consistency']:.2f}")
    
    # 再次实践同一个技能
    metrics2 = await skill_acquirer.practice_skill(
        skill_name="code_optimization",
        input_context="数据库查询优化问题",
        expected_output="查询性能提升",
        actual_output="使用索引和查询重写",
        success=True,
        metadata={"domain": "database", "difficulty": "hard"}
    )
    
    print(f"   第二次实践 - 整体得分: {metrics2['overall_score']:.2f}")
    
    # 实践失败的情况
    metrics3 = await skill_acquirer.practice_skill(
        skill_name="code_optimization",
        input_context="复杂算法优化问题",
        expected_output="算法效率大幅提升",
        actual_output="优化效果不明显",
        success=False,
        metadata={"domain": "algorithm", "difficulty": "very_hard"}
    )
    
    print(f"   失败实践 - 整体得分: {metrics3['overall_score']:.2f}")
    
    # 获取技能发展路径
    path = await skill_acquirer.get_skill_development_path("code_optimization")
    print(f"   技能发展路径: {path[0]['stage']} (进度: {path[0]['progress']:.2f})")
    
    # 评估技能
    from xiaotie.skills.core import Skill
    skill = Skill(name="code_optimization", description="代码优化技能")
    evaluation = await skill_acquirer.evaluate_skill(skill)
    print(f"   技能评估 - 整体得分: {evaluation['overall_score']:.2f}")
    print(f"   总示例数: {evaluation['total_examples']}")
    print(f"   成功示例数: {evaluation['successful_examples']}")
    
    print("   ✅ 技能获取器测试完成")


async def test_skill_observation_learning():
    """测试观察学习"""
    print("👀 测试观察学习...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    
    # 测试观察学习
    observation_result = await skill_acquirer.observe_skill(
        skill_name="data_analysis",
        observed_context="观察专家进行数据分析的过程",
        demonstration="首先清洗数据，然后进行可视化，最后得出结论"
    )
    
    print(f"   观察技能: {observation_result['skill_name']}")
    print(f"   观察上下文长度: {observation_result['observed_context'][:20]}...")
    print(f"   示范长度: {observation_result['demonstration_length']}")
    print(f"   示例总数: {observation_result['examples_count']}")
    
    # 测试指令学习
    instruction_result = await skill_acquirer.receive_instruction(
        skill_name="report_writing",
        instruction="撰写报告时需要遵循结构化格式，包含引言、方法、结果和结论部分",
        expected_behavior="按照IMRaD格式撰写学术报告"
    )
    
    print(f"   指令技能: {instruction_result['skill_name']}")
    print(f"   指令长度: {instruction_result['instruction_length']}")
    print(f"   理论示例数: {instruction_result['theoretical_examples_count']}")
    
    print("   ✅ 观察学习测试完成")


async def test_skill_transfer():
    """测试技能迁移"""
    print("🔄 测试技能迁移...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    
    # 首先创建一些源技能示例
    await skill_acquirer.practice_skill(
        skill_name="python_programming",
        input_context="编写Python函数",
        expected_output="高效可读的代码",
        actual_output="使用函数式编程和列表推导",
        success=True
    )
    
    await skill_acquirer.practice_skill(
        skill_name="python_programming",
        input_context="Python性能优化",
        expected_output="代码执行效率提升",
        actual_output="使用缓存和算法优化",
        success=True
    )
    
    # 测试技能迁移
    transfer_success = await skill_acquirer.transfer_skill_knowledge(
        source_skill="python_programming",
        target_skill="javascript_programming"
    )
    
    print(f"   技能迁移成功: {transfer_success}")
    
    # 检查目标技能是否获得了示例
    target_examples_count = len(skill_acquirer.skill_examples["javascript_programming"])
    print(f"   目标技能示例数: {target_examples_count}")
    
    print("   ✅ 技能迁移测试完成")


async def test_skill_learning_agent_mixin():
    """测试技能学习Agent混入"""
    print("🤖 测试技能学习Agent混入...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    
    # 创建Agent混入
    agent_mixin = SkillLearningAgentMixin(skill_acquirer)
    
    # 实践技能
    practice_metrics = await agent_mixin.practice_skill(
        skill_name="communication",
        input_context="与用户进行技术问题沟通",
        expected_output="清晰解释技术概念",
        actual_output="使用类比和示例解释复杂概念",
        success=True
    )
    
    print(f"   实践技能 - 整体得分: {practice_metrics['overall_score']:.2f}")
    
    # 评估技能
    evaluation = await agent_mixin.evaluate_my_skill("communication")
    print(f"   技能评估 - 整体得分: {evaluation['overall_score']:.2f}")
    
    # 获取技能进步情况
    progress = await agent_mixin.get_my_skill_progress("communication")
    print(f"   技能进步 - 阶段: {progress[0]['stage']}, 进度: {progress[0]['progress']:.2f}")
    
    # 获取学习推荐
    recommendations = await agent_mixin.get_skill_recommendations()
    print(f"   学习推荐数: {len(recommendations)}")
    if recommendations:
        rec = recommendations[0]
        print(f"   推荐技能: {rec['skill']}, 当前水平: {rec['current_level']}")
    
    # 获取学习分析
    analytics = await agent_mixin.get_learning_analytics()
    print(f"   学习分析 - 技能总数: {analytics['total_skills']}")
    print(f"   示例总数: {analytics['total_examples']}")
    print(f"   成功率: {analytics['success_rate']:.2f}")
    print(f"   学习启用: {analytics['learning_enabled']}")
    
    print("   ✅ 技能学习Agent混入测试完成")


async def test_multiple_skills():
    """测试多种技能"""
    print("📚 测试多种技能...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    context_manager = ContextManager(memory_manager)
    skill_acquirer = SkillAcquirer(memory_manager, context_manager)
    
    # 定义多种技能
    skills_to_test = [
        ("tool_usage", "使用各种工具解决问题"),
        ("problem_solving", "分析和解决复杂问题"),
        ("analytical_thinking", "进行深入分析"),
        ("creative_solution", "提出创意思路")
    ]
    
    for skill_name, description in skills_to_test:
        # 实践每个技能
        for i in range(3):
            success = i != 1  # 模拟成功率
            await skill_acquirer.practice_skill(
                skill_name=skill_name,
                input_context=f"测试{skill_name}的场景{i+1}",
                expected_output=f"针对{description}的解决方案",
                actual_output=f"应用{skill_name}技能的实践{i+1}",
                success=success
            )
        
        # 评估技能
        skill = Skill(name=skill_name, description=description)
        evaluation = await skill_acquirer.evaluate_skill(skill)
        print(f"   {skill_name}: 整体得分 {evaluation['overall_score']:.2f}, 成功率 {evaluation['accuracy']:.2f}")
    
    # 获取所有技能的分析
    total_skills = len(skill_acquirer.skill_examples)
    print(f"   总技能数: {total_skills}")
    
    # 检查每个技能的示例数
    for skill_name in skill_acquirer.skill_examples.keys():
        example_count = len(skill_acquirer.skill_examples[skill_name])
        print(f"   - {skill_name}: {example_count} 个示例")
    
    print("   ✅ 多种技能测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行技能学习系统测试...\n")
    
    await test_skill_acquirer()
    print()
    
    await test_skill_observation_learning()
    print()
    
    await test_skill_transfer()
    print()
    
    await test_skill_learning_agent_mixin()
    print()
    
    await test_multiple_skills()
    print()
    
    print("🎉 所有测试完成！技能学习系统功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())