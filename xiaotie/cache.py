"""响应缓存系统

提供 LLM 响应缓存功能，减少重复 API 调用：
- 多后端支持 (SQLite/Memory/Redis)
- TTL 过期策略
- 请求指纹计算
- 缓存命中率统计
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    backend: str = "memory"  # memory/sqlite/redis
    ttl: int = 3600  # 秒
    max_size: int = 1000  # 最大缓存条目数
    db_path: str = "~/.xiaotie/cache.db"  # SQLite 路径
    redis_url: str = "redis://localhost:6379"  # Redis URL

    def __post_init__(self):
        if self.backend not in ("memory", "sqlite", "redis"):
            raise ValueError(f"Unknown cache backend: {self.backend}")


@dataclass
class CacheEntry:
    """缓存条目"""

    key: str
    value: str
    created_at: float
    ttl: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.created_at + self.ttl

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """从字典创建"""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=data["created_at"],
            ttl=data["ttl"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class CacheStats:
    """缓存统计"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "hit_rate": f"{self.hit_rate:.2%}",
        }


def compute_cache_key(
    messages: List[Dict[str, Any]],
    model: str,
    provider: str,
    **kwargs,
) -> str:
    """计算缓存键

    基于消息内容、模型和 provider 生成唯一键
    """
    # 构建用于哈希的数据
    data = {
        "messages": messages,
        "model": model,
        "provider": provider,
        # 包含影响输出的参数
        "temperature": kwargs.get("temperature"),
        "max_tokens": kwargs.get("max_tokens"),
        "tools": kwargs.get("tools"),
    }

    # 序列化并计算 MD5
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(serialized.encode()).hexdigest()


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存"""
        pass

    @abstractmethod
    def set(self, entry: CacheEntry) -> None:
        """设置缓存"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass

    @abstractmethod
    def clear(self) -> int:
        """清空缓存，返回删除数量"""
        pass

    @abstractmethod
    def size(self) -> int:
        """返回缓存大小"""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """清理过期条目，返回删除数量"""
        pass


class MemoryBackend(CacheBackend):
    """内存缓存后端"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # LRU 顺序

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired:
            self.delete(key)
            return None

        # 更新 LRU 顺序
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return entry

    def set(self, entry: CacheEntry) -> None:
        # 检查是否需要驱逐
        while len(self._cache) >= self.max_size:
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                self._cache.pop(oldest_key, None)

        self._cache[entry.key] = entry
        if entry.key in self._access_order:
            self._access_order.remove(entry.key)
        self._access_order.append(entry.key)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        return count

    def size(self) -> int:
        return len(self._cache)

    def cleanup_expired(self) -> int:
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            self.delete(key)
        return len(expired_keys)


class SQLiteBackend(CacheBackend):
    """SQLite 缓存后端"""

    def __init__(self, db_path: str, max_size: int = 1000):
        self.db_path = Path(db_path).expanduser()
        self.max_size = max_size
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl INTEGER NOT NULL,
                    metadata TEXT,
                    accessed_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_accessed_at ON cache(accessed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(created_at + ttl)")
            conn.commit()

    def get(self, key: str) -> Optional[CacheEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key, value, created_at, ttl, metadata FROM cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            entry = CacheEntry(
                key=row[0],
                value=row[1],
                created_at=row[2],
                ttl=row[3],
                metadata=json.loads(row[4]) if row[4] else {},
            )

            if entry.is_expired:
                self.delete(key)
                return None

            # 更新访问时间
            conn.execute(
                "UPDATE cache SET accessed_at = ? WHERE key = ?",
                (time.time(), key),
            )
            conn.commit()

            return entry

    def set(self, entry: CacheEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            # 检查是否需要驱逐
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]

            while count >= self.max_size:
                # 删除最旧的条目
                conn.execute("""
                    DELETE FROM cache WHERE key = (
                        SELECT key FROM cache ORDER BY accessed_at ASC LIMIT 1
                    )
                """)
                count -= 1

            # 插入或更新
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, created_at, ttl, metadata, accessed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.key,
                    entry.value,
                    entry.created_at,
                    entry.ttl,
                    json.dumps(entry.metadata),
                    time.time(),
                ),
            )
            conn.commit()

    def delete(self, key: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache")
            conn.commit()
            return cursor.rowcount

    def size(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            return cursor.fetchone()[0]

    def cleanup_expired(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE created_at + ttl < ?",
                (time.time(),),
            )
            conn.commit()
            return cursor.rowcount


class ResponseCache:
    """LLM 响应缓存

    使用示例:
    ```python
    cache = ResponseCache(CacheConfig(backend="sqlite"))

    # 检查缓存
    key = compute_cache_key(messages, model, provider)
    cached = cache.get(key)
    if cached:
        return cached

    # 调用 API
    response = await llm.generate(messages)

    # 存入缓存
    cache.set(key, response, metadata={"model": model})
    ```
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self._backend = self._create_backend()

    def _create_backend(self) -> CacheBackend:
        """创建缓存后端"""
        if self.config.backend == "memory":
            return MemoryBackend(max_size=self.config.max_size)
        elif self.config.backend == "sqlite":
            return SQLiteBackend(
                db_path=self.config.db_path,
                max_size=self.config.max_size,
            )
        elif self.config.backend == "redis":
            # Redis 后端需要额外依赖，延迟导入
            raise NotImplementedError("Redis backend not yet implemented")
        else:
            raise ValueError(f"Unknown backend: {self.config.backend}")

    def get(self, key: str) -> Optional[str]:
        """获取缓存的响应"""
        if not self.config.enabled:
            return None

        entry = self._backend.get(key)
        if entry is not None:
            self.stats.hits += 1
            return entry.value
        else:
            self.stats.misses += 1
            return None

    def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """设置缓存"""
        if not self.config.enabled:
            return

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl or self.config.ttl,
            metadata=metadata or {},
        )
        self._backend.set(entry)
        self.stats.size = self._backend.size()

    def delete(self, key: str) -> bool:
        """删除缓存"""
        result = self._backend.delete(key)
        self.stats.size = self._backend.size()
        return result

    def clear(self) -> int:
        """清空缓存"""
        count = self._backend.clear()
        self.stats.evictions += count
        self.stats.size = 0
        return count

    def cleanup(self) -> int:
        """清理过期条目"""
        count = self._backend.cleanup_expired()
        self.stats.evictions += count
        self.stats.size = self._backend.size()
        return count

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        self.stats.size = self._backend.size()
        return self.stats

    def __contains__(self, key: str) -> bool:
        """检查键是否存在"""
        return self._backend.get(key) is not None
