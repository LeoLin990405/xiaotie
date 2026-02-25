"""
智能决策引擎

实现基于上下文和学习经验的智能决策
"""

import asyncio
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict
import math

from ..schema import Message
from ..context.core import ContextManager, ContextType
from ..learning.core import AdaptiveLearner, LearningStrategy
from ..memory.core import MemoryManager, MemoryType
from ..planning.core import PlanningSystem, TaskManager, Task as PlanningTask
from ..reflection.core import ReflectionManager, ReflectionType


class DecisionType(Enum):
    """决策类型"""
    SEQUENTIAL = "sequential"      # 序贯决策
    PARALLEL = "parallel"         # 并行决策
    HIERARCHICAL = "hierarchical" # 层次化决策
    REACTIVE = "reactive"         # 反应式决策
    PROACTIVE = "proactive"       # 主动式决策


class DecisionStrategy(Enum):
    """决策策略"""
    RULE_BASED = "rule_based"          # 基于规则
    LEARNING_BASED = "learning_based"  # 基于学习
    UTILITY_BASED = "utility_based"    # 基于效用
    PROBABILISTIC = "probabilistic"    # 概率型
    HEURISTIC = "heuristic"            # 启发式


@dataclass
class DecisionOption:
    """决策选项"""
    id: str
    action: str
    description: str
    estimated_outcome: str
    utility: float = 0.0      # 效用值 [-1, 1]
    probability: float = 0.5  # 成功概率 [0, 1]
    cost: float = 0.0         # 执行成本 [0, 1]
    risk: float = 0.0         # 风险水平 [0, 1]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DecisionOutcome:
    """决策结果"""
    decision_id: str
    chosen_option: DecisionOption
    actual_outcome: str
    utility_realized: float
    timestamp: datetime
    context_snapshot: Dict[str, Any]
    feedback: Optional[str] = None
    reward: Optional[float] = None


class BaseDecisionPolicy(ABC):
    """决策策略基类"""
    
    @abstractmethod
    async def evaluate_options(self, options: List[DecisionOption], 
                             context: Dict[str, Any]) -> List[Tuple[DecisionOption, float]]:
        """评估选项并返回(选项, 分数)列表"""
        pass
    
    @abstractmethod
    async def select_option(self, options: List[DecisionOption], 
                          context: Dict[str, Any]) -> DecisionOption:
        """从选项中选择最佳选项"""
        pass


class UtilityBasedPolicy(BaseDecisionPolicy):
    """基于效用的决策策略"""
    
    def __init__(self, risk_tolerance: float = 0.5, exploration_rate: float = 0.1):
        self.risk_tolerance = risk_tolerance  # 风险容忍度 [0,1]
        self.exploration_rate = exploration_rate  # 探索率 [0,1]
    
    async def evaluate_options(self, options: List[DecisionOption], 
                             context: Dict[str, Any]) -> List[Tuple[DecisionOption, float]]:
        """评估选项"""
        evaluations = []
        
        for option in options:
            # 综合效用 = 基础效用 - 风险惩罚 - 成本
            base_utility = option.utility
            risk_penalty = option.risk * (1 - self.risk_tolerance)
            cost_penalty = option.cost
            
            # 调整后的效用
            adjusted_utility = base_utility - risk_penalty - cost_penalty
            
            # 如果有历史数据，加入学习因子
            historical_success_rate = context.get(f"option_{option.id}_success_rate", 0.5)
            learning_factor = 0.2
            final_score = (1 - learning_factor) * adjusted_utility + \
                         learning_factor * historical_success_rate * base_utility
            
            evaluations.append((option, final_score))
        
        return evaluations
    
    async def select_option(self, options: List[DecisionOption], 
                          context: Dict[str, Any]) -> DecisionOption:
        """选择选项"""
        if not options:
            raise ValueError("没有可选的决策选项")
        
        # 评估所有选项
        evaluations = await self.evaluate_options(options, context)
        
        # ε-贪婪策略：exploration_rate概率随机选择，其余时间选择最高分
        if random.random() < self.exploration_rate:
            # 随机选择（带权重）
            total_score = sum(max(0, eval_score) for _, eval_score in evaluations)
            if total_score > 0:
                rand_val = random.uniform(0, total_score)
                cumulative = 0
                for option, score in evaluations:
                    cumulative += max(0, score)
                    if cumulative >= rand_val:
                        return option
            # 如果权重有问题，随机选择
            return random.choice(options)
        else:
            # 选择评分最高的
            best_option, best_score = max(evaluations, key=lambda x: x[1])
            return best_option


