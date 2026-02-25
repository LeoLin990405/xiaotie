"""
自适应学习机制

实现Agent的持续学习和自我改进能力
"""

import asyncio
import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum
import math

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from ..memory.core import MemoryManager, MemoryType
from ..reflection.core import ReflectionManager, ReflectionType
from ..schema import Message


class LearningStrategy(Enum):
    """学习策略类型"""
    REINFORCEMENT_LEARNING = "reinforcement_learning"  # 强化学习
    SUPERVISED_LEARNING = "supervised_learning"      # 监督学习
    UNSUPERVISED_LEARNING = "unsupervised_learning"   # 无监督学习
    FEDERATED_LEARNING = "federated_learning"        # 联邦学习
    ONLINE_LEARNING = "online_learning"              # 在线学习


@dataclass
class LearningExperience:
    """学习经验"""
    id: str
    input_context: str
    action_taken: str
    outcome: str
    reward: float  # 奖励值，范围通常在[-1, 1]
    timestamp: datetime
    metadata: Dict[str, Any]
    strategy: LearningStrategy


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    proficiency: float = 0.0  # 熟练度 0-1
    usage_count: int = 0
    success_count: int = 0
    last_used: Optional[datetime] = None
    learned_from: List[str] = None  # 从哪些经验中学到的
    
    def __post_init__(self):
        if self.learned_from is None:
            self.learned_from = []


class BaseLearningAlgorithm(ABC):
    """学习算法基类"""
    
    @abstractmethod
    async def update(self, experience: LearningExperience) -> Dict[str, Any]:
        """根据经验更新模型"""
        pass
    
    @abstractmethod
    async def predict(self, context: str) -> Tuple[str, float]:
        """预测最佳动作及置信度"""
        pass
    
    @abstractmethod
    async def evaluate_performance(self) -> Dict[str, float]:
        """评估性能"""
        pass


class QLearningAlgorithm(BaseLearningAlgorithm):
    """Q学习算法实现"""
    
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9, epsilon: float = 0.1):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon  # 探索率
        self.q_table: Dict[str, Dict[str, float]] = {}  # Q表: state -> action -> value
        self.action_space: List[str] = []  # 可能的动作空间
        self.performance_history: List[Dict[str, float]] = []
    
    async def update(self, experience: LearningExperience) -> Dict[str, Any]:
        """更新Q表"""
        state = self._hash_context(experience.input_context)
        action = experience.action_taken
        reward = experience.reward
        
        # 确保状态在Q表中存在
        if state not in self.q_table:
            self.q_table[state] = {}
        
        # 确保动作在状态中存在
        if action not in self.q_table[state]:
            self.q_table[state][action] = 0.0
        
        # Q学习更新公式: Q(s,a) = Q(s,a) + α[r + γmax(Q(s',a')) - Q(s,a)]
        # 这里简化为直接更新，实际应用中需要考虑下一个状态
        current_q = self.q_table[state][action]
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_table[state][action] = new_q
        
        # 记录性能
        self.performance_history.append({
            "timestamp": experience.timestamp,
            "reward": reward,
            "state": state,
            "action": action
        })
        
        return {
            "updated_state": state,
            "updated_action": action,
            "old_value": current_q,
            "new_value": new_q
        }
    
    async def predict(self, context: str) -> Tuple[str, float]:
        """预测最佳动作"""
        state = self._hash_context(context)
        
        if state not in self.q_table:
            # 如果状态未见过，随机选择一个动作（探索）
            if self.action_space:
                import random
                action = random.choice(self.action_space)
                return action, 0.5  # 随机选择的置信度较低
            else:
                return "default_action", 0.1
        
        # ε-贪婪策略：epsilon概率随机探索，(1-epsilon)概率选择最优
        import random as _random
        if _random.random() < self.epsilon:
            # 探索：随机选择动作
            import random
            action = random.choice(list(self.q_table[state].keys()))
            return action, 0.3  # 探索行为的置信度较低
        
        # 利用：选择Q值最高的动作
        action_values = self.q_table[state]
        best_action = max(action_values, key=action_values.get)
        best_value = action_values[best_action]
        
        # 标准化置信度
        max_q = max(action_values.values())
        min_q = min(action_values.values())
        if max_q == min_q:
            confidence = 0.5
        else:
            confidence = (best_value - min_q) / (max_q - min_q)
        
        return best_action, confidence
    
    async def evaluate_performance(self) -> Dict[str, float]:
        """评估性能"""
        if not self.performance_history:
            return {"average_reward": 0.0, "total_experiences": 0, "convergence": 0.0}
        
        rewards = [exp["reward"] for exp in self.performance_history[-100:]]  # 最近100次经验
        avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
        
        # 计算收敛性（奖励波动程度）
        if len(rewards) > 1:
            variance = sum((r - avg_reward) ** 2 for r in rewards) / len(rewards)
            convergence = max(0.0, 1.0 - variance)  # 方差越小，收敛性越好
        else:
            convergence = 0.0
        
        return {
            "average_reward": avg_reward,
            "total_experiences": len(self.performance_history),
            "convergence": convergence,
            "latest_rewards": rewards[-10:] if len(rewards) >= 10 else rewards
        }
    
    def _hash_context(self, context: str) -> str:
        """将上下文转换为状态标识符"""
        import hashlib
        # 使用前100个字符创建哈希，避免过长的上下文
        context_short = context[:100] if len(context) > 100 else context
        return hashlib.md5(context_short.encode()).hexdigest()


