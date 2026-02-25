"""
Agent技能学习系统

实现Agent技能的获取、评估和改进
"""

import asyncio
import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque

from ..schema import Message
from ..memory.core import MemoryManager, MemoryType
from ..learning.core import AdaptiveLearner, Skill
from ..context.core import ContextManager


class SkillType(Enum):
    """技能类型"""
    TOOL_USE = "tool_use"              # 工具使用
    COMMUNICATION = "communication"     # 沟通交流
    PROBLEM_SOLVING = "problem_solving" # 问题解决
    ANALYTICAL = "analytical"          # 分析能力
    CREATIVE = "creative"              # 创造能力
    MEMORY_MANAGEMENT = "memory_management"  # 记忆管理
    TASK_EXECUTION = "task_execution"    # 任务执行
    LEARNING_ABILITY = "learning_ability"   # 学习能力


class SkillAcquisitionMethod(Enum):
    """技能获取方法"""
    PRACTICE_BASED = "practice_based"      # 基于实践
    OBSERVATION = "observation"            # 观察学习
    INSTRUCTION = "instruction"            # 指令学习
    REINFORCEMENT = "reinforcement"        # 强化学习
    TRANSFER_LEARNING = "transfer_learning" # 迁移学习


@dataclass
class SkillExample:
    """技能示例"""
    id: str
    input_context: str
    expected_output: str
    actual_output: str
    success: bool
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SkillDevelopmentStage:
    """技能发展阶段"""
    stage: str  # novice, advanced_beginner, competent, proficient, expert
    criteria: List[str]  # 该阶段的评价标准
    duration: timedelta  # 达到该阶段所需时间
    prerequisites: List[str]  # 前置技能要求


class BaseSkillEvaluator(ABC):
    """技能评估器基类"""
    
    @abstractmethod
    async def evaluate(self, skill: Skill, examples: List[SkillExample]) -> Dict[str, float]:
        """评估技能水平"""
        pass


