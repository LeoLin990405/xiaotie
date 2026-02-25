"""
上下文感知系统

实现智能上下文理解和管理
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import defaultdict, deque
import hashlib

from ..schema import Message
from ..memory.core import MemoryManager, MemoryType
from ..planning.core import TaskManager


class ContextType(Enum):
    """上下文类型"""
    CONVERSATIONAL = "conversational"    # 对话上下文
    TOPICAL = "topical"                  # 主题上下文
    TEMPORAL = "temporal"               # 时间上下文
    SPATIAL = "spatial"                 # 空间上下文
    TASK = "task"                       # 任务上下文
    DOMAIN = "domain"                   # 领域上下文
    SOCIAL = "social"                   # 社交上下文
    EMOTIONAL = "emotional"             # 情感上下文


class ContextScope(Enum):
    """上下文范围"""
    LOCAL = "local"      # 本地/当前交互
    SESSION = "session"  # 会话级别
    CONVERSATION = "conversation"  # 对话级别
    TOPIC = "topic"      # 主题级别
    LONG_TERM = "long_term"  # 长期记忆


@dataclass
class ContextEntity:
    """上下文实体"""
    id: str
    name: str
    entity_type: str  # person, place, concept, object, etc.
    value: Any
    confidence: float = 1.0  # 置信度 0-1
    importance: float = 0.5  # 重要性 0-1
    relevance: float = 0.5   # 相关性 0-1
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ContextFrame:
    """上下文框架"""
    id: str
    context_type: ContextType
    scope: ContextScope
    entities: List[ContextEntity]
    relationships: Dict[str, List[str]]  # entity_id -> related_entity_ids
    salience_scores: Dict[str, float]   # entity_id -> salience score
    timestamp: datetime
    duration: Optional[timedelta] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
        if self.entities is None:
            self.entities = []
        if self.relationships is None:
            self.relationships = {}
        if self.salience_scores is None:
            self.salience_scores = {}


class BaseContextExtractor(ABC):
    """上下文提取器基类"""
    
    @abstractmethod
    async def extract(self, text: str, existing_context: Optional[ContextFrame] = None) -> List[ContextEntity]:
        """从文本中提取上下文实体"""
        pass


class RuleBasedContextExtractor(BaseContextExtractor):
    """基于规则的上下文提取器"""
    
    def __init__(self):
        # 定义一些基本的提取规则
        self.rules = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'url': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            'time': r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
            'number': r'\b\d+(?:\.\d+)?\b',
            'person': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # 简单的姓名模式
        }
    
    async def extract(self, text: str, existing_context: Optional[ContextFrame] = None) -> List[ContextEntity]:
        """从文本中提取上下文实体"""
        entities = []
        
        for entity_type, pattern in self.rules.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                entity_id = hashlib.md5(f"{entity_type}_{match.group()}_{text}".encode()).hexdigest()[:8]
                
                entity = ContextEntity(
                    id=entity_id,
                    name=match.group(),
                    entity_type=entity_type,
                    value=match.group(),
                    confidence=0.8,  # 基于规则的提取通常比较可靠
                    importance=0.5,
                    relevance=0.7
                )
                entities.append(entity)
        
        # 提取名词短语作为概念实体（简单实现）
        # 这里可以集成更复杂的NLP技术
        words = re.findall(r'\b\w+\b', text)
        nouns = [word for word in words if word[0].isupper() or len(word) > 4]  # 简单启发式
        
        for noun in nouns[:10]:  # 限制数量
            entity_id = hashlib.md5(f"concept_{noun}_{text}".encode()).hexdigest()[:8]
            entity = ContextEntity(
                id=entity_id,
                name=noun,
                entity_type="concept",
                value=noun,
                confidence=0.6,
                importance=0.4,
                relevance=0.5
            )
            entities.append(entity)
        
        return entities


class ContextSimilarityScorer:
    """上下文相似度评分器"""
    
    @staticmethod
    def calculate_text_similarity(text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 使用Jaccard相似度
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def calculate_entity_similarity(entity1: ContextEntity, entity2: ContextEntity) -> float:
        """计算实体相似度"""
        if entity1.entity_type != entity2.entity_type:
            return 0.0
        
        if entity1.name.lower() == entity2.name.lower():
            return 1.0
        
        # 计算名称相似度
        name_sim = ContextSimilarityScorer.calculate_text_similarity(
            entity1.name, entity2.name
        )
        
        # 结合类型和值的相似度
        type_weight = 0.3
        name_weight = 0.7
        
        return type_weight * (1.0 if entity1.entity_type == entity2.entity_type else 0.0) + \
               name_weight * name_sim


class ContextManager:
    """上下文管理器"""
    
    def __init__(self, memory_manager: MemoryManager, task_manager: TaskManager = None):
        self.memory_manager = memory_manager
        self.task_manager = task_manager
        self.extractor = RuleBasedContextExtractor()
        self.scorer = ContextSimilarityScorer()
        
        # 当前上下文栈
        self.context_stack: List[ContextFrame] = []
        
        # 实体跟踪
        self.entity_tracker: Dict[str, ContextEntity] = {}
        
        # 上下文窗口大小
        self.max_context_frames = 100
        self.max_entities_per_frame = 50
    
    async def extract_context(self, text: str, context_type: ContextType = ContextType.CONVERSATIONAL,
                             scope: ContextScope = ContextScope.LOCAL) -> ContextFrame:
        """从文本中提取上下文"""
        # 提取实体
        entities = await self.extractor.extract(text)
        
        # 过滤重复实体
        unique_entities = []
        seen_names = set()
        for entity in entities:
            if entity.name.lower() not in seen_names and len(unique_entities) < self.max_entities_per_frame:
                unique_entities.append(entity)
                seen_names.add(entity.name.lower())
                # 更新实体跟踪器
                self.entity_tracker[entity.id] = entity
        
        # 创建上下文框架
        import uuid
        frame_id = str(uuid.uuid4())
        
        # 计算实体间的关系（简单实现：基于共同出现）
        relationships = self._compute_relationships(unique_entities, text)
        
        # 计算显著性分数
        salience_scores = self._compute_salience_scores(unique_entities, text)
        
        context_frame = ContextFrame(
            id=frame_id,
            context_type=context_type,
            scope=scope,
            entities=unique_entities,
            relationships=relationships,
            salience_scores=salience_scores,
            timestamp=datetime.now()
        )
        
        # 添加到上下文栈
        self.context_stack.append(context_frame)
        
        # 保持栈大小限制
        if len(self.context_stack) > self.max_context_frames:
            self.context_stack.pop(0)
        
        return context_frame
    
    def _compute_relationships(self, entities: List[ContextEntity], text: str) -> Dict[str, List[str]]:
        """计算实体间的关系"""
        relationships = defaultdict(list)
        
        # 简单实现：如果两个实体在文本中同时出现，则认为有关联
        entity_positions = {}
        for entity in entities:
            positions = [m.start() for m in re.finditer(re.escape(entity.name), text, re.IGNORECASE)]
            if positions:
                entity_positions[entity.id] = positions
        
        # 如果两个实体出现在相近位置，则建立关系
        for ent1_id, pos1 in entity_positions.items():
            for ent2_id, pos2 in entity_positions.items():
                if ent1_id != ent2_id:
                    # 检查是否在相近位置（例如，相距不超过100个字符）
                    for p1 in pos1:
                        for p2 in pos2:
                            if abs(p1 - p2) <= 100:  # 100字符内的共现
                                if ent2_id not in relationships[ent1_id]:
                                    relationships[ent1_id].append(ent2_id)
                                break
        
        return dict(relationships)
    
    def _compute_salience_scores(self, entities: List[ContextEntity], text: str) -> Dict[str, float]:
        """计算实体的显著性分数"""
        scores = {}
        
        # 基于实体在文本中的出现频率和位置
        text_lower = text.lower()
        total_length = len(text)
        
        for entity in entities:
            # 计算出现频率
            frequency = len(re.findall(re.escape(entity.name), text_lower, re.IGNORECASE))
            
            # 计算位置分数（前面的词通常更重要）
            positions = [m.start() for m in re.finditer(re.escape(entity.name), text_lower, re.IGNORECASE)]
            position_score = sum((total_length - pos) / total_length for pos in positions) if positions else 0
            
            # 综合分数
            salience = (frequency * 0.6) + (position_score * 0.4)
            # 归一化到[0,1]
            normalized_salience = min(1.0, salience / 10.0)  # 假设最大值约为10
            
            scores[entity.id] = normalized_salience
        
        return scores
    
    async def get_relevant_context(self, query: str, top_k: int = 5) -> List[ContextFrame]:
        """获取与查询相关的上下文"""
        relevant_frames = []
        
        for frame in self.context_stack[-20:]:  # 检查最近的20个上下文帧
            # 计算帧与查询的相关性
            frame_text = " ".join([entity.name for entity in frame.entities])
            similarity = self.scorer.calculate_text_similarity(query.lower(), frame_text.lower())
            
            if similarity > 0.1:  # 阈值
                relevant_frames.append((frame, similarity))
        
        # 按相似度排序
        relevant_frames.sort(key=lambda x: x[1], reverse=True)
        
        # 返回前top_k个
        return [frame for frame, sim in relevant_frames[:top_k]]
    
    async def get_entity_by_name(self, name: str, threshold: float = 0.8) -> Optional[ContextEntity]:
        """通过名称获取实体"""
        name_lower = name.lower()
        
        for entity in self.entity_tracker.values():
            if entity.name.lower() == name_lower:
                return entity
            
            # 检查相似性
            similarity = self.scorer.calculate_text_similarity(name_lower, entity.name.lower())
            if similarity >= threshold:
                return entity
        
        return None
    
    async def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """更新实体信息"""
        if entity_id in self.entity_tracker:
            entity = self.entity_tracker[entity_id]
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            return True
        return False
    
    async def get_context_summary(self, scope: ContextScope = None) -> Dict[str, Any]:
        """获取上下文摘要"""
        frames_to_consider = self.context_stack
        if scope:
            frames_to_consider = [f for f in self.context_stack if f.scope == scope]
        
        if not frames_to_consider:
            return {
                "total_frames": 0,
                "total_entities": 0,
                "context_types": [],
                "most_common_entities": [],
                "active_topics": []
            }
        
        # 统计信息
        total_frames = len(frames_to_consider)
        total_entities = sum(len(frame.entities) for frame in frames_to_consider)
        
        # 上下文类型分布
        type_counts = defaultdict(int)
        for frame in frames_to_consider:
            type_counts[frame.context_type.value] += 1
        
        # 最常见实体
        entity_freq = defaultdict(int)
        for frame in frames_to_consider:
            for entity in frame.entities:
                entity_freq[entity.name] += 1
        
        most_common_entities = sorted(
            entity_freq.items(), key=lambda x: x[1], reverse=True
        )[:10]
        
        # 活跃主题（基于最近的实体）
        recent_entities = []
        for frame in frames_to_consider[-5:]:  # 最近5个帧
            recent_entities.extend(frame.entities)
        
        active_topics = list(set(
            entity.name for entity in recent_entities 
            if entity.entity_type in ['concept', 'topic', 'subject']
        ))[:10]
        
        return {
            "total_frames": total_frames,
            "total_entities": total_entities,
            "context_types": dict(type_counts),
            "most_common_entities": most_common_entities,
            "active_topics": active_topics,
            "current_stack_size": len(self.context_stack)
        }
    
    async def clear_context(self, scope: ContextScope = None):
        """清除上下文"""
        if scope:
            self.context_stack = [f for f in self.context_stack if f.scope != scope]
        else:
            self.context_stack = []
            self.entity_tracker = {}
    
    async def get_salient_entities(self, threshold: float = 0.5) -> List[ContextEntity]:
        """获取显著实体"""
        salient_entities = []
        
        for frame in self.context_stack[-10:]:  # 检查最近的帧
            for entity_id, score in frame.salience_scores.items():
                if score >= threshold:
                    # 找到对应的实体
                    for entity in frame.entities:
                        if entity.id == entity_id:
                            salient_entities.append(entity)
                            break
        
        # 去重
        unique_entities = []
        seen_ids = set()
        for entity in salient_entities:
            if entity.id not in seen_ids:
                unique_entities.append(entity)
                seen_ids.add(entity.id)
        
        return unique_entities
    
    async def infer_topic_shift(self, current_text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """推断话题转换"""
        if len(self.context_stack) < 2:
            return False, None, None
        
        prev_frame = self.context_stack[-2]
        curr_frame = self.context_stack[-1]
        
        # 计算前后上下文的相似度
        prev_entities = {e.name.lower() for e in prev_frame.entities}
        curr_entities = {e.name.lower() for e in curr_frame.entities}
        
        intersection = len(prev_entities.intersection(curr_entities))
        union = len(prev_entities.union(curr_entities))
        
        similarity = intersection / union if union > 0 else 0
        
        # 如果相似度很低，可能发生了话题转换
        topic_change_threshold = 0.3
        if similarity < topic_change_threshold:
            # 识别新话题
            new_entities = curr_entities - prev_entities
            old_entities = prev_entities - curr_entities
            
            new_topic = ", ".join(list(new_entities)[:3])  # 最多3个新实体
            old_topic = ", ".join(list(old_entities)[:3])  # 最多3个旧实体
            
            return True, new_topic, old_topic
        
        return False, None, None
    
    async def get_context_for_task(self, task_description: str) -> Dict[str, Any]:
        """获取任务相关上下文"""
        # 查找与任务描述相关的上下文
        relevant_frames = await self.get_relevant_context(task_description, top_k=10)
        
        # 提取相关实体
        relevant_entities = []
        for frame in relevant_frames:
            for entity in frame.entities:
                if entity.relevance > 0.3:  # 相关性阈值
                    relevant_entities.append({
                        "name": entity.name,
                        "type": entity.entity_type,
                        "value": entity.value,
                        "confidence": entity.confidence,
                        "relevance": entity.relevance
                    })
        
        return {
            "relevant_frames_count": len(relevant_frames),
            "relevant_entities": relevant_entities,
            "context_summary": await self.get_context_summary()
        }


class ContextAwareAgentMixin:
    """上下文感知Agent混入类"""
    
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.context_awareness_enabled = True
    
    async def enable_context_awareness(self):
        """启用上下文感知"""
        self.context_awareness_enabled = True
    
    async def disable_context_awareness(self):
        """禁用上下文感知"""
        self.context_awareness_enabled = False
    
    async def process_with_context(self, input_text: str, context_type: ContextType = ContextType.CONVERSATIONAL,
                                 scope: ContextScope = ContextScope.LOCAL) -> Dict[str, Any]:
        """在上下文中处理输入"""
        if not self.context_awareness_enabled:
            return {"processed_text": input_text, "context_enhanced": False}
        
        # 提取当前上下文
        current_context = await self.context_manager.extract_context(
            input_text, context_type, scope
        )
        
        # 检查话题转换
        topic_changed, new_topic, old_topic = await self.context_manager.infer_topic_shift(input_text)
        
        # 获取相关上下文
        relevant_context = await self.context_manager.get_relevant_context(input_text, top_k=3)
        
        # 获取显著实体
        salient_entities = await self.context_manager.get_salient_entities(threshold=0.6)
        
        # 生成上下文增强的输入
        context_enhanced_text = input_text
        if salient_entities:
            context_enhanced_text += f"\n[上下文相关实体: {', '.join([e.name for e in salient_entities[:5]])}]"
        
        return {
            "original_text": input_text,
            "context_enhanced_text": context_enhanced_text,
            "extracted_context": {
                "entities_count": len(current_context.entities),
                "relationships_count": len(current_context.relationships),
                "salient_entities_count": len(salient_entities)
            },
            "topic_changed": topic_changed,
            "new_topic": new_topic,
            "old_topic": old_topic,
            "relevant_context_count": len(relevant_context),
            "context_enhanced": True
        }
    
    async def get_current_context_state(self) -> Dict[str, Any]:
        """获取当前上下文状态"""
        if not self.context_awareness_enabled:
            return {"enabled": False}
        
        context_summary = await self.context_manager.get_context_summary()
        salient_entities = await self.context_manager.get_salient_entities()
        
        return {
            "enabled": self.context_awareness_enabled,
            "summary": context_summary,
            "salient_entities": [
                {"name": e.name, "type": e.entity_type, "value": e.value, "score": e.relevance}
                for e in salient_entities[:10]
            ],
            "active_context_frames": len(self.context_manager.context_stack)
        }
    
    async def update_context_entity(self, entity_name: str, updates: Dict[str, Any]) -> bool:
        """更新上下文实体"""
        # 首先找到实体ID
        entity = await self.context_manager.get_entity_by_name(entity_name)
        if entity:
            return await self.context_manager.update_entity(entity.id, updates)
        return False
    
    async def get_task_context(self, task_description: str) -> Dict[str, Any]:
        """获取任务上下文"""
        return await self.context_manager.get_context_for_task(task_description)
    
    async def reset_context(self, scope: ContextScope = None):
        """重置上下文"""
        await self.context_manager.clear_context(scope)