class SupervisedLearningAlgorithm(BaseLearningAlgorithm):
    """监督学习算法实现（用于模式识别和分类）"""
    
    def __init__(self):
        self.patterns: Dict[str, List[Dict[str, Any]]] = {}  # 识别的模式
        self.classifications: Dict[str, str] = {}  # 分类结果
        self.accuracy_history: List[float] = []
    
    async def update(self, experience: LearningExperience) -> Dict[str, Any]:
        """根据经验更新模式识别"""
        # 提取上下文特征
        features = self._extract_features(experience.input_context)
        category = self._categorize_outcome(experience.outcome)
        
        # 将经验归类到相应模式
        if category not in self.patterns:
            self.patterns[category] = []
        
        pattern_entry = {
            "features": features,
            "action": experience.action_taken,
            "outcome": experience.outcome,
            "reward": experience.reward,
            "timestamp": experience.timestamp
        }
        
        self.patterns[category].append(pattern_entry)
        
        # 更新分类
        context_hash = self._hash_context(experience.input_context)
        self.classifications[context_hash] = category
        
        return {
            "category": category,
            "features": features,
            "pattern_count": len(self.patterns[category])
        }
    
    async def predict(self, context: str) -> Tuple[str, float]:
        """预测最可能的输出"""
        features = self._extract_features(context)
        
        # 寻找最相似的模式
        best_match = None
        best_similarity = -1
        
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                similarity = self._calculate_similarity(features, pattern["features"])
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = pattern
        
        if best_match:
            # 基于相似度返回最可能的动作
            return best_match["action"], min(best_similarity, 1.0)
        else:
            # 没有匹配模式时返回默认动作
            return "default", 0.1
    
    async def evaluate_performance(self) -> Dict[str, float]:
        """评估监督学习性能"""
        if not self.accuracy_history:
            return {"average_accuracy": 0.0, "total_classifications": 0}
        
        avg_accuracy = sum(self.accuracy_history) / len(self.accuracy_history)
        return {
            "average_accuracy": avg_accuracy,
            "total_classifications": len(self.accuracy_history),
            "pattern_categories": len(self.patterns)
        }
    
    def _extract_features(self, text: str) -> List[str]:
        """提取文本特征"""
        # 简化的特征提取：关键词提取
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        # 返回最常见的10个词根
        from collections import Counter
        word_counts = Counter(words)
        return [word for word, count in word_counts.most_common(10)]
    
    def _categorize_outcome(self, outcome: str) -> str:
        """对结果进行分类"""
        if "成功" in outcome or "完成" in outcome or "正确" in outcome:
            return "positive"
        elif "失败" in outcome or "错误" in outcome or "问题" in outcome:
            return "negative"
        else:
            return "neutral"
    
    def _calculate_similarity(self, features1: List[str], features2: List[str]) -> float:
        """计算两个特征集合的相似度"""
        if not features1 or not features2:
            return 0.0
        
        set1 = set(features1)
        set2 = set(features2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _hash_context(self, context: str) -> str:
        """将上下文转换为哈希值"""
        import hashlib
        return hashlib.md5(context.encode()).hexdigest()


class UnsupervisedLearningAlgorithm(BaseLearningAlgorithm):
    """无监督学习算法实现（用于聚类和模式发现）"""
    
    def __init__(self, cluster_count: int = 5):
        self.cluster_count = cluster_count
        self.clusters: List[List[Dict[str, Any]]] = [[] for _ in range(cluster_count)]
        self.cluster_centers: List[List[float]] = [[0.0] * 10 for _ in range(cluster_count)]  # 假设10维特征
        self.feature_history: List[List[float]] = []
    
    async def update(self, experience: LearningExperience) -> Dict[str, Any]:
        """更新聚类"""
        features = self._vectorize_context(experience.input_context)
        
        # 将特征向量添加到历史记录
        self.feature_history.append(features)
        
        # 简单的K-means聚类更新
        cluster_assignments = []
        for feat_vec in self.feature_history[-50:]:  # 只使用最近50个特征向量
            distances = [self._euclidean_distance(feat_vec, center) for center in self.cluster_centers]
            closest_cluster = distances.index(min(distances))
            cluster_assignments.append(closest_cluster)
        
        # 更新聚类中心
        for i in range(self.cluster_count):
            cluster_points = [self.feature_history[j] for j, assignment in enumerate(cluster_assignments) if assignment == i]
            if cluster_points:
                # 计算新中心
                new_center = [sum(dim) / len(dim) for dim in zip(*cluster_points)]
                self.cluster_centers[i] = new_center
        
        # 将当前经验分配给最近的聚类
        distances = [self._euclidean_distance(features, center) for center in self.cluster_centers]
        assigned_cluster = distances.index(min(distances))
        
        # 添加到聚类
        cluster_entry = {
            "experience_id": experience.id,
            "features": features,
            "action": experience.action_taken,
            "outcome": experience.outcome,
            "timestamp": experience.timestamp
        }
        self.clusters[assigned_cluster].append(cluster_entry)
        
        return {
            "assigned_cluster": assigned_cluster,
            "distance_to_center": min(distances),
            "cluster_size": len(self.clusters[assigned_cluster])
        }
    
    async def predict(self, context: str) -> Tuple[str, float]:
        """基于聚类预测"""
        features = self._vectorize_context(context)
        
        # 找到最近的聚类
        distances = [self._euclidean_distance(features, center) for center in self.cluster_centers]
        closest_cluster_idx = distances.index(min(distances))
        closest_cluster = self.clusters[closest_cluster_idx]
        
        if closest_cluster:
            # 从聚类中选择最常见的动作
            from collections import Counter
            actions = [entry["action"] for entry in closest_cluster]
            action_counts = Counter(actions)
            most_common_action = action_counts.most_common(1)[0][0]
            
            # 计算置信度（基于聚类密度和相似度）
            max_dist = max(distances) if distances else 1.0
            confidence = 1.0 - (min(distances) / max_dist) if max_dist > 0 else 0.5
            
            return most_common_action, confidence
        else:
            return "default", 0.1
    
    async def evaluate_performance(self) -> Dict[str, float]:
        """评估聚类性能"""
        # 计算聚类的紧密度和分离度
        if not self.feature_history:
            return {"cohesion": 0.0, "separation": 0.0, "total_clusters": 0}
        
        total_cohesion = 0.0
        inter_cluster_distances = []
        
        for i, cluster in enumerate(self.clusters):
            if cluster:
                # 计算聚类内部的平均距离（紧密度）
                cluster_features = [entry["features"] for entry in cluster]
                if len(cluster_features) > 1:
                    cohesion_sum = 0.0
                    for j, feat1 in enumerate(cluster_features):
                        for k, feat2 in enumerate(cluster_features):
                            if j != k:
                                cohesion_sum += self._euclidean_distance(feat1, feat2)
                    avg_cohesion = cohesion_sum / (len(cluster_features) * (len(cluster_features) - 1)) if len(cluster_features) > 1 else 0
                    total_cohesion += avg_cohesion
        
        avg_cohesion = total_cohesion / len([c for c in self.clusters if c]) if any(self.clusters) else 0
        cohesion_score = 1.0 / (1.0 + avg_cohesion) if avg_cohesion > 0 else 1.0  # 紧密度越高，得分越低
        
        return {
            "cohesion": cohesion_score,
            "total_clusters": len([c for c in self.clusters if c]),
            "avg_cluster_size": (sum(len(c) for c in self.clusters) / len(self.clusters)) if self.clusters else 0
        }
    
    def _vectorize_context(self, context: str) -> List[float]:
        """将上下文转换为数值向量"""
        # 简化的向量化：基于字符频率
        import hashlib
        # 使用固定长度的向量表示
        vector = [0.0] * 10
        if context:
            hash_obj = hashlib.md5(context.encode())
            hex_dig = hash_obj.hexdigest()
            # 将十六进制字符串转换为浮点数
            for i in range(min(10, len(hex_dig))):
                vector[i] = int(hex_dig[i], 16) / 15.0  # 归一化到[0,1]
        return vector
    
    def _euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """计算欧几里得距离"""
        if len(vec1) != len(vec2):
            return float('inf')
        
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))


