"""memory/core.py 单元测试"""

import asyncio
import time

import pytest

from xiaotie.memory.core import (
    MemoryType,
    MemoryChunk,
    InMemoryBackend,
    MemoryManager,
    ConversationMemory,
)
from xiaotie.schema import Message


# ---------------------------------------------------------------------------
# MemoryChunk dataclass
# ---------------------------------------------------------------------------


class TestMemoryChunk:
    def test_defaults(self):
        chunk = MemoryChunk(id="1", content="hello")
        assert chunk.metadata == {}
        assert chunk.tags == []
        assert chunk.importance == 0.5
        assert chunk.memory_type == MemoryType.SHORT_TERM
        assert chunk.timestamp > 0

    def test_custom_values(self):
        chunk = MemoryChunk(
            id="2",
            content="world",
            importance=0.9,
            tags=["a", "b"],
            memory_type=MemoryType.LONG_TERM,
            timestamp=100.0,
        )
        assert chunk.importance == 0.9
        assert chunk.tags == ["a", "b"]
        assert chunk.timestamp == 100.0


# ---------------------------------------------------------------------------
# InMemoryBackend
# ---------------------------------------------------------------------------


class TestInMemoryBackend:
    @pytest.fixture
    def backend(self):
        return InMemoryBackend()

    @pytest.fixture
    def sample_chunk(self):
        return MemoryChunk(
            id="c1",
            content="python programming language",
            tags=["code", "python"],
            importance=0.8,
        )

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, backend, sample_chunk):
        assert await backend.store(sample_chunk)
        results = await backend.retrieve("python", top_k=5)
        assert len(results) >= 1
        assert results[0].id == "c1"

    @pytest.mark.asyncio
    async def test_store_overwrites_existing(self, backend):
        c = MemoryChunk(id="x", content="old content", tags=["t"])
        await backend.store(c)
        c2 = MemoryChunk(id="x", content="new content", tags=["t"])
        await backend.store(c2)
        assert backend.memory_store["x"].content == "new content"

    @pytest.mark.asyncio
    async def test_retrieve_empty(self, backend):
        results = await backend.retrieve("nothing", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_respects_top_k(self, backend):
        for i in range(10):
            await backend.store(
                MemoryChunk(id=f"m{i}", content=f"test item {i}", tags=["test"])
            )
        results = await backend.retrieve("test", top_k=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_update_existing(self, backend, sample_chunk):
        await backend.store(sample_chunk)
        updated = MemoryChunk(
            id="c1",
            content="rust programming language",
            tags=["code", "rust"],
            importance=0.9,
        )
        assert await backend.update(updated)
        assert backend.memory_store["c1"].content == "rust programming language"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_false(self, backend):
        chunk = MemoryChunk(id="missing", content="nope")
        assert not await backend.update(chunk)

    @pytest.mark.asyncio
    async def test_delete_existing(self, backend, sample_chunk):
        await backend.store(sample_chunk)
        assert await backend.delete("c1")
        assert "c1" not in backend.memory_store

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, backend):
        assert not await backend.delete("missing")

    @pytest.mark.asyncio
    async def test_search_by_tags(self, backend):
        await backend.store(
            MemoryChunk(id="a", content="alpha", tags=["greek"])
        )
        await backend.store(
            MemoryChunk(id="b", content="beta", tags=["greek", "second"])
        )
        await backend.store(
            MemoryChunk(id="c", content="gamma", tags=["greek"])
        )
        results = await backend.search_by_tags(["greek"])
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_by_tags_respects_top_k(self, backend):
        for i in range(20):
            await backend.store(
                MemoryChunk(id=f"t{i}", content=f"item {i}", tags=["bulk"])
            )
        results = await backend.search_by_tags(["bulk"], top_k=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_by_tags_empty(self, backend):
        results = await backend.search_by_tags(["nonexistent"])
        assert results == []

    @pytest.mark.asyncio
    async def test_word_index_cleanup_on_delete(self, backend):
        chunk = MemoryChunk(id="w1", content="unique_word_xyz", tags=[])
        await backend.store(chunk)
        assert "unique_word_xyz" in backend._word_index
        await backend.delete("w1")
        assert "unique_word_xyz" not in backend._word_index

    @pytest.mark.asyncio
    async def test_retrieve_scores_by_tag_match(self, backend):
        await backend.store(
            MemoryChunk(id="t1", content="something", tags=["python"])
        )
        results = await backend.retrieve("python", top_k=5)
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class TestMemoryManager:
    @pytest.fixture
    def manager(self):
        return MemoryManager(backend=InMemoryBackend())

    @pytest.mark.asyncio
    async def test_add_memory_returns_id(self, manager):
        mid = await manager.add_memory("test content")
        assert mid is not None
        assert isinstance(mid, str)

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self, manager):
        await manager.add_memory("hello world", tags=["greet"])
        results = await manager.retrieve_memories("hello")
        assert len(results) >= 1
        assert "hello world" in results[0].content

    @pytest.mark.asyncio
    async def test_retrieve_with_type_filter(self, manager):
        await manager.add_memory("short mem", memory_type=MemoryType.SHORT_TERM)
        await manager.add_memory("long mem", memory_type=MemoryType.LONG_TERM)
        results = await manager.retrieve_memories("mem", memory_type=MemoryType.LONG_TERM)
        for r in results:
            assert r.memory_type == MemoryType.LONG_TERM

    @pytest.mark.asyncio
    async def test_delete_memory(self, manager):
        mid = await manager.add_memory("to delete")
        assert await manager.delete_memory(mid)

    @pytest.mark.asyncio
    async def test_search_by_tags(self, manager):
        await manager.add_memory("tagged", tags=["special"])
        results = await manager.search_by_tags(["special"])
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_statistics(self, manager):
        await manager.add_memory("stat test", memory_type=MemoryType.WORKING)
        stats = await manager.get_statistics()
        assert isinstance(stats, dict)
        assert "working" in stats


# ---------------------------------------------------------------------------
# ConversationMemory
# ---------------------------------------------------------------------------


class TestConversationMemory:
    @pytest.fixture
    def conv_memory(self):
        manager = MemoryManager(backend=InMemoryBackend())
        return ConversationMemory(memory_manager=manager)

    @pytest.mark.asyncio
    async def test_start_conversation(self, conv_memory):
        cid = await conv_memory.start_conversation("Test chat")
        assert cid is not None
        assert conv_memory.conversation_id == cid

    @pytest.mark.asyncio
    async def test_store_message(self, conv_memory):
        await conv_memory.start_conversation("chat")
        msg = Message(role="user", content="hi there")
        mid = await conv_memory.store_message(msg)
        assert mid is not None

    @pytest.mark.asyncio
    async def test_store_message_auto_starts_conversation(self, conv_memory):
        assert conv_memory.conversation_id is None
        msg = Message(role="user", content="auto start")
        await conv_memory.store_message(msg)
        assert conv_memory.conversation_id is not None

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conv_memory):
        await conv_memory.start_conversation("hist")
        await conv_memory.store_message(Message(role="user", content="msg1"))
        await conv_memory.store_message(Message(role="assistant", content="msg2"))
        history = await conv_memory.get_conversation_history()
        assert len(history) >= 2

    @pytest.mark.asyncio
    async def test_get_history_no_conversation(self, conv_memory):
        history = await conv_memory.get_conversation_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_summarize_conversation(self, conv_memory):
        await conv_memory.start_conversation("sum")
        await conv_memory.store_message(Message(role="user", content="First sentence. Second sentence. Third sentence."))
        summary = await conv_memory.summarize_conversation()
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_summarize_empty_conversation(self, conv_memory):
        # Note: start_conversation stores an episodic memory, so only
        # a truly unstarted conversation returns the "no history" message.
        summary = await conv_memory.summarize_conversation()
        assert summary == "没有对话历史可总结"