class ProbabilisticPolicy(BaseDecisionPolicy):
    """概率型决策策略"""
    
    def __init__(self, temperature: float = 1.0):
        self.temperature = temperature  # 控制随机性程度
    
    async def evaluate_options(self, options: List[DecisionOption], 
                             context: Dict[str, Any]) -> List[Tuple[DecisionOption, float]]:
        """评估选项"""
        evaluations = []
        
        for option in options:
            # 使用概率和效用的组合
            combined_score = option.probability * option.utility
            
            # 考虑成本和风险
            penalty = option.cost * 0.3 + option.risk * 0.2
            final_score = combined_score - penalty
            
            evaluations.append((option, final_score))
        
        return evaluations
    
    async def select_option(self, options: List[DecisionOption], 
                          context: Dict[str, Any]) -> DecisionOption:
        """选择选项（使用softmax）"""
        if not options:
            raise ValueError("没有可选的决策选项")
        
        evaluations = await self.evaluate_options(options, context)
        
        # 提取分数
        scores = [score for _, score in evaluations]
        
        # Softmax选择
        if self.temperature == 0:
            # 贪心选择
            best_idx = scores.index(max(scores))
            return options[best_idx]
        
        # 计算softmax概率
        exp_scores = [math.exp(score / self.temperature) for score in scores]
        total = sum(exp_scores)
        
        if total == 0:
            # 如果所有分数都是极小值，随机选择
            return random.choice(options)
        
        probabilities = [exp_score / total for exp_score in exp_scores]
        
        # 按概率选择
        rand_val = random.random()
        cumulative_prob = 0
        for i, prob in enumerate(probabilities):
            cumulative_prob += prob
            if rand_val <= cumulative_prob:
                return options[i]
        
        # 理论上不会到达这里
        return options[-1]


class RuleBasedPolicy(BaseDecisionPolicy):
    """基于规则的决策策略"""
    
    def __init__(self):
        self.rules: List[Dict[str, Any]] = []
    
    def add_rule(self, condition: str, action_id: str, priority: int = 1):
        """添加决策规则"""
        rule = {
            "condition": condition,
            "action_id": action_id,
            "priority": priority
        }
        self.rules.append(rule)
        # 按优先级排序
        self.rules.sort(key=lambda x: x["priority"], reverse=True)
    
    async def evaluate_options(self, options: List[DecisionOption], 
                             context: Dict[str, Any]) -> List[Tuple[DecisionOption, float]]:
        """评估选项"""
        evaluations = []
        
        for option in options:
            # 检查规则匹配
            score = 0.0
            for rule in self.rules:
                if self._evaluate_condition(rule["condition"], context):
                    if rule["action_id"] == option.id:
                        score = rule["priority"] * 0.1  # 规则优先级转换为分数
                        break  # 找到匹配规则就跳出
            
            evaluations.append((option, score))
        
        return evaluations
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """评估条件"""
        # 简单的条件评估（实际应用中应该更复杂）
        try:
            # 检查条件是否在上下文中有匹配
            if "high_risk" in condition.lower() and context.get("risk_level") == "high":
                return True
            elif "urgent" in condition.lower() and context.get("urgency") == "high":
                return True
            elif "safe" in condition.lower() and context.get("risk_level") != "high":
                return True
            elif "learned" in condition.lower() and context.get("option_learned", False):
                return True
            else:
                return False
        except:
            return False
    
    async def select_option(self, options: List[DecisionOption], 
                          context: Dict[str, Any]) -> DecisionOption:
        """选择选项"""
        if not options:
            raise ValueError("没有可选的决策选项")
        
        # 按规则优先级评估
        evaluations = await self.evaluate_options(options, context)
        
        # 选择评分最高的
        if evaluations:
            best_option, best_score = max(evaluations, key=lambda x: x[1])
            if best_score > 0:  # 只有当有匹配规则时才使用规则选择
                return best_option
        
        # 如果没有匹配规则，返回第一个选项
        return options[0]


