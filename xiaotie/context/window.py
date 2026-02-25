"""
上下文窗口管理系统

实现动态上下文窗口管理，优化上下文长度和相关性
"""

import asyncio
import heapq
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import deque

from ..schema import Message
from ..memory.core import MemoryManager, MemoryType
from ..context.core import ContextManager, ContextEntity


class CompressionMethod(Enum):
    """压缩方法"""
    SUMMARIZATION = "summarization"      # 摘要
    TRUNCATION = "truncation"           # 截断
    SLIDING_WINDOW = "sliding_window"    # 滑动窗口
    RELEVANCE_FILTERING = "relevance_filtering"  # 相关性过滤
    HYBRID = "hybrid"                  # 混合方法


class WindowStrategy(Enum):
    """窗口策略"""
    FIXED_SIZE = "fixed_size"          # 固定大小
    DYNAMIC_SIZE = "dynamic_size"       # 动态大小
    TASK_BASED = "task_based"          # 基于任务
    CONTEXT_AWARE = "context_aware"     # 上下文感知


@dataclass
class ContextWindow:
    """上下文窗口"""
    id: str
    messages: List[Message]
    entities: List[ContextEntity]
    compression_ratio: float = 1.0  # 压缩比例 0-1，1为无压缩
    max_size: Optional[int] = None   # 最大消息数量
    strategy: WindowStrategy = WindowStrategy.FIXED_SIZE
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
        if self.messages is None:
            self.messages = []
        if self.entities is None:
            self.entities = []


class BaseCompressionAlgorithm(ABC):
    """压缩算法基类"""
    
    @abstractmethod
    async def compress(self, messages: List[Message], target_size: int) -> List[Message]:
        """压缩消息列表到目标大小"""
        pass
    
    @abstractmethod
    async def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """计算压缩比例"""
        pass


