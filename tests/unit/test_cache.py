"""响应缓存系统测试"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from xiaotie.cache import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    MemoryBackend,
    ResponseCache,
    SQLiteBackend,
    compute_cache_key,
)


class TestCacheConfig:
    """CacheConfig 测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CacheConfig()
        assert config.enabled is True
        assert config.backend == "memory"
        assert config.ttl == 3600
        assert config.max_size == 1000

    def test_custom_config(self):
        """测试自定义配置"""
        config = CacheConfig(
            enabled=False,
            backend="sqlite",
            ttl=7200,
            max_size=500,
        )
        assert config.enabled is False
        assert config.backend == "sqlite"
        assert config.ttl == 7200
        assert config.max_size == 500

    def test_invalid_backend(self):
        """测试无效后端"""
        with pytest.raises(ValueError, match="Unknown cache backend"):
            CacheConfig(backend="invalid")


class TestCacheEntry:
    """CacheEntry 测试"""

    def test_create_entry(self):
        """测试创建条目"""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time(),
            ttl=3600,
        )
        assert entry.key == "test-key"
        assert entry.value == "test-value"
        assert entry.is_expired is False

    def test_expired_entry(self):
        """测试过期条目"""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time() - 7200,  # 2 小时前
            ttl=3600,  # 1 小时 TTL
        )
        assert entry.is_expired is True

    def test_to_dict_and_from_dict(self):
        """测试序列化"""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=1234567890.0,
            ttl=3600,
            metadata={"model": "gpt-4"},
        )
        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.key == entry.key
        assert restored.value == entry.value
        assert restored.metadata == entry.metadata


class TestCacheStats:
    """CacheStats 测试"""

    def test_initial_stats(self):
        """测试初始统计"""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """测试命中率计算"""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_to_dict(self):
        """测试转换为字典"""
        stats = CacheStats(hits=10, misses=5, evictions=2, size=100)
        data = stats.to_dict()
        assert data["hits"] == 10
        assert data["misses"] == 5
        assert data["hit_rate"] == "66.67%"


class TestComputeCacheKey:
    """compute_cache_key 测试"""

    def test_same_input_same_key(self):
        """测试相同输入产生相同键"""
        messages = [{"role": "user", "content": "Hello"}]
        key1 = compute_cache_key(messages, "gpt-4", "openai")
        key2 = compute_cache_key(messages, "gpt-4", "openai")
        assert key1 == key2

    def test_different_messages_different_key(self):
        """测试不同消息产生不同键"""
        key1 = compute_cache_key([{"role": "user", "content": "Hello"}], "gpt-4", "openai")
        key2 = compute_cache_key([{"role": "user", "content": "Hi"}], "gpt-4", "openai")
        assert key1 != key2

    def test_different_model_different_key(self):
        """测试不同模型产生不同键"""
        messages = [{"role": "user", "content": "Hello"}]
        key1 = compute_cache_key(messages, "gpt-4", "openai")
        key2 = compute_cache_key(messages, "gpt-3.5", "openai")
        assert key1 != key2

    def test_key_is_md5_hash(self):
        """测试键是 MD5 哈希"""
        messages = [{"role": "user", "content": "Hello"}]
        key = compute_cache_key(messages, "gpt-4", "openai")
        assert len(key) == 32  # MD5 哈希长度
        assert all(c in "0123456789abcdef" for c in key)


class TestMemoryBackend:
    """MemoryBackend 测试"""

    def test_set_and_get(self):
        """测试设置和获取"""
        backend = MemoryBackend()
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time(),
            ttl=3600,
        )
        backend.set(entry)
        result = backend.get("test-key")
        assert result is not None
        assert result.value == "test-value"

    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        backend = MemoryBackend()
        result = backend.get("nonexistent")
        assert result is None

    def test_delete(self):
        """测试删除"""
        backend = MemoryBackend()
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time(),
            ttl=3600,
        )
        backend.set(entry)
        assert backend.delete("test-key") is True
        assert backend.get("test-key") is None

    def test_clear(self):
        """测试清空"""
        backend = MemoryBackend()
        for i in range(5):
            entry = CacheEntry(
                key=f"key-{i}",
                value=f"value-{i}",
                created_at=time.time(),
                ttl=3600,
            )
            backend.set(entry)
        count = backend.clear()
        assert count == 5
        assert backend.size() == 0

    def test_lru_eviction(self):
        """测试 LRU 驱逐"""
        backend = MemoryBackend(max_size=3)
        for i in range(5):
            entry = CacheEntry(
                key=f"key-{i}",
                value=f"value-{i}",
                created_at=time.time(),
                ttl=3600,
            )
            backend.set(entry)
        assert backend.size() == 3
        # 最早的键应该被驱逐
        assert backend.get("key-0") is None
        assert backend.get("key-1") is None
        assert backend.get("key-4") is not None

    def test_expired_entry_cleanup(self):
        """测试过期条目清理"""
        backend = MemoryBackend()
        entry = CacheEntry(
            key="expired-key",
            value="value",
            created_at=time.time() - 7200,
            ttl=3600,
        )
        backend.set(entry)
        # 获取时应该返回 None 并删除
        result = backend.get("expired-key")
        assert result is None
        assert backend.size() == 0