class DecisionEngine:
    """决策引擎"""
    
    def __init__(self, 
                 context_manager: ContextManager,
                 learning_learner: AdaptiveLearner,
                 memory_manager: MemoryManager,
                 planning_system: PlanningSystem = None):
        self.context_manager = context_manager
        self.learning_learner = learning_learner
        self.memory_manager = memory_manager
        self.planning_system = planning_system
        
        # 初始化不同策略
        self.policies = {
            DecisionStrategy.UTILITY_BASED: UtilityBasedPolicy(),
            DecisionStrategy.PROBABILISTIC: ProbabilisticPolicy(),
            DecisionStrategy.RULE_BASED: RuleBasedPolicy()
        }
        
        self.active_policy = DecisionStrategy.UTILITY_BASED
        self.decision_history: List[DecisionOutcome] = []
        self.option_performance: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "total_score": 0.0,
            "execution_count": 0,
            "success_count": 0,
            "average_utility": 0.0
        })
    
    async def make_decision(self, 
                          options: List[DecisionOption], 
                          context_description: str = "",
                          decision_type: DecisionType = DecisionType.SEQUENTIAL,
                          strategy: DecisionStrategy = None) -> Tuple[DecisionOption, Dict[str, Any]]:
        """做出决策"""
        if not options:
            raise ValueError("没有可选的决策选项")
        
        # 如果没有指定策略，使用激活的策略
        if strategy is None:
            strategy = self.active_policy
        
        policy = self.policies[strategy]
        
        # 获取当前上下文
        context = await self._build_context(context_description)
        
        # 评估选项
        evaluations = await policy.evaluate_options(options, context)
        
        # 选择最佳选项
        chosen_option = await policy.select_option(options, context)
        
        # 记录决策
        import uuid
        decision_id = str(uuid.uuid4())
        
        decision_outcome = DecisionOutcome(
            decision_id=decision_id,
            chosen_option=chosen_option,
            actual_outcome="决策已做出，待执行",
            utility_realized=0.0,
            timestamp=datetime.now(),
            context_snapshot=context
        )
        
        self.decision_history.append(decision_outcome)
        
        # 更新选项性能统计
        self._update_option_performance(chosen_option.id, 0.0, False)
        
        # 存储决策到记忆系统
        decision_content = f"决策: {context_description} -> 选择: {chosen_option.action} (效用: {chosen_option.utility})"
        await self.memory_manager.add_memory(
            content=decision_content,
            memory_type=MemoryType.EPISODIC,
            importance=abs(chosen_option.utility),
            tags=["decision", strategy.value, decision_type.value],
            metadata={
                "decision_id": decision_id,
                "context": context_description,
                "chosen_option": chosen_option.action,
                "strategy": strategy.value,
                "decision_type": decision_type.value
            }
        )
        
        # 返回结果和分析
        analysis = {
            "decision_id": decision_id,
            "chosen_option": chosen_option,
            "strategy_used": strategy.value,
            "evaluations": evaluations,  # 返回完整的评估结果 (opt, score)
            "context_considered": list(context.keys()),
            "alternative_options_count": len(options) - 1
        }
        
        return chosen_option, analysis
    
    async def evaluate_decision_impact(self, decision_id: str, 
                                    actual_outcome: str, 
                                    feedback: str = "",
                                    reward: float = 0.0) -> Dict[str, Any]:
        """评估决策影响"""
        # 找到对应的决策
        decision = None
        for dec in self.decision_history:
            if dec.decision_id == decision_id:
                decision = dec
                break
        
        if not decision:
            raise ValueError(f"未找到决策ID: {decision_id}")
        
        # 计算实际效用
        if reward != 0.0:
            realized_utility = reward
        else:
            # 根据反馈计算效用
            positive_words = ["好", "成功", "正确", "满意", "有效"]
            negative_words = ["坏", "失败", "错误", "不满意", "无效"]
            
            pos_count = sum(1 for word in positive_words if word in feedback.lower())
            neg_count = sum(1 for word in negative_words if word in feedback.lower())
            
            if pos_count > neg_count:
                realized_utility = min(1.0, 0.2 * pos_count)
            elif neg_count > pos_count:
                realized_utility = max(-1.0, -0.2 * neg_count)
            else:
                realized_utility = 0.1  # 中性
        
        # 更新决策结果
        decision.actual_outcome = actual_outcome
        decision.utility_realized = realized_utility
        decision.feedback = feedback
        decision.reward = realized_utility
        
        # 更新选项性能
        option_id = decision.chosen_option.id
        self._update_option_performance(option_id, realized_utility, realized_utility > 0)
        
        # 添加学习经验
        await self.learning_learner.add_experience(
            input_context=decision.context_snapshot.get("description", ""),
            action_taken=decision.chosen_option.action,
            outcome=actual_outcome,
            reward=realized_utility,
            metadata={
                "decision_id": decision_id,
                "feedback": feedback,
                "decision_context": decision.context_snapshot
            }
        )
        
        return {
            "decision_id": decision_id,
            "realized_utility": realized_utility,
            "performance_updated": True,
            "learning_recorded": True
        }
    
    def _update_option_performance(self, option_id: str, utility: float, success: bool):
        """更新选项性能统计"""
        perf = self.option_performance[option_id]
        perf["total_score"] += utility
        perf["execution_count"] += 1
        if success:
            perf["success_count"] += 1
        perf["average_utility"] = perf["total_score"] / perf["execution_count"]
    
    async def _build_context(self, description: str) -> Dict[str, Any]:
        """构建决策上下文"""
        context = {
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "options_count": 0,
            "risk_level": "medium",
            "urgency": "normal",
            "available_resources": 1.0,
            "historical_success_rate": 0.5
        }
        
        # 从上下文管理器获取信息
        relevant_contexts = await self.context_manager.get_relevant_context(description, top_k=3)
        if relevant_contexts:
            context["relevant_contexts"] = [ctx.id for ctx in relevant_contexts]
            context["context_entities"] = []
            for ctx in relevant_contexts:
                context["context_entities"].extend([e.name for e in ctx.entities])
        
        # 从决策历史获取信息
        if self.decision_history:
            recent_decisions = self.decision_history[-5:]  # 最近5个决策
            success_rate = sum(1 for dec in recent_decisions if dec.utility_realized > 0) / len(recent_decisions)
            context["recent_success_rate"] = success_rate
            context["historical_success_rate"] = success_rate
        
        # 从选项性能获取信息
        # 这有当描述中包含选项ID时才添加性能信息
        context["option_learned"] = False  # 默认值
        
        return context
    
    async def adapt_strategy(self, context_description: str = "") -> DecisionStrategy:
        """根据上下文自适应选择最佳策略"""
        # 基于历史性能选择策略
        strategy_performance = {}
        
        for strategy, policy in self.policies.items():
            # 这里应该基于历史数据计算每种策略的性能
            # 简单实现：随机选择或使用默认策略
            # 在实际实现中，应该分析历史决策的效果
            if strategy == DecisionStrategy.UTILITY_BASED:
                performance_score = 0.8
            elif strategy == DecisionStrategy.PROBABILISTIC:
                performance_score = 0.7
            else:
                performance_score = 0.6
            
            strategy_performance[strategy.value] = performance_score
        
        # 选择性能最好的策略
        best_strategy_str = max(strategy_performance, key=strategy_performance.get)
        
        for strategy in DecisionStrategy:
            if strategy.value == best_strategy_str:
                self.active_policy = strategy
                break
        
        return self.active_policy
    
    async def get_decision_analytics(self) -> Dict[str, Any]:
        """获取决策分析"""
        if not self.decision_history:
            return {
                "total_decisions": 0,
                "average_utility": 0.0,
                "success_rate": 0.0,
                "strategy_distribution": {},
                "option_performance": {}
            }
        
        total_decisions = len(self.decision_history)
        total_utility = sum(dec.utility_realized for dec in self.decision_history)
        avg_utility = total_utility / total_decisions
        
        successful_decisions = sum(1 for dec in self.decision_history if dec.utility_realized > 0)
        success_rate = successful_decisions / total_decisions
        
        # 策略分布
        strategy_counts = defaultdict(int)
        for dec in self.decision_history:
            strategy_counts[dec.chosen_option.metadata.get("strategy", "unknown")] += 1
        
        return {
            "total_decisions": total_decisions,
            "average_utility": avg_utility,
            "success_rate": success_rate,
            "strategy_distribution": dict(strategy_counts),
            "option_performance": dict(self.option_performance),
            "recent_decisions": [
                {
                    "option": dec.chosen_option.action,
                    "utility": dec.utility_realized,
                    "timestamp": dec.timestamp.isoformat()
                }
                for dec in self.decision_history[-10:]  # 最近10个决策
            ]
        }
    
    async def add_decision_rule(self, condition: str, action_id: str, priority: int = 1):
        """为规则策略添加决策规则"""
        if isinstance(self.policies[DecisionStrategy.RULE_BASED], RuleBasedPolicy):
            self.policies[DecisionStrategy.RULE_BASED].add_rule(condition, action_id, priority)