class SummarizationCompression(BaseCompressionAlgorithm):
    """摘要压缩算法"""
    
    async def compress(self, messages: List[Message], target_size: int) -> List[Message]:
        """通过摘要压缩消息"""
        if len(messages) <= target_size:
            return messages
        
        # 保留最后的几条消息（最近的上下文很重要）
        preserved_count = max(1, target_size // 3)  # 保留1/3的消息
        preserved_messages = messages[-preserved_count:]
        
        # 将前面的消息压缩为摘要
        messages_to_summarize = messages[:len(messages) - preserved_count]
        
        if messages_to_summarize:
            # 创建摘要消息
            summary_content = await self._create_summary(messages_to_summarize)
            summary_message = Message(
                role="system",
                content=f"[上下文摘要: {summary_content}]",
                timestamp=datetime.now()
            )
            
            # 将摘要插入到保留消息之前
            return [summary_message] + preserved_messages
        else:
            return preserved_messages
    
    async def _create_summary(self, messages: List[Message]) -> str:
        """创建消息摘要"""
        # 简化的摘要创建
        # 在实际应用中，这可能需要调用LLM来生成摘要
        summary_parts = []
        
        for msg in messages[:10]:  # 限制摘要的消息数量
            role_prefix = {"user": "用户说", "assistant": "助手说", "system": "系统提示"}.get(msg.role, msg.role)
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            summary_parts.append(f"{role_prefix}: {content_preview}")
        
        return "; ".join(summary_parts)
    
    async def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """计算压缩比例"""
        if original_size == 0:
            return 1.0
        return compressed_size / original_size


class RelevanceFilteringCompression(BaseCompressionAlgorithm):
    """相关性过滤压缩算法"""
    
    def __init__(self):
        self.entity_extractor = None  # 可能需要外部实体提取器
    
    async def compress(self, messages: List[Message], target_size: int) -> List[Message]:
        """通过相关性过滤压缩消息"""
        if len(messages) <= target_size:
            return messages
        
        # 为每条消息分配相关性分数
        message_scores = []
        for i, msg in enumerate(messages):
            score = await self._calculate_relevance_score(msg, i, messages)
            message_scores.append((msg, score, i))  # (message, score, original_index)
        
        # 保留相关性最高的消息
        # 同时确保保留最近的消息（时间衰减）
        time_decay_factor = 0.8
        weighted_scores = []
        
        for msg, rel_score, orig_idx in message_scores:
            # 时间权重：越近的消息权重越高
            time_weight = time_decay_factor ** (len(messages) - orig_idx)
            final_score = rel_score * 0.7 + time_weight * 0.3  # 相关性和时间的平衡
            weighted_scores.append((msg, final_score))
        
        # 按分数排序并选择top-k
        weighted_scores.sort(key=lambda x: x[1], reverse=True)
        selected_messages = [msg for msg, score in weighted_scores[:target_size]]
        
        # 保持原始顺序
        original_order = {id(msg): i for i, (msg, _) in enumerate(weighted_scores)}
        selected_messages.sort(key=lambda msg: original_order[id(msg)])
        
        return selected_messages
    
    async def _calculate_relevance_score(self, message: Message, index: int, all_messages: List[Message]) -> float:
        """计算消息相关性分数"""
        # 简化的相关性计算
        score = 0.0
        
        # 基于消息长度的分数（较长的消息可能更重要）
        score += min(len(message.content) / 100, 0.3)  # 最多0.3分
        
        # 基于角色的分数
        if message.role == "user":
            score += 0.3
        elif message.role == "system":
            score += 0.2
        else:
            score += 0.1
        
        # 基于关键词的分数
        important_keywords = ["重要", "关键", "注意", "必须", "紧急", "核心", "主要"]
        content_lower = message.content.lower()
        keyword_score = sum(0.1 for kw in important_keywords if kw in content_lower)
        score += min(keyword_score, 0.2)  # 最多0.2分
        
        return min(score, 1.0)  # 限制在[0,1]范围内
    
    async def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """计算压缩比例"""
        if original_size == 0:
            return 1.0
        return compressed_size / original_size


class SlidingWindowCompression(BaseCompressionAlgorithm):
    """滑动窗口压缩算法"""
    
    async def compress(self, messages: List[Message], target_size: int) -> List[Message]:
        """使用滑动窗口保留最近的消息"""
        if len(messages) <= target_size:
            return messages
        
        # 保留最新的target_size条消息
        return messages[-target_size:]
    
    async def calculate_compression_ratio(self, original_size: int, compressed_size: int) -> float:
        """计算压缩比例"""
        if original_size == 0:
            return 1.0
        return compressed_size / original_size


class ContextWindowManager:
    """上下文窗口管理器"""
    
    def __init__(self, 
                 memory_manager: MemoryManager,
                 context_manager: ContextManager,
                 max_context_size: int = 20,
                 default_compression_method: CompressionMethod = CompressionMethod.RELEVANCE_FILTERING):
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.max_context_size = max_context_size
        self.default_compression_method = default_compression_method
        
        # 初始化压缩算法
        self.compression_algorithms = {
            CompressionMethod.SUMMARIZATION: SummarizationCompression(),
            CompressionMethod.RELEVANCE_FILTERING: RelevanceFilteringCompression(),
            CompressionMethod.SLIDING_WINDOW: SlidingWindowCompression(),
        }
        
        # 当前窗口
        self.current_window: Optional[ContextWindow] = None
        self.window_history: List[ContextWindow] = []
        
        # 实体跟踪
        self.tracked_entities: List[ContextEntity] = []
        
        # 压缩统计
        self.compression_stats: Dict[CompressionMethod, Dict[str, float]] = {
            method: {"total_operations": 0, "average_ratio": 1.0, "saved_tokens": 0}
            for method in CompressionMethod
        }
    
    async def update_context(self, new_messages: List[Message]) -> ContextWindow:
        """更新上下文窗口"""
        # 获取当前窗口或创建新窗口
        if self.current_window is None:
            self.current_window = ContextWindow(
                id="initial_window",
                messages=[],
                entities=[],
                max_size=self.max_context_size,
                strategy=WindowStrategy.DYNAMIC_SIZE
            )
        
        # 添加新消息
        self.current_window.messages.extend(new_messages)
        
        # 提取新消息中的上下文实体
        for msg in new_messages:
            context_frame = await self.context_manager.extract_context(
                msg.content, 
                scope=self.context_manager.scope.LOCAL if hasattr(self.context_manager, 'scope') else None
            )
            self.current_window.entities.extend(context_frame.entities)
            self.tracked_entities.extend(context_frame.entities)
        
        # 检查是否需要压缩
        if len(self.current_window.messages) > self.max_context_size:
            await self._compress_window()
        
        # 保存到历史
        self.window_history.append(self.current_window)
        
        # 保持历史记录在合理范围内
        if len(self.window_history) > 100:
            self.window_history = self.window_history[-50:]  # 保留最近50个窗口
        
        return self.current_window
    
    async def _compress_window(self):
        """压缩当前窗口"""
        if not self.current_window or len(self.current_window.messages) <= self.current_window.max_size:
            return
        
        # 选择压缩算法
        compression_algorithm = self.compression_algorithms[self.default_compression_method]
        
        # 执行压缩
        original_size = len(self.current_window.messages)
        compressed_messages = await compression_algorithm.compress(
            self.current_window.messages, 
            self.current_window.max_size
        )
        
        # 更新压缩比例
        compression_ratio = await compression_algorithm.calculate_compression_ratio(
            original_size, len(compressed_messages)
        )
        
        # 更新窗口
        self.current_window.messages = compressed_messages
        self.current_window.compression_ratio = compression_ratio
        
        # 更新统计信息
        stats = self.compression_stats[self.default_compression_method]
        stats["total_operations"] += 1
        stats["average_ratio"] = (stats["average_ratio"] * (stats["total_operations"] - 1) + compression_ratio) / stats["total_operations"]
        stats["saved_tokens"] += (original_size - len(compressed_messages))
    
    async def get_optimized_context(self, 
                                  target_size: Optional[int] = None,
                                  compression_method: Optional[CompressionMethod] = None) -> Tuple[List[Message], Dict[str, Any]]:
        """获取优化后的上下文"""
        if target_size is None:
            target_size = self.max_context_size
        
        if compression_method is None:
            compression_method = self.default_compression_method
        
        if not self.current_window or not self.current_window.messages:
            return [], {"compression_applied": False, "original_size": 0, "final_size": 0}
        
        original_size = len(self.current_window.messages)
        
        if original_size <= target_size:
            return self.current_window.messages, {
                "compression_applied": False,
                "original_size": original_size,
                "final_size": original_size,
                "compression_method": None
            }
        
        # 应用压缩
        compression_algorithm = self.compression_algorithms[compression_method]
        compressed_messages = await compression_algorithm.compress(
            self.current_window.messages, target_size
        )
        
        final_size = len(compressed_messages)
        compression_ratio = await compression_algorithm.calculate_compression_ratio(original_size, final_size)
        
        # 更新统计
        stats = self.compression_stats[compression_method]
        stats["total_operations"] += 1
        old_avg = stats["average_ratio"]
        stats["average_ratio"] = (old_avg * (stats["total_operations"] - 1) + compression_ratio) / stats["total_operations"]
        stats["saved_tokens"] += (original_size - final_size)
        
        return compressed_messages, {
            "compression_applied": True,
            "original_size": original_size,
            "final_size": final_size,
            "compression_method": compression_method.value,
            "compression_ratio": compression_ratio,
            "tokens_saved": original_size - final_size
        }
    
    async def switch_compression_method(self, method: CompressionMethod):
        """切换压缩方法"""
        if method in self.compression_algorithms:
            self.default_compression_method = method
            return True
        return False
    
    async def get_compression_analytics(self) -> Dict[str, Any]:
        """获取压缩分析"""
        total_operations = sum(stats["total_operations"] for stats in self.compression_stats.values())
        total_saved = sum(stats["saved_tokens"] for stats in self.compression_stats.values())
        
        method_breakdown = {}
        for method, stats in self.compression_stats.items():
            method_breakdown[method.value] = {
                "operations_count": stats["total_operations"],
                "average_compression_ratio": stats["average_ratio"],
                "tokens_saved": stats["saved_tokens"]
            }
        
        return {
            "total_compression_operations": total_operations,
            "total_tokens_saved": total_saved,
            "current_method": self.default_compression_method.value,
            "method_performance": method_breakdown,
            "current_window_size": len(self.current_window.messages) if self.current_window else 0,
            "max_allowed_size": self.max_context_size,
            "compression_history_length": len(self.window_history)
        }
    
    async def adaptive_resize(self, 
                           task_complexity: str = "medium",
                           urgency: str = "normal",
                           available_tokens: int = 4000) -> int:
        """自适应调整窗口大小"""
        # 根据任务复杂性、紧急程度和可用token数调整窗口大小
        
        base_size = self.max_context_size
        
        # 根据任务复杂性调整
        complexity_factors = {
            "simple": 0.7,
            "medium": 1.0,
            "complex": 1.5,
            "very_complex": 2.0
        }
        complexity_factor = complexity_factors.get(task_complexity, 1.0)
        
        # 根据紧急程度调整
        urgency_factors = {
            "low": 1.2,  # 低紧急：可以有更大的上下文
            "normal": 1.0,
            "high": 0.8,  # 高紧急：较小的上下文以节省资源
            "critical": 0.6
        }
        urgency_factor = urgency_factors.get(urgency, 1.0)
        
        # 根据可用token数调整
        token_factor = min(available_tokens / 8000, 1.5)  # 偿设最大8000 tokens
        
        # 计算调整后的大小
        adjusted_size = int(base_size * complexity_factor * urgency_factor * token_factor)
        
        # 限制在合理范围内
        min_size = max(5, base_size // 4)
        max_size = base_size * 2
        
        final_size = max(min_size, min(max_size, adjusted_size))
        
        # 更新最大上下文大小
        self.max_context_size = final_size
        
        return final_size
    
    async def get_relevant_context_for_task(self, 
                                          task_description: str, 
                                          max_messages: int = 10) -> List[Message]:
        """获取与特定任务相关的上下文"""
        if not self.current_window:
            return []
        
        # 使用相关性过滤算法获取最相关的消息
        all_messages = self.current_window.messages
        target_size = min(max_messages, len(all_messages))
        
        if len(all_messages) <= target_size:
            return all_messages
        
        # 临时使用相关性过滤算法来选择与任务最相关的消息
        relevance_filter = self.compression_algorithms[CompressionMethod.RELEVANCE_FILTERING]
        
        # 这有这需要修改算法以考虑任务描述
        # 简化实现：返回最近的消息
        return all_messages[-target_size:]
    
    async def clear_context(self):
        """清除上下文"""
        self.current_window = None
        self.window_history = []
        self.tracked_entities = []
    
    async def get_context_diversity_metrics(self) -> Dict[str, float]:
        """获取上下文多样性指标"""
        if not self.current_window or not self.current_window.messages:
            return {
                "message_count": 0,
                "role_diversity": 0.0,
                "topic_diversity": 0.0,
                "entity_density": 0.0
            }
        
        messages = self.current_window.messages
        
        # 角色多样性
        roles = [msg.role for msg in messages]
        unique_roles = set(roles)
        role_diversity = len(unique_roles) / 3.0 if roles else 0.0  # 假设最多3种角色
        
        # 实体密度
        total_entities = len(self.current_window.entities)
        entity_density = total_entities / len(messages) if messages else 0.0
        
        return {
            "message_count": len(messages),
            "role_diversity": role_diversity,
            "topic_diversity": 0.5,  # 简化实现
            "entity_density": entity_density
        }


class ContextAwareWindowManager(ContextWindowManager):
    """上下文感知窗口管理器"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_signals = []  # 上下文信号队列
        self.importance_weights = {}  # 重要性权重
    
    async def update_with_context_signals(self, 
                                        new_messages: List[Message], 
                                        context_signals: List[Dict[str, Any]] = None) -> ContextWindow:
        """使用上下文信号更新窗口"""
        if context_signals:
            self.context_signals.extend(context_signals)
            # 根据信号调整重要性权重
            await self._update_importance_weights(context_signals)
        
        return await self.update_context(new_messages)
    
    async def _update_importance_weights(self, signals: List[Dict[str, Any]]):
        """根据上下文信号更新重要性权重"""
        for signal in signals:
            entity_id = signal.get("entity_id")
            if entity_id:
                weight = signal.get("importance", 0.5)
                self.importance_weights[entity_id] = weight
    
    async def get_context_for_llm(self, 
                                 max_tokens: int = 3000,
                                 task_type: str = "general") -> Tuple[List[Message], Dict[str, Any]]:
        """为LLM获取优化的上下文"""
        # 估算token数量（简化：假设平均每个字符0.25个token）
        approx_tokens_per_char = 0.25
        approx_max_messages = int(max_tokens * 0.8 / (100 * approx_tokens_per_char))  # 偿设平均每条消息100字符
        
        # 获取优化的上下文
        optimized_messages, analytics = await self.get_optimized_context(
            target_size=min(approx_max_messages, self.max_context_size)
        )
        
        # 根据任务类型进行额外优化
        if task_type == "analytical":
            # 分析型任务可能需要更多的历史上下文
            pass
        elif task_type == "creative":
            # 创造性任务可能需要较少的约束上下文
            optimized_messages = optimized_messages[-5:]  # 只保留最近5条
        
        return optimized_messages, {
            **analytics,
            "task_type": task_type,
            "target_token_limit": max_tokens,
            "estimated_final_tokens": len(" ".join([m.content for m in optimized_messages])) * approx_tokens_per_char
        }