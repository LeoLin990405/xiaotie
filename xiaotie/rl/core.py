"""
强化学习机制

实现基于奖励的强化学习算法，使Agent能够通过与环境互动来学习最优策略
"""

import asyncio
import numpy as np
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict, deque
import pickle
import json

from ..schema import Message
from ..memory.core import MemoryManager, MemoryType
from ..learning.core import AdaptiveLearner
from ..decision.core import DecisionEngine, DecisionType


class RLAlgorithm(Enum):
    """强化学习算法类型"""
    Q_LEARNING = "q_learning"
    SARSA = "sarsa"
    DQN = "dqn"  # Deep Q-Network
    POLICY_GRADIENT = "policy_gradient"
    ACTOR_CRITIC = "actor_critic"
    MONTE_CARLO = "monte_carlo"


class StateRepresentation(Enum):
    """状态表示方法"""
    TABULAR = "tabular"  # 表格形式
    FUNCTION_APPROXIMATION = "function_approximation"  # 函数逼近
    DEEP_LEARNING = "deep_learning"  # 深度学习


@dataclass
class State:
    """状态定义"""
    id: str
    features: List[float]  # 状态特征向量
    description: str = ""
    is_terminal: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Action:
    """动作定义"""
    id: str
    name: str
    description: str = ""
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class Transition:
    """状态转移"""
    state: State
    action: Action
    next_state: State
    reward: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BaseReinforcementLearner(ABC):
    """强化学习器基类"""
    
    @abstractmethod
    async def update(self, transition: Transition) -> Dict[str, Any]:
        """根据状态转移更新学习模型"""
        pass
    
    @abstractmethod
    async def get_action_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        pass
    
    @abstractmethod
    async def select_action(self, state: State, epsilon: float = 0.1) -> Action:
        """根据ε-贪婪策略选择动作"""
        pass
    
    @abstractmethod
    async def get_policy(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的概率分布"""
        pass


class QTableLearner(BaseReinforcementLearner):
    """Q表学习器（适用于离散状态和动作空间）"""
    
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9, initial_q_value: float = 0.0):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.initial_q_value = initial_q_value
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: self.initial_q_value))
        self.visit_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.action_history: List[Transition] = []
    
    async def update(self, transition: Transition) -> Dict[str, Any]:
        """Q学习更新"""
        state_id = transition.state.id
        action_id = transition.action.id
        next_state_id = transition.next_state.id
        reward = transition.reward
        
        # 更新访问计数
        self.visit_counts[state_id][action_id] += 1
        
        # 获取当前Q值
        current_q = self.q_table[state_id][action_id]
        
        # 如果下一状态是终止状态，则未来奖励为0
        if transition.next_state.is_terminal:
            max_next_q = 0
        else:
            # 获取下一状态的最大Q值
            next_q_values = self.q_table[next_state_id]
            if next_q_values:
                max_next_q = max(next_q_values.values())
            else:
                max_next_q = 0
        
        # Q学习更新规则
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        self.q_table[state_id][action_id] = new_q
        
        # 记录转移
        self.action_history.append(transition)
        
        return {
            "state_id": state_id,
            "action_id": action_id,
            "old_q_value": current_q,
            "new_q_value": new_q,
            "reward": reward,
            "visit_count": self.visit_counts[state_id][action_id]
        }
    
    async def get_action_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        state_id = state.id
        return dict(self.q_table[state_id])
    
    async def select_action(self, state: State, epsilon: float = 0.1) -> Action:
        """ε-贪婪策略选择动作"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            # 如果没有可用的动作，返回一个默认动作
            return Action(id="default", name="default_action", description="默认动作")
        
        # ε-贪婪策略
        if random.random() < epsilon:
            # 随机选择动作
            action_id = random.choice(list(action_values.keys()))
        else:
            # 选择价值最高的动作
            action_id = max(action_values, key=action_values.get)
        
        # 在实际应用中，我们需要根据action_id还原Action对象
        # 这里简化处理，返回一个同名的Action对象
        return Action(id=action_id, name=action_id, description=f"动作 {action_id}")
    
    async def get_policy(self, state: State) -> Dict[str, float]:
        """获取确定性策略（贪心策略）"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            return {}
        
        # 返回价值最高的动作的策略（概率为1，其余为0）
        best_action = max(action_values, key=action_values.get)
        policy = {aid: 0.0 for aid in action_values.keys()}
        policy[best_action] = 1.0
        
        return policy


class SARSALearner(BaseReinforcementLearner):
    """SARSA学习器（在线策略学习）"""
    
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9, initial_q_value: float = 0.0):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.initial_q_value = initial_q_value
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(lambda: self.initial_q_value))
        self.action_history: List[Transition] = []
    
    async def update(self, transition: Transition) -> Dict[str, Any]:
        """SARSA更新（在线策略）"""
        state_id = transition.state.id
        action_id = transition.action.id
        next_state_id = transition.next_state.id
        next_action_id = transition.action.id  # SARSA使用实际执行的下一个动作
        reward = transition.reward
        
        # 获取当前Q值
        current_q = self.q_table[state_id][action_id]
        
        # 获取下一个状态-动作对的Q值
        next_q = self.q_table[next_state_id][next_action_id]
        
        # SARSA更新规则
        td_target = reward + self.discount_factor * next_q
        td_error = td_target - current_q
        new_q = current_q + self.learning_rate * td_error
        self.q_table[state_id][action_id] = new_q
        
        # 记录转移
        self.action_history.append(transition)
        
        return {
            "state_id": state_id,
            "action_id": action_id,
            "old_q_value": current_q,
            "new_q_value": new_q,
            "td_error": td_error,
            "reward": reward
        }
    
    async def get_action_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        state_id = state.id
        return dict(self.q_table[state_id])
    
    async def select_action(self, state: State, epsilon: float = 0.1) -> Action:
        """ε-贪婪策略选择动作"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            return Action(id="default", name="default_action", description="默认动作")
        
        if random.random() < epsilon:
            action_id = random.choice(list(action_values.keys()))
        else:
            action_id = max(action_values, key=action_values.get)
        
        return Action(id=action_id, name=action_id, description=f"动作 {action_id}")
    
    async def get_policy(self, state: State) -> Dict[str, float]:
        """获取策略"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            return {}
        
        best_action = max(action_values, key=action_values.get)
        policy = {aid: 0.0 for aid in action_values.keys()}
        policy[best_action] = 1.0
        
        return policy


class MonteCarloLearner(BaseReinforcementLearner):
    """蒙特卡洛学习器（需要完整episode才能更新）"""
    
    def __init__(self, discount_factor: float = 0.9):
        self.discount_factor = discount_factor
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.returns: Dict[Tuple[str, str], List[float]] = defaultdict(list)  # 状态-动作对的回报列表
        self.episode_transitions: List[Transition] = []  # 当前episode的转移
        self.completed_episodes: List[List[Transition]] = []  # 完成的episodes
    
    async def update(self, transition: Transition) -> Dict[str, Any]:
        """记录转移，只有在episode结束时才会更新Q值"""
        self.episode_transitions.append(transition)
        
        # 如果下一状态是终止状态，说明episode结束了
        if transition.next_state.is_terminal:
            await self._update_episode_returns()
            self.completed_episodes.append(self.episode_transitions[:])
            self.episode_transitions.clear()
        
        return {
            "episode_length": len(self.episode_transitions),
            "completed_episodes": len(self.completed_episodes),
            "transition_recorded": True
        }
    
    async def _update_episode_returns(self):
        """更新episode中所有状态-动作对的回报"""
        # 从后往前计算累积回报
        G = 0.0  # 累积回报
        visited_state_actions = set()
        
        for i in range(len(self.episode_transitions) - 1, -1, -1):
            transition = self.episode_transitions[i]
            G = self.discount_factor * G + transition.reward
            
            state_action = (transition.state.id, transition.action.id)
            
            # 首次访问MC：只更新episode中首次出现的状态-动作对
            if state_action not in visited_state_actions:
                self.returns[state_action].append(G)
                
                # 更新Q值（平均回报）
                self.q_table[transition.state.id][transition.action.id] = \
                    np.mean(self.returns[state_action])
                
                visited_state_actions.add(state_action)
    
    async def get_action_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        state_id = state.id
        return dict(self.q_table[state_id])
    
    async def select_action(self, state: State, epsilon: float = 0.1) -> Action:
        """ε-贪婪策略选择动作"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            return Action(id="default", name="default_action", description="默认动作")
        
        if random.random() < epsilon:
            action_id = random.choice(list(action_values.keys()))
        else:
            action_id = max(action_values, key=action_values.get)
        
        return Action(id=action_id, name=action_id, description=f"动作 {action_id}")
    
    async def get_policy(self, state: State) -> Dict[str, float]:
        """获取策略"""
        state_id = state.id
        action_values = self.q_table[state_id]
        
        if not action_values:
            return {}
        
        best_action = max(action_values, key=action_values.get)
        policy = {aid: 0.0 for aid in action_values.keys()}
        policy[best_action] = 1.0
        
        return policy


class ReinforcementLearningEngine:
    """强化学习引擎"""
    
    def __init__(self, 
                 memory_manager: MemoryManager,
                 adaptive_learner: AdaptiveLearner,
                 rl_algorithm: RLAlgorithm = RLAlgorithm.Q_LEARNING):
        self.memory_manager = memory_manager
        self.adaptive_learner = adaptive_learner
        self.rl_algorithm = rl_algorithm
        
        # 学习参数（必须在创建学习器之前设置）
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.1
        
        # 初始化学习器
        self.learner = self._create_learner(rl_algorithm)
        
        # 动作和状态空间
        self.action_space: Dict[str, Action] = {}
        self.state_space: Dict[str, State] = {}
        
        # 性能指标
        self.total_reward = 0.0
        self.episode_count = 0
        self.step_count = 0
        
        # 经验回放缓冲区
        self.experience_buffer = deque(maxlen=10000)
    
    def _create_learner(self, algorithm: RLAlgorithm) -> BaseReinforcementLearner:
        """创建学习器"""
        if algorithm == RLAlgorithm.Q_LEARNING:
            return QTableLearner(learning_rate=self.learning_rate, discount_factor=self.discount_factor)
        elif algorithm == RLAlgorithm.SARSA:
            return SARSALearner(learning_rate=self.learning_rate, discount_factor=self.discount_factor)
        elif algorithm == RLAlgorithm.MONTE_CARLO:
            return MonteCarloLearner(discount_factor=self.discount_factor)
        else:
            # 默认使用Q学习
            return QTableLearner(learning_rate=self.learning_rate, discount_factor=self.discount_factor)
    
    async def add_action(self, action: Action):
        """添加动作到动作空间"""
        self.action_space[action.id] = action
    
    async def add_state(self, state: State):
        """添加状态到状态空间"""
        self.state_space[state.id] = state
    
    async def update(self, transition: Transition) -> Dict[str, Any]:
        """更新学习模型"""
        # 更新学习器
        update_result = await self.learner.update(transition)
        
        # 更新性能指标
        self.total_reward += transition.reward
        self.step_count += 1
        
        # 存储经验到缓冲区
        self.experience_buffer.append(transition)
        
        # 存储到记忆系统
        experience_content = f"RL经验: 状态{transition.state.id} -> 动作{transition.action.id} -> 状态{transition.next_state.id}, 奖励: {transition.reward}"
        await self.memory_manager.add_memory(
            content=experience_content,
            memory_type=MemoryType.EPISODIC,
            importance=abs(transition.reward),  # 奖励绝对值作为重要性
            tags=["reinforcement_learning", "experience", self.rl_algorithm.value],
            metadata={
                "state_id": transition.state.id,
                "action_id": transition.action.id,
                "next_state_id": transition.next_state.id,
                "reward": transition.reward,
                "timestamp": transition.timestamp.isoformat()
            }
        )
        
        return {
            **update_result,
            "total_reward": self.total_reward,
            "step_count": self.step_count,
            "experience_buffer_size": len(self.experience_buffer)
        }
    
    async def get_action_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        return await self.learner.get_action_values(state)
    
    async def select_action(self, state: State, exploration_override: Optional[float] = None) -> Action:
        """选择动作"""
        epsilon = exploration_override if exploration_override is not None else self.exploration_rate
        return await self.learner.select_action(state, epsilon)
    
    async def get_policy(self, state: State) -> Dict[str, float]:
        """获取策略"""
        return await self.learner.get_policy(state)
    
    async def get_action_advantage(self, state: State, action: Action) -> float:
        """获取动作优势（价值相对于平均价值的优势）"""
        action_values = await self.get_action_values(state)
        
        if not action_values:
            return 0.0
        
        action_value = action_values.get(action.id, 0.0)
        avg_value = np.mean(list(action_values.values()))
        
        return action_value - avg_value
    
    async def compute_reward(self, 
                           context: str, 
                           action: Action, 
                           outcome: str, 
                           success: bool) -> float:
        """计算奖励"""
        # 基础奖励
        base_reward = 1.0 if success else -1.0
        
        # 根据结果质量调整奖励
        positive_indicators = ["成功", "正确", "好", "有效", "满意", "改进", "优化", "解决"]
        negative_indicators = ["失败", "错误", "差", "无效", "不满", "恶化", "问题", "错误"]
        
        pos_count = sum(1 for indicator in positive_indicators if indicator in outcome)
        neg_count = sum(1 for indicator in negative_indicators if indicator in outcome)
        
        quality_bonus = (pos_count - neg_count) * 0.2
        
        # 根据动作选择稀有性调整奖励（鼓励探索）
        action_values = await self.get_action_values(State(id="temp", features=[]))
        if action_values and len(action_values) > 1:
            # 计算该动作的相对稀有性（基于Q值）
            sorted_values = sorted(action_values.values())
            if sorted_values:
                min_val, max_val = sorted_values[0], sorted_values[-1]
                if max_val != min_val:
                    action_rank = list(action_values.values()).index(action_values.get(action.id, 0))
                    exploration_bonus = (len(sorted_values) - action_rank) * 0.1  # 选择不太常用动作的奖励
                else:
                    exploration_bonus = 0.1
            else:
                exploration_bonus = 0.1
        else:
            exploration_bonus = 0.1
        
        total_reward = base_reward + quality_bonus + exploration_bonus
        
        # 限制奖励范围
        total_reward = max(-2.0, min(2.0, total_reward))
        
        return total_reward
    
    async def get_learning_analytics(self) -> Dict[str, Any]:
        """获取学习分析"""
        return {
            "total_reward": self.total_reward,
            "episode_count": self.episode_count,
            "step_count": self.step_count,
            "average_reward_per_step": self.total_reward / self.step_count if self.step_count > 0 else 0,
            "experience_buffer_size": len(self.experience_buffer),
            "action_space_size": len(self.action_space),
            "state_space_size": len(self.state_space),
            "algorithm": self.rl_algorithm.value,
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor
        }
    
    async def adapt_parameters(self, performance_feedback: Dict[str, float]):
        """根据性能反馈调整参数"""
        avg_reward = performance_feedback.get("average_reward", 0)
        
        # 根据平均奖励调整探索率
        if avg_reward < 0:
            # 表现不佳，增加探索
            self.exploration_rate = min(0.5, self.exploration_rate + 0.05)
        elif avg_reward > 0.5:
            # 表现良好，减少探索
            self.exploration_rate = max(0.05, self.exploration_rate - 0.02)
        
        # 根据学习进度调整学习率
        learning_progress = performance_feedback.get("learning_progress", 0)
        if learning_progress < 0.3:
            # 学习缓慢，增加学习率
            self.learning_rate = min(0.5, self.learning_rate + 0.02)
        else:
            # 学习稳定，适当降低学习率
            self.learning_rate = max(0.05, self.learning_rate - 0.01)
    
    async def get_best_action_sequence(self, start_state: State, max_steps: int = 5) -> List[Action]:
        """获取从起始状态开始的最佳动作序列"""
        sequence = []
        current_state = start_state
        
        for _ in range(max_steps):
            # 使用贪心策略选择动作（不进行探索）
            action = await self.learner.select_action(current_state, epsilon=0.0)
            sequence.append(action)
            
            # 这里需要一个状态转移模型来预测下一个状态
            # 在实际应用中，这可能需要环境模型或模拟器
            # 简化实现：返回当前状态
            break  # 为了避免无限循环，在没有真实环境模型的情况下提前退出
        
        return sequence
    
    async def reset(self):
        """重置学习引擎"""
        self.learner = self._create_learner(self.rl_algorithm)
        self.action_space.clear()
        self.state_space.clear()
        self.total_reward = 0.0
        self.episode_count = 0
        self.step_count = 0
        self.experience_buffer.clear()


class RLAgentMixin:
    """强化学习Agent混入类"""
    
    def __init__(self, rl_engine: ReinforcementLearningEngine):
        self.rl_engine = rl_engine
        self.rl_enabled = True
        self.current_state: Optional[State] = None
    
    async def enable_rl(self):
        """启用强化学习"""
        self.rl_enabled = True
    
    async def disable_rl(self):
        """禁用强化学习"""
        self.rl_enabled = False
    
    async def set_current_state(self, state: State):
        """设置当前状态"""
        self.current_state = state
    
    async def get_next_action(self, exploration_override: Optional[float] = None) -> Action:
        """获取下一个动作"""
        if not self.rl_enabled or self.current_state is None:
            # 如果RL未启用或没有当前状态，返回默认动作
            return Action(id="default", name="default_action", description="默认动作")
        
        return await self.rl_engine.select_action(self.current_state, exploration_override)
    
    async def learn_from_interaction(self, 
                                   action: Action, 
                                   outcome: str, 
                                   success: bool,
                                   next_state_description: str = "") -> float:
        """从交互中学习"""
        if not self.rl_enabled or self.current_state is None:
            return 0.0  # 未启用RL，返回零奖励
        
        # 计算奖励
        reward = await self.rl_engine.compute_reward(
            context=self.current_state.description,
            action=action,
            outcome=outcome,
            success=success
        )
        
        # 创建下一状态（简化实现）
        next_state = State(
            id=f"state_{hash(next_state_description)}",
            features=[float(abs(hash(next_state_description)) % 1000) / 1000],  # 简化的特征向量
            description=next_state_description or f"Result of action {action.name}"
        )
        
        # 创建转移
        transition = Transition(
            state=self.current_state,
            action=action,
            next_state=next_state,
            reward=reward
        )
        
        # 更新学习引擎
        update_result = await self.rl_engine.update(transition)
        
        # 更新当前状态
        self.current_state = next_state
        
        return reward
    
    async def get_action_advice(self, action: Action) -> Dict[str, Any]:
        """获取动作建议"""
        if not self.rl_enabled or self.current_state is None:
            return {"advisable": True, "reason": "RL disabled or no current state", "advantage": 0.0}
        
        advantage = await self.rl_engine.get_action_advantage(self.current_state, action)
        
        if advantage > 0.5:
            advisable = True
            reason = "高价值动作，建议执行"
        elif advantage > 0:
            advisable = True
            reason = "中等价值动作，可以执行"
        elif advantage > -0.5:
            advisable = False
            reason = "低价值动作，谨慎执行"
        else:
            advisable = False
            reason = "负价值动作，不建议执行"
        
        return {
            "advisable": advisable,
            "reason": reason,
            "advantage": advantage,
            "current_state_id": self.current_state.id
        }
    
    async def get_rl_analytics(self) -> Dict[str, Any]:
        """获取强化学习分析"""
        analytics = await self.rl_engine.get_learning_analytics()
        return {
            **analytics,
            "enabled": self.rl_enabled,
            "has_current_state": self.current_state is not None,
            "current_state_id": self.current_state.id if self.current_state else None
        }
    
    async def adapt_to_feedback(self, feedback: Dict[str, float]):
        """根据反馈调整参数"""
        await self.rl_engine.adapt_parameters(feedback)
    
    async def get_policy_for_state(self, state: State) -> Dict[str, float]:
        """获取特定状态的策略"""
        return await self.rl_engine.get_policy(state)
    
    async def get_state_values(self, state: State) -> Dict[str, float]:
        """获取状态下各动作的价值"""
        return await self.rl_engine.get_action_values(state)
    
    async def reset_learning(self):
        """重置学习"""
        await self.rl_engine.reset()
        self.current_state = None