class DecisionAwareAgentMixin:
    """决策感知Agent混入类"""
    
    def __init__(self, decision_engine: DecisionEngine):
        self.decision_engine = decision_engine
        self.decision_making_enabled = True
    
    async def enable_decision_making(self):
        """启用决策制定"""
        self.decision_making_enabled = True
    
    async def disable_decision_making(self):
        """禁用决策制定"""
        self.decision_making_enabled = False
    
    async def make_decision_with_context(self, 
                                       options: List[DecisionOption],
                                       context_description: str = "",
                                       decision_type: DecisionType = DecisionType.SEQUENTIAL) -> Tuple[DecisionOption, Dict[str, Any]]:
        """在上下文中做决策"""
        if not self.decision_making_enabled:
            # 如果决策制定被禁用，返回第一个选项
            return options[0], {"disabled": True}
        
        # 自适应选择策略
        await self.decision_engine.adapt_strategy(context_description)
        
        # 做出决策
        return await self.decision_engine.make_decision(
            options, context_description, decision_type
        )
    
    async def evaluate_action_impact(self, action_taken: str, 
                                   outcome: str, 
                                   feedback: str = "",
                                   reward: float = 0.0) -> Optional[str]:
        """评估动作影响并尝试匹配决策ID"""
        # 在决策历史中查找最近的匹配动作
        for decision in reversed(self.decision_engine.decision_history[-10:]):  # 检查最近10个决策
            if decision.chosen_option.action == action_taken:
                await self.decision_engine.evaluate_decision_impact(
                    decision.decision_id, outcome, feedback, reward
                )
                return decision.decision_id
        
        return None  # 没有找到匹配的决策
    
    async def get_decision_insights(self) -> Dict[str, Any]:
        """获取决策洞察"""
        analytics = await self.decision_engine.get_decision_analytics()
        
        return {
            "analytics": analytics,
            "enabled": self.decision_making_enabled,
            "active_policy": self.decision_engine.active_policy.value,
            "recent_decisions_count": len(self.decision_engine.decision_history[-5:])
        }
    
    async def suggest_best_option(self, possible_actions: List[str], 
                                context: str = "") -> Tuple[str, float]:
        """根据上下文建议最佳选项"""
        if not self.decision_making_enabled:
            return possible_actions[0] if possible_actions else "default", 0.5
        
        # 创建决策选项
        options = []
        for i, action in enumerate(possible_actions):
            option = DecisionOption(
                id=f"opt_{i}",
                action=action,
                description=f"执行动作: {action}",
                estimated_outcome=f"可能产生正面结果",
                utility=random.uniform(0.3, 0.8),  # 随机初始效用
                probability=random.uniform(0.5, 0.9),  # 随机初始概率
                cost=random.uniform(0.1, 0.4),  # 随机初始成本
                risk=random.uniform(0.1, 0.3)   # 随机初始风险
            )
            options.append(option)
        
        # 做出决策
        chosen_option, analysis = await self.make_decision_with_context(
            options, context
        )
        
        # 返回动作和置信度
        # 置信度可以基于评估分数
        evaluations = analysis["evaluations"]
        scores = [score for _, score in evaluations]  # 修正：只提取分数
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        
        if max_score == min_score:
            confidence = 0.5
        else:
            # 找到被选中选项的分数
            chosen_score = None
            for opt, score in evaluations:
                if opt.id == chosen_option.id:
                    chosen_score = score
                    break
            if chosen_score is not None:
                confidence = (chosen_score - min_score) / (max_score - min_score)
            else:
                confidence = 0.5  # 默认置信度
        
        return chosen_option.action, confidence
    
    async def add_decision_guideline(self, condition: str, recommended_action: str, priority: int = 1):
        """添加决策指导方针"""
        await self.decision_engine.add_decision_rule(condition, recommended_action, priority)