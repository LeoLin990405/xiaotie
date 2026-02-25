"""
记忆系统

实现短期记忆和长期记忆管理
"""

import asyncio
import json
import pickle
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from ..schema import Message
from ..storage.database import Database


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"    # 短期记忆
    LONG_TERM = "long_term"      # 长期记忆
    EPISODIC = "episodic"        # 情节记忆
    SEMANTIC = "semantic"        # 语义记忆
    WORKING = "working"          # 工作记忆


@dataclass
class MemoryChunk:
    """记忆块"""
    id: str
    content: str
    embedding: Optional[List[float]] = None  # 向量嵌入
    metadata: Dict[str, Any] = None
    timestamp: float = 0.0
    importance: float = 0.5  # 重要性评分 0-1
    tags: List[str] = None
    memory_type: MemoryType = MemoryType.SHORT_TERM

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = []
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class BaseMemoryBackend(ABC):
    """记忆后端基类"""
    
    @abstractmethod
    async def store(self, chunk: MemoryChunk) -> bool:
        """存储记忆块"""
        pass
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryChunk]:
        """检索记忆块"""
        pass
    
    @abstractmethod
    async def update(self, chunk: MemoryChunk) -> bool:
        """更新记忆块"""
        pass
    
    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """删除记忆块"""
        pass
    
    @abstractmethod
    async def search_by_tags(self, tags: List[str], top_k: int = 10) -> List[MemoryChunk]:
        """按标签搜索"""
        pass