class AdaptiveLearner:
    """自适应学习器"""
    
    def __init__(self, memory_manager: MemoryManager, reflection_manager: ReflectionManager):
        self.memory_manager = memory_manager
        self.reflection_manager = reflection_manager
        
        # 初始化不同的学习算法
        self.learning_algorithms = {
            LearningStrategy.REINFORCEMENT_LEARNING: QLearningAlgorithm(),
            LearningStrategy.SUPERVISED_LEARNING: SupervisedLearningAlgorithm(),
            LearningStrategy.UNSUPERVISED_LEARNING: UnsupervisedLearningAlgorithm()
        }
        
        self.active_strategy = LearningStrategy.REINFORCEMENT_LEARNING
        self.skill_inventory: Dict[str, Skill] = {}
        self.learning_goals: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, List[float]] = {
            "reward": [],
            "accuracy": [],
            "efficiency": []
        }
    
    async def add_experience(self, input_context: str, action_taken: str, 
                           outcome: str, reward: float, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加学习经验"""
        import uuid
        from datetime import datetime
        
        experience = LearningExperience(
            id=str(uuid.uuid4()),
            input_context=input_context,
            action_taken=action_taken,
            outcome=outcome,
            reward=reward,
            timestamp=datetime.now(),
            metadata=metadata or {},
            strategy=self.active_strategy
        )
        
        # 更新当前激活的学习算法
        algorithm = self.learning_algorithms[self.active_strategy]
        update_result = await algorithm.update(experience)
        
        # 更新技能熟练度
        await self._update_skill_proficiency(action_taken, reward)
        
        # 存储经验到记忆系统
        experience_content = f"经验: {input_context} -> {action_taken} -> {outcome} (奖励: {reward})"
        await self.memory_manager.add_memory(
            content=experience_content,
            memory_type=MemoryType.EPISODIC,
            importance=min(max(reward, 0), 1),  # 将奖励值规范化到[0,1]作为重要性
            tags=["learning_experience", self.active_strategy.value],
            metadata={
                "experience_id": experience.id,
                "input_context": input_context,
                "action_taken": action_taken,
                "outcome": outcome,
                "reward": reward
            }
        )
        
        # 记录性能指标
        self.performance_metrics["reward"].append(reward)
        
        return {
            "experience_id": experience.id,
            "algorithm_update": update_result,
            "skill_updates": [action_taken],  # 实际上可能更新了技能
            "stored_in_memory": True
        }
    
    async def predict_next_action(self, current_context: str) -> Tuple[str, float, LearningStrategy]:
        """预测下一个最佳动作"""
        predictions = {}
        
        # 从所有算法获取预测
        for strategy, algorithm in self.learning_algorithms.items():
            try:
                action, confidence = await algorithm.predict(current_context)
                predictions[strategy] = (action, confidence)
            except Exception as e:
                print(f"算法 {strategy} 预测失败: {e}")
                predictions[strategy] = ("default", 0.1)
        
        # 选择置信度最高的预测
        best_strategy = None
        best_action = "default"
        best_confidence = 0.0
        
        for strategy, (action, confidence) in predictions.items():
            if confidence > best_confidence:
                best_strategy = strategy
                best_action = action
                best_confidence = confidence
        
        # 更新激活的策略
        if best_strategy:
            self.active_strategy = best_strategy
        
        return best_action, best_confidence, self.active_strategy
    
    async def evaluate_performance(self) -> Dict[str, Any]:
        """评估整体学习性能"""
        performance = {}
        
        # 获取每个算法的性能
        for strategy, algorithm in self.learning_algorithms.items():
            try:
                perf = await algorithm.evaluate_performance()
                performance[strategy.value] = perf
            except Exception as e:
                print(f"算法 {strategy} 性能评估失败: {e}")
                performance[strategy.value] = {"error": str(e)}
        
        # 计算整体指标
        _rewards = self.performance_metrics["reward"]
        avg_reward = (sum(_rewards) / len(_rewards)) if _rewards else 0.0
        
        return {
            "algorithm_performance": performance,
            "overall_average_reward": float(avg_reward),
            "total_experiences": len(self.performance_metrics["reward"]),
            "active_strategy": self.active_strategy.value,
            "skill_count": len(self.skill_inventory),
            "learning_goals_count": len(self.learning_goals)
        }
    
    async def _update_skill_proficiency(self, skill_name: str, reward: float):
        """更新技能熟练度"""
        if skill_name not in self.skill_inventory:
            self.skill_inventory[skill_name] = Skill(
                name=skill_name,
                description=f"技能: {skill_name}",
                proficiency=max(0.0, min(1.0, (reward + 1) / 2)),  # 将[-1,1]的奖励映射到[0,1]
                usage_count=1,
                success_count=1 if reward > 0 else 0
            )
        else:
            skill = self.skill_inventory[skill_name]
            skill.usage_count += 1
            if reward > 0:
                skill.success_count += 1
            
            # 更新熟练度（结合历史成功率和最近表现）
            historical_success_rate = skill.success_count / skill.usage_count
            recent_impact = 0.3  # 最近表现的权重
            new_proficiency = (1 - recent_impact) * skill.proficiency + recent_impact * ((reward + 1) / 2)
            skill.proficiency = max(0.0, min(1.0, new_proficiency))
            skill.last_used = datetime.now()
    
    async def adapt_strategy(self, context: str = "") -> LearningStrategy:
        """根据上下文自适应选择最佳学习策略"""
        # 简单的策略选择逻辑：根据任务类型和历史表现
        performance = await self.evaluate_performance()
        
        # 基于性能选择策略
        best_strategy = self.active_strategy
        best_score = float('-inf')
        
        for strategy_name, perf_data in performance["algorithm_performance"].items():
            if "error" not in perf_data:
                # 计算综合得分（奖励、收敛性、准确性的加权平均）
                reward_score = perf_data.get("average_reward", 0)
                convergence_score = perf_data.get("convergence", 0)
                accuracy_score = perf_data.get("average_accuracy", 0)
                
                # 加权综合得分
                composite_score = 0.5 * reward_score + 0.3 * convergence_score + 0.2 * accuracy_score
                
                if composite_score > best_score:
                    best_score = composite_score
                    try:
                        best_strategy = LearningStrategy(strategy_name)
                    except ValueError:
                        # 如果策略名称无效，则保持当前策略
                        continue
        
        self.active_strategy = best_strategy
        return self.active_strategy
    
    async def get_recommendations(self) -> List[str]:
        """获取学习改进建议"""
        recommendations = []
        
        # 检查技能熟练度
        low_proficiency_skills = [
            skill.name for skill in self.skill_inventory.values() 
            if skill.proficiency < 0.5 and skill.usage_count > 2
        ]
        
        if low_proficiency_skills:
            recommendations.append(f"建议加强以下技能的练习: {', '.join(low_proficiency_skills)}")
        
        # 检查性能指标
        if self.performance_metrics["reward"]:
            recent_rewards = self.performance_metrics["reward"][-10:]  # 最近10次奖励
            if sum(recent_rewards) / len(recent_rewards) < 0.2:  # 平均奖励较低
                recommendations.append("近期表现不佳，建议调整策略或寻求帮助")
        
        # 检查学习目标完成情况
        incomplete_goals = [goal for goal in self.learning_goals if not goal.get("completed", False)]
        if len(incomplete_goals) > 5:  # 超过5个未完成目标
            recommendations.append(f"有{len(incomplete_goals)}个学习目标待完成，建议优先处理")
        
        return recommendations if recommendations else ["当前学习状态良好，继续保持"]
    
    async def set_learning_goal(self, goal: str, target_metric: str = "reward", target_value: float = 0.8):
        """设定学习目标"""
        import uuid
        
        goal_entry = {
            "id": str(uuid.uuid4()),
            "description": goal,
            "target_metric": target_metric,
            "target_value": target_value,
            "current_value": 0.0,
            "created_at": datetime.now(),
            "completed": False,
            "progress": 0.0
        }
        
        self.learning_goals.append(goal_entry)
    
    async def get_skills_summary(self) -> Dict[str, Any]:
        """获取技能总结"""
        if not self.skill_inventory:
            return {"total_skills": 0, "average_proficiency": 0.0, "most_used": [], "highest_rated": []}
        
        total_skills = len(self.skill_inventory)
        _profs = [s.proficiency for s in self.skill_inventory.values()]
        avg_proficiency = sum(_profs) / len(_profs)
        
        # 按使用次数排序
        most_used = sorted(self.skill_inventory.values(), key=lambda s: s.usage_count, reverse=True)[:5]
        
        # 按熟练度排序
        highest_rated = sorted(self.skill_inventory.values(), key=lambda s: s.proficiency, reverse=True)[:5]
        
        return {
            "total_skills": total_skills,
            "average_proficiency": float(avg_proficiency),
            "most_used": [(s.name, s.usage_count, s.proficiency) for s in most_used],
            "highest_rated": [(s.name, s.proficiency, s.usage_count) for s in highest_rated]
        }


class LearningAgentMixin:
    """学习型Agent混入类"""
    
    def __init__(self, adaptive_learner: AdaptiveLearner):
        self.adaptive_learner = adaptive_learner
        self.learning_enabled = True
    
    async def enable_learning(self):
        """启用学习"""
        self.learning_enabled = True
    
    async def disable_learning(self):
        """禁用学习"""
        self.learning_enabled = False
    
    async def learn_from_interaction(self, user_input: str, agent_response: str, 
                                   environment_feedback: str = "", reward: float = 0.0):
        """从交互中学习"""
        if not self.learning_enabled:
            return
        
        # 如果没有显式奖励，根据反馈推断奖励
        if reward == 0.0:
            reward = self._infer_reward(agent_response, environment_feedback)
        
        # 添加学习经验
        await self.adaptive_learner.add_experience(
            input_context=user_input,
            action_taken=agent_response,
            outcome=environment_feedback,
            reward=reward,
            metadata={
                "interaction_type": "user_agent",
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def _infer_reward(self, response: str, feedback: str) -> float:
        """从反馈中推断奖励"""
        positive_indicators = ["好", "不错", "谢谢", "有用", "正确", "满意"]
        negative_indicators = ["不好", "错误", "没用", "不对", "失望", "糟糕"]
        
        pos_count = sum(1 for indicator in positive_indicators if indicator in feedback.lower())
        neg_count = sum(1 for indicator in negative_indicators if indicator in feedback.lower())
        
        if pos_count > neg_count:
            return min(1.0, 0.2 * pos_count)  # 最大奖励为1.0
        elif neg_count > pos_count:
            return max(-1.0, -0.2 * neg_count)  # 最小奖励为-1.0
        else:
            return 0.1  # 中性反馈给予轻微正奖励
    
    async def get_advice_for_task(self, task_description: str) -> Tuple[str, float]:
        """获取任务执行建议"""
        if not self.learning_enabled:
            return "default_action", 0.5
        
        # 使用学习算法预测最佳动作
        action, confidence, strategy = await self.adaptive_learner.predict_next_action(task_description)
        
        # 适应策略
        await self.adaptive_learner.adapt_strategy(task_description)
        
        return action, confidence
    
    async def get_learning_status(self) -> Dict[str, Any]:
        """获取学习状态"""
        performance = await self.adaptive_learner.evaluate_performance()
        skills_summary = await self.adaptive_learner.get_skills_summary()
        recommendations = await self.adaptive_learner.get_recommendations()
        
        return {
            "performance": performance,
            "skills": skills_summary,
            "recommendations": recommendations,
            "learning_enabled": self.learning_enabled
        }
    
    async def set_learning_target(self, goal: str, metric: str = "reward", target: float = 0.8):
        """设定学习目标"""
        await self.adaptive_learner.set_learning_goal(goal, metric, target)