class AccuracyBasedEvaluator(BaseSkillEvaluator):
    """基于准确率的评估器"""
    
    async def evaluate(self, skill: Skill, examples: List[SkillExample]) -> Dict[str, float]:
        """基于成功率评估技能"""
        if not examples:
            return {"accuracy": 0.0, "reliability": 0.0, "consistency": 0.0}
        
        successful_examples = [ex for ex in examples if ex.success]
        accuracy = len(successful_examples) / len(examples)
        
        # 计算可靠性（基于最近的表现）
        recent_examples = examples[-10:] if len(examples) >= 10 else examples
        recent_successful = [ex for ex in recent_examples if ex.success]
        reliability = len(recent_successful) / len(recent_examples) if recent_examples else 0.0
        
        # 计算一致性（基于表现的稳定性）
        if len(examples) < 2:
            consistency = accuracy
        else:
            # 计算成功率的标准差的倒数作为一致性指标
            accuracies = []
            for i in range(0, len(examples), max(1, len(examples)//5)):  # 分成5段
                segment = examples[i:i+max(1, len(examples)//5)]
                seg_success = [ex for ex in segment if ex.success]
                seg_acc = len(seg_success) / len(segment)
                accuracies.append(seg_acc)
            
            if len(accuracies) > 1:
                mean_acc = sum(accuracies) / len(accuracies)
                variance = sum((acc - mean_acc)**2 for acc in accuracies) / len(accuracies)
                consistency = 1.0 / (1.0 + variance)  # 方差越小，一致性越高
            else:
                consistency = accuracy
        
        return {
            "accuracy": accuracy,
            "reliability": reliability,
            "consistency": consistency
        }


class EfficiencyBasedEvaluator(BaseSkillEvaluator):
    """基于效率的评估器"""
    
    async def evaluate(self, skill: Skill, examples: List[SkillExample]) -> Dict[str, float]:
        """基于效率评估技能"""
        if not examples:
            return {"speed": 0.0, "resource_usage": 0.0, "optimality": 0.0}
        
        # 计算平均执行时间（这里模拟）
        total_time = sum(5 + i for i in range(len(examples)))  # 模拟时间
        avg_time = total_time / len(examples) if examples else 0
        speed = 1.0 / (1.0 + avg_time / 10)  # 时间越短，速度分越高
        
        # 资源使用效率（模拟）
        resource_usage = min(1.0, 0.8 - (len(examples) * 0.01))  # 示例计算
        
        # 最优性（基于结果质量）
        optimal_results = [ex for ex in examples if "optimal" in ex.actual_output.lower()]
        optimality = len(optimal_results) / len(examples) if examples else 0.0
        
        return {
            "speed": speed,
            "resource_usage": resource_usage,
            "optimality": optimality
        }


class SkillAcquirer:
    """技能获取器"""
    
    def __init__(self, memory_manager: MemoryManager, context_manager: ContextManager):
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.skill_examples: Dict[str, List[SkillExample]] = defaultdict(list)
        self.skill_evaluators = {
            "accuracy": AccuracyBasedEvaluator(),
            "efficiency": EfficiencyBasedEvaluator()
        }
    
    async def practice_skill(self, skill_name: str, input_context: str, 
                           expected_output: str, actual_output: str,
                           success: bool, metadata: Dict[str, Any] = None) -> Dict[str, float]:
        """通过实践获取技能"""
        import uuid
        
        example = SkillExample(
            id=str(uuid.uuid4()),
            input_context=input_context,
            expected_output=expected_output,
            actual_output=actual_output,
            success=success,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.skill_examples[skill_name].append(example)
        
        # 评估技能
        skill = Skill(name=skill_name, description=f"技能: {skill_name}")
        metrics = await self.evaluate_skill(skill)
        
        # 存储技能实践到记忆
        content = f"技能练习: {skill_name} - 输入: {input_context[:50]}... -> 结果: {'成功' if success else '失败'}"
        await self.memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=0.7 if success else 0.3,
            tags=["skill_practice", skill_name, "learning"],
            metadata={
                "skill_name": skill_name,
                "success": success,
                "timestamp": example.timestamp.isoformat()
            }
        )
        
        return metrics
    
    async def observe_skill(self, skill_name: str, observed_context: str, 
                          demonstration: str) -> Dict[str, Any]:
        """通过观察学习技能"""
        # 将观察到的示范存储为示例
        import uuid
        
        example = SkillExample(
            id=str(uuid.uuid4()),
            input_context=observed_context,
            expected_output=demonstration,
            actual_output=demonstration,  # 观察到的就是期望的
            success=True,
            timestamp=datetime.now(),
            metadata={"learning_method": "observation"}
        )
        
        self.skill_examples[skill_name].append(example)
        
        return {
            "skill_name": skill_name,
            "observed_context": observed_context,
            "demonstration_length": len(demonstration),
            "examples_count": len(self.skill_examples[skill_name])
        }
    
    async def receive_instruction(self, skill_name: str, instruction: str, 
                               expected_behavior: str) -> Dict[str, Any]:
        """通过指令学习技能"""
        # 指令可能包含技能的理论知识
        import uuid
        
        # 创建一个示例，表示理论学习
        example = SkillExample(
            id=str(uuid.uuid4()),
            input_context=instruction,
            expected_output=expected_behavior,
            actual_output="",  # 初始为空，等待实践验证
            success=False,  # 理论学习不算成功，需要实践验证
            timestamp=datetime.now(),
            metadata={"learning_method": "instruction", "type": "theoretical"}
        )
        
        self.skill_examples[skill_name].append(example)
        
        # 存储指令到记忆
        content = f"技能指令: {skill_name} - {instruction[:100]}..."
        await self.memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.SEMANTIC,
            importance=0.5,
            tags=["skill_instruction", skill_name, "learning"],
            metadata={
                "skill_name": skill_name,
                "instruction": instruction,
                "expected_behavior": expected_behavior
            }
        )
        
        return {
            "skill_name": skill_name,
            "instruction_length": len(instruction),
            "theoretical_examples_count": len([ex for ex in self.skill_examples[skill_name] if ex.metadata.get("type") == "theoretical"])
        }
    
    async def evaluate_skill(self, skill: Skill) -> Dict[str, float]:
        """评估技能"""
        examples = self.skill_examples[skill.name]
        
        # 使用多个评估器
        accuracy_metrics = await self.skill_evaluators["accuracy"].evaluate(skill, examples)
        efficiency_metrics = await self.skill_evaluators["efficiency"].evaluate(skill, examples)
        
        # 综合评估
        overall_score = (
            accuracy_metrics.get("accuracy", 0) * 0.4 +
            accuracy_metrics.get("reliability", 0) * 0.2 +
            efficiency_metrics.get("speed", 0) * 0.2 +
            efficiency_metrics.get("optimality", 0) * 0.2
        )
        
        return {
            **accuracy_metrics,
            **efficiency_metrics,
            "overall_score": overall_score,
            "total_examples": len(examples),
            "successful_examples": len([ex for ex in examples if ex.success])
        }
    
    async def get_skill_development_path(self, skill_name: str) -> List[Dict[str, Any]]:
        """获取技能发展路径"""
        examples = self.skill_examples[skill_name]
        
        if not examples:
            return [{"stage": "novice", "progress": 0.0, "next_steps": ["开始练习该技能"]}]
        
        # 计算技能发展阶段
        success_rate = len([ex for ex in examples if ex.success]) / len(examples)
        
        stages = []
        if success_rate < 0.3:
            stages.append({"stage": "novice", "progress": success_rate, "next_steps": ["更多练习", "寻求指导"]})
        elif success_rate < 0.6:
            stages.append({"stage": "advanced_beginner", "progress": success_rate, "next_steps": ["挑战更难任务", "反思错误"]})
        elif success_rate < 0.8:
            stages.append({"stage": "competent", "progress": success_rate, "next_steps": ["多样化练习", "教授他人"]})
        elif success_rate < 0.95:
            stages.append({"stage": "proficient", "progress": success_rate, "next_steps": ["创新应用", "优化效率"]})
        else:
            stages.append({"stage": "expert", "progress": success_rate, "next_steps": ["传授技能", "开拓新领域"]})
        
        return stages
    
    async def transfer_skill_knowledge(self, source_skill: str, target_skill: str) -> bool:
        """技能知识迁移到另一个技能"""
        if source_skill not in self.skill_examples:
            return False
        
        source_examples = self.skill_examples[source_skill]
        
        # 迁移成功的示例到目标技能
        transferred_examples = []
        for example in source_examples:
            if example.success:
                # 修改示例以适应新技能
                new_example = SkillExample(
                    id=f"transferred_{example.id}",
                    input_context=example.input_context,
                    expected_output=example.expected_output,
                    actual_output=example.actual_output,
                    success=example.success,
                    timestamp=datetime.now(),
                    metadata={**example.metadata, "transferred_from": source_skill}
                )
                transferred_examples.append(new_example)
        
        # 添加到目标技能
        self.skill_examples[target_skill].extend(transferred_examples)
        
        return True


class SkillLearningAgentMixin:
    """技能学习Agent混入类"""
    
    def __init__(self, skill_acquirer: SkillAcquirer):
        self.skill_acquirer = skill_acquirer
        self.skill_learning_enabled = True
    
    async def enable_skill_learning(self):
        """启用技能学习"""
        self.skill_learning_enabled = True
    
    async def disable_skill_learning(self):
        """禁用技能学习"""
        self.skill_learning_enabled = False
    
    async def practice_skill(self, skill_name: str, input_context: str, 
                           expected_output: str, actual_output: str,
                           success: bool, metadata: Dict[str, Any] = None) -> Dict[str, float]:
        """实践技能"""
        if not self.skill_learning_enabled:
            return {"overall_score": 0.0, "practice_recorded": False}
        
        return await self.skill_acquirer.practice_skill(
            skill_name, input_context, expected_output, actual_output, success, metadata
        )
    
    async def learn_from_observation(self, skill_name: str, observed_context: str, 
                                   demonstration: str) -> Dict[str, Any]:
        """通过观察学习"""
        if not self.skill_learning_enabled:
            return {"learning_recorded": False}
        
        return await self.skill_acquirer.observe_skill(skill_name, observed_context, demonstration)
    
    async def learn_from_instruction(self, skill_name: str, instruction: str, 
                                  expected_behavior: str) -> Dict[str, Any]:
        """通过指令学习"""
        if not self.skill_learning_enabled:
            return {"learning_recorded": False}
        
        return await self.skill_acquirer.receive_instruction(skill_name, instruction, expected_behavior)
    
    async def evaluate_my_skill(self, skill_name: str) -> Dict[str, float]:
        """评估自己的技能"""
        if not self.skill_learning_enabled:
            return {"overall_score": 0.0, "evaluation_performed": False}
        
        skill = Skill(name=skill_name, description=f"技能: {skill_name}")
        return await self.skill_acquirer.evaluate_skill(skill)
    
    async def get_my_skill_progress(self, skill_name: str) -> List[Dict[str, Any]]:
        """获取技能进步情况"""
        if not self.skill_learning_enabled:
            return []
        
        return await self.skill_acquirer.get_skill_development_path(skill_name)
    
    async def get_skill_recommendations(self) -> List[Dict[str, str]]:
        """获取技能学习推荐"""
        if not self.skill_learning_enabled:
            return []
        
        recommendations = []
        
        # 分析所有技能的发展情况
        for skill_name in self.skill_acquirer.skill_examples.keys():
            progress = await self.get_my_skill_progress(skill_name)
            if progress:
                current_stage = progress[0]["stage"]
                next_steps = progress[0]["next_steps"]
                
                recommendations.append({
                    "skill": skill_name,
                    "current_level": current_stage,
                    "recommendations": ", ".join(next_steps)
                })
        
        return recommendations
    
    async def transfer_knowledge(self, source_skill: str, target_skill: str) -> bool:
        """知识迁移"""
        if not self.skill_learning_enabled:
            return False
        
        return await self.skill_acquirer.transfer_skill_knowledge(source_skill, target_skill)
    
    async def get_learning_analytics(self) -> Dict[str, Any]:
        """获取学习分析"""
        total_skills = len(self.skill_acquirer.skill_examples)
        total_examples = sum(len(examples) for examples in self.skill_acquirer.skill_examples.values())
        successful_examples = sum(
            len([ex for ex in examples if ex.success]) 
            for examples in self.skill_acquirer.skill_examples.values()
        )
        
        success_rate = successful_examples / total_examples if total_examples > 0 else 0.0
        
        return {
            "total_skills": total_skills,
            "total_examples": total_examples,
            "successful_examples": successful_examples,
            "success_rate": success_rate,
            "learning_enabled": self.skill_learning_enabled,
            "evaluator_types": list(self.skill_acquirer.skill_evaluators.keys())
        }