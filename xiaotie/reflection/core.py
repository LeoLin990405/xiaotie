"""
反思机制

实现Agent的自我评估和学习能力
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from ..schema import Message
from ..memory.core import MemoryManager, MemoryType


class ReflectionType(Enum):
    """反思类型"""
    TASK_EVALUATION = "task_evaluation"      # 任务评估
    STRATEGY_ADJUSTMENT = "strategy_adjustment"  # 策略调整
    KNOWLEDGE_UPDATE = "knowledge_update"    # 知识更新
    BEHAVIOR_LEARNING = "behavior_learning"  # 行为学习
    PERFORMANCE_ANALYSIS = "performance_analysis"  # 性能分析


@dataclass
class Reflection:
    """反思记录"""
    id: str
    reflection_type: ReflectionType
    trigger_event: str  # 触发反思的事件
    content: str       # 反思内容
    insights: List[str]  # 洞察/学习点
    action_items: List[str]  # 待办事项
    timestamp: datetime
    metadata: Dict[str, Any]
    rating: Optional[float] = None  # 1-10的评分


class BaseReflector(ABC):
    """反思器基类"""
    
    @abstractmethod
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """执行反思"""
        pass


class TaskEvaluator(BaseReflector):
    """任务评估反射器"""
    
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """评估任务执行效果"""
        task_result = context.get("task_result", "")
        task_goal = context.get("task_goal", "")
        execution_steps = context.get("execution_steps", [])
        time_taken = context.get("time_taken", 0)
        
        # 分析任务完成情况
        success_indicators = []
        improvement_areas = []
        
        if "成功" in task_result or "完成" in task_result:
            success_indicators.append("任务目标达成")
        else:
            improvement_areas.append("任务目标未完全达成")
        
        if time_taken > 30:  # 假设30秒以上为较慢
            improvement_areas.append("执行时间较长，可优化效率")
        else:
            success_indicators.append("执行效率良好")
        
        # 生成洞察
        insights = []
        if success_indicators:
            insights.extend(success_indicators)
        if improvement_areas:
            insights.extend(improvement_areas)
        
        # 生成行动项
        action_items = []
        if "执行时间较长" in " ".join(improvement_areas):
            action_items.append("研究更高效的执行策略")
        
        rating = 8.0 if "任务目标达成" in " ".join(success_indicators) else 5.0
        
        reflection = Reflection(
            id=str(uuid.uuid4()),
            reflection_type=ReflectionType.TASK_EVALUATION,
            trigger_event=trigger_event,
            content=f"任务评估: 针对目标'{task_goal}'的执行结果进行评估",
            insights=insights,
            action_items=action_items,
            timestamp=datetime.now(),
            metadata=context,
            rating=rating
        )
        
        return reflection


class StrategyAdjuster(BaseReflector):
    """策略调整反射器"""
    
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """调整执行策略"""
        previous_strategy = context.get("previous_strategy", "未知策略")
        outcome = context.get("outcome", "")
        alternatives_tried = context.get("alternatives_tried", [])
        
        # 分析策略有效性
        if "失败" in outcome or "错误" in outcome:
            insights = [
                f"策略 '{previous_strategy}' 未能达到预期结果",
                "需要尝试不同的方法"
            ]
            action_items = [
                "分析失败原因",
                "探索替代策略",
                "记录策略失效的场景"
            ]
        else:
            insights = [
                f"策略 '{previous_strategy}' 有效",
                "可以在类似场景中复用"
            ]
            action_items = [
                "将此策略加入策略库",
                "定义适用场景"
            ]
        
        rating = 6.0 if "失败" in outcome else 9.0
        
        reflection = Reflection(
            id=str(uuid.uuid4()),
            reflection_type=ReflectionType.STRATEGY_ADJUSTMENT,
            trigger_event=trigger_event,
            content=f"策略调整: 基于'{outcome}'结果调整'{previous_strategy}'策略",
            insights=insights,
            action_items=action_items,
            timestamp=datetime.now(),
            metadata=context,
            rating=rating
        )
        
        return reflection


class KnowledgeUpdater(BaseReflector):
    """知识更新反射器"""
    
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """更新知识库"""
        new_information = context.get("new_information", "")
        source = context.get("source", "unknown")
        confidence = context.get("confidence", 0.5)
        
        insights = [
            f"获得了关于'{source}'的新信息",
            f"信息可信度: {confidence:.2f}"
        ]
        
        action_items = [
            "整合新信息到知识库",
            "验证信息准确性",
            "更新相关概念连接"
        ]
        
        rating = min(10.0, 5.0 + confidence * 5.0)  # 基于置信度评分
        
        reflection = Reflection(
            id=str(uuid.uuid4()),
            reflection_type=ReflectionType.KNOWLEDGE_UPDATE,
            trigger_event=trigger_event,
            content=f"知识更新: 添加来自'{source}'的新信息: {new_information[:100]}...",
            insights=insights,
            action_items=action_items,
            timestamp=datetime.now(),
            metadata=context,
            rating=rating
        )
        
        return reflection


class BehaviorLearner(BaseReflector):
    """行为学习反射器"""
    
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """学习新行为模式"""
        behavior_sequence = context.get("behavior_sequence", [])
        outcome = context.get("outcome", "")
        environment = context.get("environment", "unknown")
        
        # 分析行为模式的有效性
        success_behavior = "产生积极结果的行为"
        failure_behavior = "导致负面结果的行为"
        
        if "成功" in outcome or "positive" in outcome.lower():
            insights = [
                f"在'{environment}'环境中，当前行为序列产生了积极结果",
                "值得在未来类似情境中复用"
            ]
            action_items = [
                "将此行为序列模式化",
                "定义触发此行为的情境条件"
            ]
        else:
            insights = [
                f"在'{environment}'环境中，当前行为序列未能产生理想结果",
                "需要调整行为策略"
            ]
            action_items = [
                "分析行为序列中的关键节点",
                "探索替代行为路径"
            ]
        
        rating = 7.0 if "积极结果" in " ".join(insights) else 4.0
        
        reflection = Reflection(
            id=str(uuid.uuid4()),
            reflection_type=ReflectionType.BEHAVIOR_LEARNING,
            trigger_event=trigger_event,
            content=f"行为学习: 分析在'{environment}'中的行为序列及其结果",
            insights=insights,
            action_items=action_items,
            timestamp=datetime.now(),
            metadata=context,
            rating=rating
        )
        
        return reflection


class PerformanceAnalyzer(BaseReflector):
    """性能分析反射器"""
    
    async def reflect(self, trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """分析性能表现"""
        metrics = context.get("metrics", {})
        baseline = context.get("baseline", {})
        resource_usage = context.get("resource_usage", {})
        
        insights = []
        action_items = []
        
        # 分析各项指标
        if metrics.get("response_time", 0) > baseline.get("response_time", 0) * 1.5:
            insights.append("响应时间超出基线标准50%以上")
            action_items.append("优化处理逻辑以提升响应速度")
        
        if metrics.get("accuracy", 0) < baseline.get("accuracy", 1.0) * 0.8:
            insights.append("准确率低于基线标准20%")
            action_items.append("分析准确率下降的原因并改进")
        
        if resource_usage.get("memory", 0) > baseline.get("memory", 0) * 2.0:
            insights.append("内存使用量超出基线标准2倍")
            action_items.append("优化内存管理策略")
        
        if not insights:
            insights.append("性能表现符合预期标准")
        
        # 计算整体评分
        score_components = []
        if "响应时间" in str(insights):
            score_components.append(3)  # 问题较多
        elif "准确率" in str(insights):
            score_components.append(5)  # 中等问题
        else:
            score_components.append(9)  # 表现良好
        
        rating = sum(score_components) / len(score_components) if score_components else 8.0
        
        reflection = Reflection(
            id=str(uuid.uuid4()),
            reflection_type=ReflectionType.PERFORMANCE_ANALYSIS,
            trigger_event=trigger_event,
            content=f"性能分析: 基于当前指标与基线对比的性能评估",
            insights=insights,
            action_items=action_items,
            timestamp=datetime.now(),
            metadata=context,
            rating=rating
        )
        
        return reflection


class ReflectionManager:
    """反思管理器"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.reflectors = {
            ReflectionType.TASK_EVALUATION: TaskEvaluator(),
            ReflectionType.STRATEGY_ADJUSTMENT: StrategyAdjuster(),
            ReflectionType.KNOWLEDGE_UPDATE: KnowledgeUpdater(),
            ReflectionType.BEHAVIOR_LEARNING: BehaviorLearner(),
            ReflectionType.PERFORMANCE_ANALYSIS: PerformanceAnalyzer(),
        }
        self.reflection_history: List[Reflection] = []
        self.learning_threshold = 0.7  # 学习阈值
    
    async def trigger_reflection(self, reflection_type: ReflectionType, 
                               trigger_event: str, context: Dict[str, Any]) -> Reflection:
        """触发特定类型的反思"""
        if reflection_type not in self.reflectors:
            raise ValueError(f"未知的反思类型: {reflection_type}")
        
        reflector = self.reflectors[reflection_type]
        reflection = await reflector.reflect(trigger_event, context)
        
        # 保存到历史记录
        self.reflection_history.append(reflection)
        
        # 存储到记忆系统
        await self._store_reflection_in_memory(reflection)
        
        # 根据评分决定是否需要采取行动
        if reflection.rating and reflection.rating < self.learning_threshold * 10:
            await self._generate_learning_actions(reflection)
        
        return reflection
    
    async def _store_reflection_in_memory(self, reflection: Reflection):
        """将反思存储到记忆系统"""
        content = f"反思类型: {reflection.reflection_type.value}\n" \
                 f"触发事件: {reflection.trigger_event}\n" \
                 f"内容: {reflection.content}\n" \
                 f"洞察: {', '.join(reflection.insights)}\n" \
                 f"行动项: {', '.join(reflection.action_items)}"
        
        metadata = {
            "reflection_type": reflection.reflection_type.value,
            "rating": reflection.rating,
            "timestamp": reflection.timestamp.isoformat()
        }
        
        await self.memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.LONG_TERM,
            importance=reflection.rating / 10 if reflection.rating else 0.5,
            tags=["reflection", reflection.reflection_type.value, "learning"],
            metadata=metadata
        )
    
    async def _generate_learning_actions(self, reflection: Reflection):
        """基于反思生成学习行动"""
        # 这里可以集成更复杂的学习算法
        # 简单实现：将行动项添加到待办事项列表
        for action_item in reflection.action_items:
            await self.memory_manager.add_memory(
                content=f"学习行动: {action_item}",
                memory_type=MemoryType.SHORT_TERM,
                importance=0.8,
                tags=["action_item", "learning"],
                metadata={"status": "pending", "reflection_id": reflection.id}
            )
    
    async def get_reflections_by_type(self, reflection_type: ReflectionType) -> List[Reflection]:
        """按类型获取反思记录"""
        return [r for r in self.reflection_history if r.reflection_type == reflection_type]
    
    async def get_high_impact_reflections(self, min_rating: float = 7.0) -> List[Reflection]:
        """获取高影响反思（高评分）"""
        return [r for r in self.reflection_history 
                if r.rating and r.rating >= min_rating]
    
    async def get_insights_summary(self) -> Dict[str, List[str]]:
        """获取洞察摘要"""
        summary = {}
        for reflection_type in ReflectionType:
            reflections = await self.get_reflections_by_type(reflection_type)
            all_insights = []
            for r in reflections:
                all_insights.extend(r.insights)
            summary[reflection_type.value] = all_insights
        
        return summary
    
    async def apply_learnings(self):
        """应用学习成果"""
        # 获取待处理的行动项
        action_memories = await self.memory_manager.search_by_tags(["action_item", "learning"])
        
        completed_actions = []
        for memory in action_memories:
            if memory.metadata.get("status") == "pending":
                # 这里应该执行实际的学习行动
                # 简单实现：标记为已完成
                await self.memory_manager.update_memory(
                    memory.id, 
                    metadata={**memory.metadata, "status": "completed", "applied_at": datetime.now().isoformat()}
                )
                completed_actions.append(memory.content)
        
        return completed_actions


