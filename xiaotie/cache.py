"""
缓存系统

实现了基于LRU和TTL的缓存机制
支持异步操作和线程安全
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    timestamp: float
    ttl: float


class AsyncLRUCache:
    """异步LRU缓存实现（带清理间隔优化）"""

    def __init__(
        self, max_size: int = 1000, default_ttl: float = 3600.0, cleanup_interval: float = 60.0
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._last_cleanup: float = 0.0

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            # 检查是否过期
            if current_time - entry.timestamp > entry.ttl:
                del self._cache[key]
                return None

            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        async with self._lock:
            # 仅在超过清理间隔时执行全量过期扫描
            now = time.time()
            if now - self._last_cleanup >= self.cleanup_interval:
                self._cleanup_expired_unlocked(now)
                self._last_cleanup = now

            if ttl is None:
                ttl = self.default_ttl

            self._cache[key] = CacheEntry(value=value, timestamp=now, ttl=ttl)

            # 如果超出大小限制，移除最老的项
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    async def delete(self, key: str) -> bool:
        """删除缓存项"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._last_cleanup = 0.0

    def _cleanup_expired_unlocked(self, current_time: Optional[float] = None):
        """清理过期项（调用方需持有锁）"""
        if current_time is None:
            current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items() if current_time - entry.timestamp > entry.ttl
        ]
        for key in expired_keys:
            del self._cache[key]

    async def _cleanup_expired(self):
        """清理过期项（兼容旧接口）"""
        self._cleanup_expired_unlocked()

    async def size(self) -> int:
        """获取缓存大小"""
        async with self._lock:
            self._cleanup_expired_unlocked()
            return len(self._cache)

    async def keys(self) -> list:
        """获取所有键"""
        async with self._lock:
            self._cleanup_expired_unlocked()
            return list(self._cache.keys())


# 全局缓存实例
_global_cache: Optional[AsyncLRUCache] = None


def get_global_cache() -> AsyncLRUCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        from .config import Config  # 延迟导入避免循环依赖

        try:
            config = Config.load()
            _global_cache = AsyncLRUCache(
                max_size=config.agent.cache_config.max_size,
                default_ttl=config.agent.cache_config.ttl_seconds,
            )
        except Exception:
            # 如果无法加载配置，使用默认值
            _global_cache = AsyncLRUCache()
    return _global_cache


def cache_result(ttl: Optional[float] = None):
    """装饰器：缓存函数结果"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成稳定的缓存键
            key_source = (
                f"{func.__module__}.{func.__qualname__}:{repr(args)}:{repr(sorted(kwargs.items()))}"
            )
            cache_key = hashlib.md5(key_source.encode()).hexdigest()

            cache = get_global_cache()

            # 尝试从缓存获取
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