class TestSQLiteBackend:
    """SQLiteBackend 测试"""

    @pytest.fixture
    def backend(self):
        """创建临时 SQLite 后端"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            yield SQLiteBackend(str(db_path))

    def test_set_and_get(self, backend):
        """测试设置和获取"""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time(),
            ttl=3600,
        )
        backend.set(entry)
        result = backend.get("test-key")
        assert result is not None
        assert result.value == "test-value"

    def test_get_nonexistent(self, backend):
        """测试获取不存在的键"""
        result = backend.get("nonexistent")
        assert result is None

    def test_delete(self, backend):
        """测试删除"""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            created_at=time.time(),
            ttl=3600,
        )
        backend.set(entry)
        assert backend.delete("test-key") is True
        assert backend.get("test-key") is None

    def test_clear(self, backend):
        """测试清空"""
        for i in range(5):
            entry = CacheEntry(
                key=f"key-{i}",
                value=f"value-{i}",
                created_at=time.time(),
                ttl=3600,
            )
            backend.set(entry)
        count = backend.clear()
        assert count == 5
        assert backend.size() == 0

    def test_cleanup_expired(self, backend):
        """测试清理过期条目"""
        # 添加过期条目
        expired_entry = CacheEntry(
            key="expired",
            value="value",
            created_at=time.time() - 7200,
            ttl=3600,
        )
        backend.set(expired_entry)

        # 添加有效条目
        valid_entry = CacheEntry(
            key="valid",
            value="value",
            created_at=time.time(),
            ttl=3600,
        )
        backend.set(valid_entry)

        count = backend.cleanup_expired()
        assert count == 1
        assert backend.get("expired") is None
        assert backend.get("valid") is not None


class TestResponseCache:
    """ResponseCache 测试"""

    def test_disabled_cache(self):
        """测试禁用缓存"""
        cache = ResponseCache(CacheConfig(enabled=False))
        cache.set("key", "value")
        result = cache.get("key")
        assert result is None

    def test_memory_cache(self):
        """测试内存缓存"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        cache.set("key", "value")
        result = cache.get("key")
        assert result == "value"

    def test_sqlite_cache(self):
        """测试 SQLite 缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "cache.db"
            cache = ResponseCache(CacheConfig(backend="sqlite", db_path=str(db_path)))
            cache.set("key", "value")
            result = cache.get("key")
            assert result == "value"

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        cache.set("key", "value")

        # 命中
        cache.get("key")
        # 未命中
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_cache_with_metadata(self):
        """测试带元数据的缓存"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        cache.set("key", "value", metadata={"model": "gpt-4", "tokens": 100})
        result = cache.get("key")
        assert result == "value"

    def test_cache_contains(self):
        """测试 contains 操作"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        cache.set("key", "value")
        assert "key" in cache
        assert "nonexistent" not in cache

    def test_cache_delete(self):
        """测试删除"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_cache_clear(self):
        """测试清空"""
        cache = ResponseCache(CacheConfig(backend="memory"))
        for i in range(5):
            cache.set(f"key-{i}", f"value-{i}")
        count = cache.clear()
        assert count == 5
        stats = cache.get_stats()
        assert stats.size == 0


class TestCacheIntegration:
    """缓存集成测试"""

    def test_llm_response_caching_flow(self):
        """测试 LLM 响应缓存流程"""
        cache = ResponseCache(CacheConfig(backend="memory"))

        # 模拟 LLM 调用
        messages = [{"role": "user", "content": "What is 2+2?"}]
        model = "gpt-4"
        provider = "openai"

        # 计算缓存键
        key = compute_cache_key(messages, model, provider)

        # 第一次调用 - 缓存未命中
        cached = cache.get(key)
        assert cached is None

        # 模拟 API 响应
        response = "The answer is 4."
        cache.set(key, response, metadata={"model": model, "provider": provider})

        # 第二次调用 - 缓存命中
        cached = cache.get(key)
        assert cached == response

        # 验证统计
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_different_params_different_cache(self):
        """测试不同参数使用不同缓存"""
        cache = ResponseCache(CacheConfig(backend="memory"))

        messages = [{"role": "user", "content": "Hello"}]

        # 不同温度参数
        key1 = compute_cache_key(messages, "gpt-4", "openai", temperature=0.0)
        key2 = compute_cache_key(messages, "gpt-4", "openai", temperature=1.0)

        cache.set(key1, "Response with temp=0")
        cache.set(key2, "Response with temp=1")

        assert cache.get(key1) == "Response with temp=0"
        assert cache.get(key2) == "Response with temp=1"