class ReflectiveAgentMixin:
    """反射式Agent混入类"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.reflection_manager = ReflectionManager(memory_manager)
        self.reflection_enabled = True
    
    async def enable_reflection(self):
        """启用反思"""
        self.reflection_enabled = True
    
    async def disable_reflection(self):
        """禁用反思"""
        self.reflection_enabled = False
    
    async def reflect_on_task_completion(self, task_result: str, task_goal: str, 
                                      execution_time: float, steps_taken: List[str]):
        """对任务完成进行反思"""
        if not self.reflection_enabled:
            return
        
        context = {
            "task_result": task_result,
            "task_goal": task_goal,
            "time_taken": execution_time,
            "execution_steps": steps_taken
        }
        
        await self.reflection_manager.trigger_reflection(
            ReflectionType.TASK_EVALUATION,
            "task_completed",
            context
        )
    
    async def reflect_on_strategy_use(self, strategy: str, outcome: str, 
                                   alternatives: List[str] = None):
        """对策略使用进行反思"""
        if not self.reflection_enabled:
            return
        
        context = {
            "previous_strategy": strategy,
            "outcome": outcome,
            "alternatives_tried": alternatives or []
        }
        
        await self.reflection_manager.trigger_reflection(
            ReflectionType.STRATEGY_ADJUSTMENT,
            "strategy_evaluated",
            context
        )
    
    async def reflect_on_new_information(self, information: str, source: str, 
                                       confidence: float = 0.5):
        """对新信息进行反思"""
        if not self.reflection_enabled:
            return
        
        context = {
            "new_information": information,
            "source": source,
            "confidence": confidence
        }
        
        await self.reflection_manager.trigger_reflection(
            ReflectionType.KNOWLEDGE_UPDATE,
            "information_received",
            context
        )
    
    async def reflect_on_performance(self, metrics: Dict[str, float], 
                                  baseline: Dict[str, float],
                                  resource_usage: Dict[str, float]):
        """对性能进行反思"""
        if not self.reflection_enabled:
            return
        
        context = {
            "metrics": metrics,
            "baseline": baseline,
            "resource_usage": resource_usage
        }
        
        await self.reflection_manager.trigger_reflection(
            ReflectionType.PERFORMANCE_ANALYSIS,
            "performance_reviewed",
            context
        )
    
    async def learn_from_interaction(self, user_input: str, agent_response: str, 
                                   feedback: str = None):
        """从交互中学习"""
        if not self.reflection_enabled:
            return
        
        # 分析交互模式
        context = {
            "user_input": user_input,
            "agent_response": agent_response,
            "feedback": feedback or "no_feedback"
        }
        
        await self.reflection_manager.trigger_reflection(
            ReflectionType.BEHAVIOR_LEARNING,
            "interaction_completed",
            context
        )
    
    async def get_learning_summary(self) -> Dict[str, Any]:
        """获取学习摘要"""
        insights = await self.reflection_manager.get_insights_summary()
        high_impact = await self.reflection_manager.get_high_impact_reflections()
        
        return {
            "total_reflections": len(self.reflection_manager.reflection_history),
            "high_impact_count": len(high_impact),
            "insights_by_type": insights,
            "recent_action_items": [r.action_items for r in self.reflection_manager.reflection_history[-5:]]
        }