class InMemoryBackend(BaseMemoryBackend):
    """内存后端实现"""

    def __init__(self):
        self.memory_store: Dict[str, MemoryChunk] = {}
        self.tag_index: Dict[str, List[str]] = {}  # tag -> [memory_ids]
        self._word_index: Dict[str, set] = {}  # word -> {chunk_ids} 倒排索引

    @staticmethod
    def _tokenize(text: str) -> set:
        """将文本拆分为小写词集合"""
        return set(text.lower().split())

    def _index_chunk(self, chunk: MemoryChunk):
        """将 chunk 加入倒排索引"""
        words = self._tokenize(chunk.content)
        for tag in chunk.tags:
            words.update(self._tokenize(tag))
        for word in words:
            if word not in self._word_index:
                self._word_index[word] = set()
            self._word_index[word].add(chunk.id)

    def _unindex_chunk(self, chunk: MemoryChunk):
        """将 chunk 从倒排索引移除"""
        words = self._tokenize(chunk.content)
        for tag in chunk.tags:
            words.update(self._tokenize(tag))
        for word in words:
            if word in self._word_index:
                self._word_index[word].discard(chunk.id)
                if not self._word_index[word]:
                    del self._word_index[word]

    async def store(self, chunk: MemoryChunk) -> bool:
        """存储记忆块"""
        # 如果已存在，先移除旧索引
        if chunk.id in self.memory_store:
            self._unindex_chunk(self.memory_store[chunk.id])

        self.memory_store[chunk.id] = chunk

        # 更新标签索引
        for tag in chunk.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            if chunk.id not in self.tag_index[tag]:
                self.tag_index[tag].append(chunk.id)

        # 更新倒排索引
        self._index_chunk(chunk)

        return True

    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryChunk]:
        """检索记忆块 - 使用倒排索引快速定位候选集 O(k)"""
        query_lower = query.lower()
        query_words = query_lower.split()

        # 通过倒排索引收集候选 chunk id
        candidate_ids: set = set()
        for word in query_words:
            if word in self._word_index:
                candidate_ids.update(self._word_index[word])

        # 仅对候选集评分，而非全量扫描
        results = []
        for cid in candidate_ids:
            chunk = self.memory_store.get(cid)
            if chunk is None:
                continue
            content_score = 0
            if query_lower in chunk.content.lower():
                content_score += 1
            for tag in chunk.tags:
                if query_lower in tag.lower():
                    content_score += 0.5

            if content_score > 0:
                age_hours = (time.time() - chunk.timestamp) / 3600
                time_decay = max(0.1, 1.0 - age_hours * 0.01)
                score = content_score + chunk.importance + time_decay
                results.append((chunk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, score in results[:top_k]]
    
    async def update(self, chunk: MemoryChunk) -> bool:
        """更新记忆块"""
        if chunk.id in self.memory_store:
            old_chunk = self.memory_store[chunk.id]
            # 移除旧标签索引
            for tag in old_chunk.tags:
                if tag in self.tag_index and chunk.id in self.tag_index[tag]:
                    self.tag_index[tag].remove(chunk.id)
            # 移除旧倒排索引
            self._unindex_chunk(old_chunk)

            # 存储新块
            self.memory_store[chunk.id] = chunk

            # 更新新标签索引
            for tag in chunk.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                if chunk.id not in self.tag_index[tag]:
                    self.tag_index[tag].append(chunk.id)
            # 更新新倒排索引
            self._index_chunk(chunk)

            return True
        return False

    async def delete(self, memory_id: str) -> bool:
        """删除记忆块"""
        if memory_id in self.memory_store:
            chunk = self.memory_store[memory_id]
            # 从标签索引中移除
            for tag in chunk.tags:
                if tag in self.tag_index and memory_id in self.tag_index[tag]:
                    self.tag_index[tag].remove(memory_id)
            # 从倒排索引中移除
            self._unindex_chunk(chunk)

            del self.memory_store[memory_id]
            return True
        return False
    
    async def search_by_tags(self, tags: List[str], top_k: int = 10) -> List[MemoryChunk]:
        """按标签搜索"""
        results = set()
        for tag in tags:
            if tag in self.tag_index:
                results.update(self.tag_index[tag])
        
        chunks = [self.memory_store[mid] for mid in results if mid in self.memory_store]
        # 按时间戳排序，最新的在前
        chunks.sort(key=lambda x: x.timestamp, reverse=True)
        return chunks[:top_k]


class DatabaseBackend(BaseMemoryBackend):
    """数据库后端实现"""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db = Database(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT,
                timestamp REAL,
                importance REAL,
                tags TEXT,
                memory_type TEXT
            )
        """)
        
        # 创建索引
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
    
    async def store(self, chunk: MemoryChunk) -> bool:
        """存储记忆块"""
        try:
            embedding_blob = pickle.dumps(chunk.embedding) if chunk.embedding else None
            metadata_json = json.dumps(chunk.metadata) if chunk.metadata else '{}'
            tags_json = json.dumps(chunk.tags) if chunk.tags else '[]'
            
            await self.db.execute_async("""
                INSERT OR REPLACE INTO memories 
                (id, content, embedding, metadata, timestamp, importance, tags, memory_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.id, chunk.content, embedding_blob, metadata_json,
                chunk.timestamp, chunk.importance, tags_json, chunk.memory_type.value
            ))
            return True
        except Exception as e:
            print(f"存储记忆块失败: {e}")
            return False
    
    async def retrieve(self, query: str, top_k: int = 5) -> List[MemoryChunk]:
        """检索记忆块"""
        try:
            rows = await self.db.fetch_all_async("""
                SELECT id, content, embedding, metadata, timestamp, importance, tags, memory_type
                FROM memories
                WHERE content LIKE ?
                ORDER BY importance DESC, timestamp DESC
                LIMIT ?
            """, (f'%{query}%', top_k))
            
            chunks = []
            for row in rows:
                embedding = pickle.loads(row['embedding']) if row['embedding'] else None
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                tags = json.loads(row['tags']) if row['tags'] else []
                
                chunk = MemoryChunk(
                    id=row['id'],
                    content=row['content'],
                    embedding=embedding,
                    metadata=metadata,
                    timestamp=row['timestamp'],
                    importance=row['importance'],
                    tags=tags,
                    memory_type=MemoryType(row['memory_type'])
                )
                chunks.append(chunk)
            
            return chunks
        except Exception as e:
            print(f"检索记忆块失败: {e}")
            return []
    
    async def update(self, chunk: MemoryChunk) -> bool:
        """更新记忆块"""
        return await self.store(chunk)  # 复用store逻辑，因为使用了INSERT OR REPLACE
    
    async def delete(self, memory_id: str) -> bool:
        """删除记忆块"""
        try:
            await self.db.execute_async("DELETE FROM memories WHERE id = ?", (memory_id,))
            return self.db.cursor.rowcount > 0
        except Exception as e:
            print(f"删除记忆块失败: {e}")
            return False
    
    async def search_by_tags(self, tags: List[str], top_k: int = 10) -> List[MemoryChunk]:
        """按标签搜索"""
        try:
            # 构建查询条件，查找包含任一标签的记忆
            tag_conditions = " OR ".join(["tags LIKE ?" for _ in tags])
            params = [f'%{tag}%' for tag in tags]
            
            query = f"""
                SELECT id, content, embedding, metadata, timestamp, importance, tags, memory_type
                FROM memories
                WHERE {tag_conditions}
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params.append(top_k)
            
            rows = await self.db.fetch_all_async(query, params)
            
            chunks = []
            for row in rows:
                embedding = pickle.loads(row['embedding']) if row['embedding'] else None
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                tags = json.loads(row['tags']) if row['tags'] else []
                
                chunk = MemoryChunk(
                    id=row['id'],
                    content=row['content'],
                    embedding=embedding,
                    metadata=metadata,
                    timestamp=row['timestamp'],
                    importance=row['importance'],
                    tags=tags,
                    memory_type=MemoryType(row['memory_type'])
                )
                chunks.append(chunk)
            
            return chunks
        except Exception as e:
            print(f"按标签搜索失败: {e}")
            return []


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, backend: BaseMemoryBackend = None):
        self.backend = backend or InMemoryBackend()
        self.capacity_limits = {
            MemoryType.SHORT_TERM: 100,
            MemoryType.LONG_TERM: 10000,
            MemoryType.EPISODIC: 1000,
            MemoryType.SEMANTIC: 5000,
            MemoryType.WORKING: 10
        }
    
    async def add_memory(self, content: str, memory_type: MemoryType = MemoryType.SHORT_TERM, 
                       importance: float = 0.5, tags: List[str] = None, 
                       metadata: Dict[str, Any] = None) -> str:
        """添加记忆"""
        import uuid
        memory_id = str(uuid.uuid4())
        
        chunk = MemoryChunk(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        success = await self.backend.store(chunk)
        if success:
            # 检查容量限制并清理
            await self._check_capacity(memory_type)
            return memory_id
        else:
            return None
    
    async def _check_capacity(self, memory_type: MemoryType):
        """检查并清理超出容量的记忆"""
        # 简单的清理策略：删除最不重要的记忆
        all_memories = await self.backend.search_by_tags([], top_k=self.capacity_limits[memory_type] * 2)
        
        if len(all_memories) > self.capacity_limits[memory_type]:
            # 使用堆来高效找到需要删除的记忆，而不是对整个列表排序
            import heapq
            # 使用最小堆来找到重要性最低的记忆
            min_heap = [(chunk.importance, chunk.id) for chunk in all_memories]
            heapq.heapify(min_heap)
            
            # 删除超出容量的记忆
            to_remove_count = len(all_memories) - self.capacity_limits[memory_type]
            to_remove = []
            for _ in range(to_remove_count):
                if min_heap:
                    _, chunk_id = heapq.heappop(min_heap)
                    to_remove.append(chunk_id)
            
            # 批量删除
            for chunk_id in to_remove:
                await self.backend.delete(chunk_id)
    
    async def retrieve_memories(self, query: str, memory_type: MemoryType = None, 
                              top_k: int = 5) -> List[MemoryChunk]:
        """检索记忆"""
        results = await self.backend.retrieve(query, top_k)
        
        if memory_type:
            results = [r for r in results if r.memory_type == memory_type]
        
        return results
    
    async def get_memory_by_id(self, memory_id: str) -> Optional[MemoryChunk]:
        """通过ID获取记忆"""
        results = await self.retrieve_memories(memory_id, top_k=1)
        return results[0] if results else None
    
    async def update_memory(self, memory_id: str, content: str = None, 
                           importance: float = None, tags: List[str] = None) -> bool:
        """更新记忆"""
        chunk = await self.get_memory_by_id(memory_id)
        if not chunk:
            return False
        
        if content is not None:
            chunk.content = content
        if importance is not None:
            chunk.importance = importance
        if tags is not None:
            chunk.tags = tags
        
        return await self.backend.update(chunk)
    
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        return await self.backend.delete(memory_id)
    
    async def search_by_tags(self, tags: List[str], top_k: int = 10) -> List[MemoryChunk]:
        """按标签搜索记忆"""
        return await self.backend.search_by_tags(tags, top_k)
    
    async def get_statistics(self) -> Dict[str, int]:
        """获取记忆统计信息"""
        stats = {}
        for mem_type in MemoryType:
            # 这里需要一个能够统计特定类型记忆数量的方法
            # 由于当前后端接口限制，我们简单地返回0
            # 在实际实现中，应该在后端添加相应的统计方法
            all_memories = await self.backend.search_by_tags([], top_k=10000)
            count = len([m for m in all_memories if m.memory_type == mem_type])
            stats[mem_type.value] = count
        return stats


class ConversationMemory:
    """对话记忆管理"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.conversation_id = None
    
    async def start_conversation(self, title: str = "") -> str:
        """开始新对话"""
        import uuid
        self.conversation_id = str(uuid.uuid4())
        
        # 存储对话开始事件
        await self.memory_manager.add_memory(
            content=f"对话开始: {title or '未命名对话'}",
            memory_type=MemoryType.EPISODIC,
            tags=["conversation", "start", self.conversation_id]
        )
        
        return self.conversation_id
    
    async def store_message(self, message: Message) -> str:
        """存储消息到记忆"""
        if not self.conversation_id:
            await self.start_conversation("临时对话")
        
        content = f"{message.role}: {message.content}"
        metadata = {
            "conversation_id": self.conversation_id,
            "role": message.role,
            "timestamp": message.timestamp.isoformat() if hasattr(message, 'timestamp') else None
        }
        
        return await self.memory_manager.add_memory(
            content=content,
            memory_type=MemoryType.SHORT_TERM,
            tags=["message", "conversation", self.conversation_id],
            metadata=metadata
        )
    
    async def get_conversation_history(self, limit: int = 50) -> List[Message]:
        """获取对话历史"""
        if not self.conversation_id:
            return []
        
        memories = await self.memory_manager.search_by_tags(
            ["message", self.conversation_id], 
            top_k=limit
        )
        
        # 将记忆转换为Message对象
        messages = []
        for mem in memories:
            # 简单解析role和content
            if ':' in mem.content:
                role, content = mem.content.split(':', 1)
                role = role.strip()
                content = content.strip()
            else:
                role = "unknown"
                content = mem.content
            
            # 创建简单的Message对象
            msg = Message(role=role, content=content)
            messages.append(msg)
        
        return messages
    
    async def summarize_conversation(self) -> str:
        """总结对话"""
        messages = await self.get_conversation_history(limit=100)
        if not messages:
            return "没有对话历史可总结"
        
        # 简单的总结策略：提取关键句子
        all_content = " ".join([msg.content for msg in messages])
        
        # 这里应该使用更复杂的总结算法
        # 为了简化，我们只返回内容的前几句
        sentences = all_content.split('.')
        summary = '.'.join(sentences[:3]) + '.' if len(sentences) >= 3 else all_content
        
        # 将总结存储为长期记忆
        await self.memory_manager.add_memory(
            content=f"对话总结: {summary}",
            memory_type=MemoryType.LONG_TERM,
            tags=["summary", "conversation", self.conversation_id],
            importance=0.8
        )
        
        return summary