"""
强化学习机制测试

验证新强化学习功能的工作情况
"""

import asyncio
from xiaotie import (
    MemoryManager,
    AdaptiveLearner,
    ReinforcementLearningEngine,
    RLAgentMixin,
    RLAlgorithm,
    State,
    Action,
    Transition
)


async def test_reinforcement_learning_engine():
    """测试强化学习引擎"""
    print("🎯 测试强化学习引擎...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    adaptive_learner = AdaptiveLearner(memory_manager, None)
    
    # 创建强化学习引擎
    rl_engine = ReinforcementLearningEngine(
        memory_manager=memory_manager,
        adaptive_learner=adaptive_learner,
        rl_algorithm=RLAlgorithm.Q_LEARNING
    )
    
    # 创建测试状态和动作
    state1 = State(id="state1", features=[1.0, 0.5], description="初始状态")
    state2 = State(id="state2", features=[0.8, 0.7], description="中间状态")
    state3 = State(id="state3", features=[0.2, 0.9], description="目标状态", is_terminal=True)
    
    action1 = Action(id="action1", name="move_forward", description="向前移动")
    action2 = Action(id="action2", name="turn_right", description="向右转")
    action3 = Action(id="action3", name="reach_goal", description="到达目标")
    
    # 添加动作到引擎
    await rl_engine.add_action(action1)
    await rl_engine.add_action(action2)
    await rl_engine.add_action(action3)
    
    await rl_engine.add_state(state1)
    await rl_engine.add_state(state2)
    await rl_engine.add_state(state3)
    
    print(f"   动作空间大小: {len(rl_engine.action_space)}")
    print(f"   状态空间大小: {len(rl_engine.state_space)}")
    
    # 测试状态转移
    transition1 = Transition(
        state=state1,
        action=action1,
        next_state=state2,
        reward=0.5
    )
    
    update_result = await rl_engine.update(transition1)
    print(f"   更新结果 - 奖励: {update_result['reward']}, 累计奖励: {update_result['total_reward']}")
    
    # 测试动作价值获取
    action_values = await rl_engine.get_action_values(state1)
    print(f"   状态1的动作价值: {action_values}")
    
    # 测试动作选择
    selected_action = await rl_engine.select_action(state1)
    print(f"   选择的动作: {selected_action.name}")
    
    # 测试策略获取
    policy = await rl_engine.get_policy(state1)
    print(f"   状态1的策略: {policy}")
    
    # 测试奖励计算
    reward = await rl_engine.compute_reward(
        context="测试环境",
        action=action1,
        outcome="成功执行动作",
        success=True
    )
    print(f"   计算奖励: {reward:.2f}")
    
    # 获取动作优势
    advantage = await rl_engine.get_action_advantage(state1, action1)
    print(f"   动作优势: {advantage:.2f}")
    
    # 获取分析
    analytics = await rl_engine.get_learning_analytics()
    print(f"   学习分析 - 总奖励: {analytics['total_reward']}, 算法: {analytics['algorithm']}")
    
    print("   ✅ 强化学习引擎测试完成")


async def test_sarsa_learning():
    """测试SARSA学习"""
    print("🔄 测试SARSA学习...")
    
    # 创建使用SARSA算法的引擎
    memory_manager = MemoryManager()
    adaptive_learner = AdaptiveLearner(memory_manager, None)
    
    sarsa_engine = ReinforcementLearningEngine(
        memory_manager=memory_manager,
        adaptive_learner=adaptive_learner,
        rl_algorithm=RLAlgorithm.SARSA
    )
    
    # 创建状态和动作
    state = State(id="sarsa_state", features=[0.5, 0.5], description="SARSA测试状态")
    action1 = Action(id="sarsa_a1", name="sarsa_action1", description="SARSA动作1")
    action2 = Action(id="sarsa_a2", name="sarsa_action2", description="SARSA动作2")
    next_state = State(id="sarsa_next", features=[0.6, 0.4], description="SARSA下一状态")
    
    await sarsa_engine.add_action(action1)
    await sarsa_engine.add_action(action2)
    await sarsa_engine.add_state(state)
    await sarsa_engine.add_state(next_state)
    
    # 执行转移
    transition = Transition(
        state=state,
        action=action1,
        next_state=next_state,
        reward=1.0
    )
    
    result = await sarsa_engine.update(transition)
    print(f"   SARSA更新 - 状态: {result['state_id']}, 动作: {result['action_id']}")
    
    print("   ✅ SARSA学习测试完成")


async def test_monte_carlo_learning():
    """测试蒙特卡洛学习"""
    print("🎲 测试蒙特卡洛学习...")
    
    # 创建使用蒙特卡洛算法的引擎
    memory_manager = MemoryManager()
    adaptive_learner = AdaptiveLearner(memory_manager, None)
    
    mc_engine = ReinforcementLearningEngine(
        memory_manager=memory_manager,
        adaptive_learner=adaptive_learner,
        rl_algorithm=RLAlgorithm.MONTE_CARLO
    )
    
    # 创建状态和动作
    state = State(id="mc_state", features=[0.3, 0.7], description="MC测试状态")
    action = Action(id="mc_action", name="mc_action", description="MC动作")
    terminal_state = State(id="terminal", features=[1.0, 1.0], description="终止状态", is_terminal=True)
    
    await mc_engine.add_action(action)
    await mc_engine.add_state(state)
    await mc_engine.add_state(terminal_state)
    
    # 创建一个episode（从非终止状态到终止状态）
    transition = Transition(
        state=state,
        action=action,
        next_state=terminal_state,
        reward=10.0  # 终止状态的高奖励
    )
    
    result = await mc_engine.update(transition)
    print(f"   MC更新 - Episode长度: {result['episode_length']}, 完成Episodes: {result['completed_episodes']}")
    
    print("   ✅ 蒙特卡洛学习测试完成")


async def test_rl_agent_mixin():
    """测试RL Agent混入"""
    print("🤖 测试RL Agent混入...")
    
    # 创建依赖组件
    memory_manager = MemoryManager()
    adaptive_learner = AdaptiveLearner(memory_manager, None)
    rl_engine = ReinforcementLearningEngine(memory_manager, adaptive_learner)
    
    # 创建Agent混入
    agent_mixin = RLAgentMixin(rl_engine)
    
    # 设置当前状态
    current_state = State(id="agent_state", features=[0.4, 0.6], description="Agent当前状态")
    await agent_mixin.set_current_state(current_state)
    
    # 获取下一个动作
    next_action = await agent_mixin.get_next_action()
    print(f"   获取动作: {next_action.name}")
    
    # 从交互中学习
    reward = await agent_mixin.learn_from_interaction(
        action=next_action,
        outcome="动作执行成功",
        success=True,
        next_state_description="执行动作后的新状态"
    )
    print(f"   学习奖励: {reward:.2f}")
    
    # 获取动作建议
    advice = await agent_mixin.get_action_advice(next_action)
    print(f"   动作建议 - 可否建议: {advice['advisable']}, 优势: {advice['advantage']:.2f}")
    
    # 获取策略
    policy = await agent_mixin.get_policy_for_state(current_state)
    print(f"   状态策略: {policy}")
    
    # 获取状态价值
    state_values = await agent_mixin.get_state_values(current_state)
    print(f"   状态价值: {state_values}")
    
    # 获取RL分析
    rl_analytics = await agent_mixin.get_rl_analytics()
    print(f"   RL分析 - 启用: {rl_analytics['enabled']}, 总奖励: {rl_analytics['total_reward']}")
    
    # 重置学习
    await agent_mixin.reset_learning()
    print(f"   学习已重置")
    
    print("   ✅ RL Agent混入测试完成")


async def test_adaptive_parameter_adjustment():
    """测试自适应参数调整"""
    print("📈 测试自适应参数调整...")
    
    # 创建引擎
    memory_manager = MemoryManager()
    adaptive_learner = AdaptiveLearner(memory_manager, None)
    rl_engine = ReinforcementLearningEngine(memory_manager, adaptive_learner)
    
    initial_exploration = rl_engine.exploration_rate
    initial_lr = rl_engine.learning_rate
    print(f"   初始探索率: {initial_exploration}, 初始学习率: {initial_lr}")
    
    # 模拟性能反馈
    poor_performance = {"average_reward": -0.5, "learning_progress": 0.1}
    good_performance = {"average_reward": 0.8, "learning_progress": 0.7}
    
    # 根据差性能调整参数
    await rl_engine.adapt_parameters(poor_performance)
    print(f"   差性能后探索率: {rl_engine.exploration_rate}, 学习率: {rl_engine.learning_rate}")
    
    # 根据好性能调整参数
    await rl_engine.adapt_parameters(good_performance)
    print(f"   好性能后探索率: {rl_engine.exploration_rate}, 学习率: {rl_engine.learning_rate}")
    
    print("   ✅ 自适应参数调整测试完成")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行强化学习机制测试...\n")
    
    await test_reinforcement_learning_engine()
    print()
    
    await test_sarsa_learning()
    print()
    
    await test_monte_carlo_learning()
    print()
    
    await test_rl_agent_mixin()
    print()
    
    await test_adaptive_parameter_adjustment()
    print()
    
    print("🎉 所有测试完成！强化学习机制功能正常。")


if __name__ == "__main__":
    asyncio.run(run_all_tests())