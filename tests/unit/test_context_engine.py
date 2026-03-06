"""ContextEngine unit tests.

Tests cover:
- Token budget allocation and enforcement
- Block priority-based trimming
- Conversation splitting (recent vs old)
- Memory context building
- Repo map trimming
- Context compaction
- ContextBundle.to_messages conversion
"""

from __future__ import annotations

import pytest

from xiaotie.context_engine import (
    BlockPriority,
    ContextBlock,
    ContextBundle,
    ContextEngine,
    TokenBudget,
    TokenCounter,
)
from xiaotie.schema import Message


# ---------------------------------------------------------------------------
# TokenCounter
# ---------------------------------------------------------------------------


class TestTokenCounter:
    def test_count_empty(self):
        counter = TokenCounter()
        assert counter.count("") == 0
        assert counter.count(None) == 0

    def test_count_returns_positive_for_text(self):
        counter = TokenCounter()
        result = counter.count("hello world, this is a test")
        assert result > 0

    def test_count_longer_text_more_tokens(self):
        counter = TokenCounter()
        short = counter.count("hi")
        long = counter.count("this is a much longer piece of text with many words")
        assert long > short


# ---------------------------------------------------------------------------
# TokenBudget
# ---------------------------------------------------------------------------


class TestTokenBudget:
    def test_used_and_remaining(self):
        b = TokenBudget(total=1000, system=100, repo_map=200, memory=150, conversation=300, skills=50)
        assert b.used == 800
        assert b.remaining == 200

    def test_remaining_never_negative(self):
        b = TokenBudget(total=100, system=200)
        assert b.remaining == 0


# ---------------------------------------------------------------------------
# ContextEngine - set_budget
# ---------------------------------------------------------------------------


class TestContextEngineBudget:
    def test_set_budget(self):
        engine = ContextEngine(token_budget=50000)
        assert engine.budget == 50000
        engine.set_budget(80000)
        assert engine.budget == 80000

    def test_set_budget_minimum(self):
        engine = ContextEngine()
        engine.set_budget(0)
        assert engine.budget == 1
        engine.set_budget(-100)
        assert engine.budget == 1


# ---------------------------------------------------------------------------
# compose_context - basic
# ---------------------------------------------------------------------------


class TestComposeContext:
    @pytest.mark.asyncio
    async def test_empty_context(self):
        engine = ContextEngine(token_budget=10000)
        bundle = await engine.compose_context(query="test")
        assert isinstance(bundle, ContextBundle)
        assert len(bundle.blocks) == 0
        assert bundle.token_usage.used == 0

    @pytest.mark.asyncio
    async def test_system_prompt_included(self):
        engine = ContextEngine(token_budget=10000)
        bundle = await engine.compose_context(
            query="test",
            system_prompt="You are a helpful assistant.",
        )
        assert len(bundle.blocks) == 1
        assert bundle.blocks[0].priority == BlockPriority.SYSTEM
        assert bundle.blocks[0].content == "You are a helpful assistant."
        assert bundle.token_usage.system > 0

    @pytest.mark.asyncio
    async def test_repo_map_included(self):
        engine = ContextEngine(token_budget=100000)
        repo_map = "src/main.py: class App\nsrc/utils.py: def helper"
        bundle = await engine.compose_context(
            query="test",
            repo_map=repo_map,
        )
        repo_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.REPO_MAP]
        assert len(repo_blocks) == 1
        assert bundle.token_usage.repo_map > 0

    @pytest.mark.asyncio
    async def test_memory_chunks_included(self):
        engine = ContextEngine(token_budget=100000)

        class FakeChunk:
            def __init__(self, content, importance=0.5):
                self.content = content
                self.importance = importance

        chunks = [
            FakeChunk("Uses JWT for auth", importance=0.9),
            FakeChunk("Database is PostgreSQL", importance=0.7),
        ]
        bundle = await engine.compose_context(
            query="test",
            memory_chunks=chunks,
        )
        mem_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.MEMORY]
        assert len(mem_blocks) == 1
        assert "JWT" in mem_blocks[0].content
        assert bundle.token_usage.memory > 0

    @pytest.mark.asyncio
    async def test_memory_sorted_by_importance(self):
        engine = ContextEngine(token_budget=100000)

        class FakeChunk:
            def __init__(self, content, importance):
                self.content = content
                self.importance = importance

        chunks = [
            FakeChunk("low importance", importance=0.1),
            FakeChunk("high importance", importance=0.9),
        ]
        bundle = await engine.compose_context(query="test", memory_chunks=chunks)
        mem_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.MEMORY]
        # High importance should come first in the content
        assert mem_blocks[0].content.index("high importance") < mem_blocks[0].content.index("low importance")

    @pytest.mark.asyncio
    async def test_skills_metadata_included(self):
        engine = ContextEngine(token_budget=100000)
        bundle = await engine.compose_context(
            query="test",
            skills_metadata="Available: bash, python, git",
        )
        skills_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.SKILLS]
        assert len(skills_blocks) == 1


# ---------------------------------------------------------------------------
# compose_context - conversation handling
# ---------------------------------------------------------------------------


class TestConversationHandling:
    @pytest.mark.asyncio
    async def test_conversation_messages_split(self):
        """Messages should be split into recent (last 6) and old."""
        engine = ContextEngine(token_budget=100000)
        msgs = [Message(role="user", content=f"message {i}") for i in range(10)]
        bundle = await engine.compose_context(query="test", conversation=msgs)

        recent = [b for b in bundle.blocks if b.priority == BlockPriority.CONVERSATION_RECENT]
        old = [b for b in bundle.blocks if b.priority == BlockPriority.CONVERSATION_OLD]
        assert len(recent) == 6
        assert len(old) == 4

    @pytest.mark.asyncio
    async def test_few_messages_all_recent(self):
        """With <= 6 messages, all should be recent priority."""
        engine = ContextEngine(token_budget=100000)
        msgs = [Message(role="user", content="hi"), Message(role="assistant", content="hello")]
        bundle = await engine.compose_context(query="test", conversation=msgs)

        recent = [b for b in bundle.blocks if b.priority == BlockPriority.CONVERSATION_RECENT]
        old = [b for b in bundle.blocks if b.priority == BlockPriority.CONVERSATION_OLD]
        assert len(recent) == 2
        assert len(old) == 0

    @pytest.mark.asyncio
    async def test_system_messages_excluded_from_conversation(self):
        """System messages in conversation list should be skipped (handled separately)."""
        engine = ContextEngine(token_budget=100000)
        msgs = [
            Message(role="system", content="system prompt"),
            Message(role="user", content="hello"),
        ]
        bundle = await engine.compose_context(query="test", conversation=msgs)
        conv_blocks = [
            b for b in bundle.blocks
            if b.priority in (BlockPriority.CONVERSATION_RECENT, BlockPriority.CONVERSATION_OLD)
        ]
        assert len(conv_blocks) == 1
        assert "hello" in conv_blocks[0].content


# ---------------------------------------------------------------------------
# Budget enforcement - trimming
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_blocks_trimmed_when_over_budget(self):
        """With a tiny budget, lowest-priority blocks should be dropped."""
        engine = ContextEngine(token_budget=50)
        bundle = await engine.compose_context(
            query="test",
            system_prompt="You are helpful.",
            repo_map="a" * 500,
            skills_metadata="skill info " * 50,
            conversation=[Message(role="user", content="x" * 500)],
        )
        total = sum(b.token_count for b in bundle.blocks)
        assert total <= 50

    @pytest.mark.asyncio
    async def test_system_prompt_survives_trimming(self):
        """System prompt has highest priority and should survive trimming."""
        engine = ContextEngine(token_budget=100)
        bundle = await engine.compose_context(
            query="test",
            system_prompt="short system",
            repo_map="x" * 2000,
            skills_metadata="y" * 2000,
        )
        sys_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.SYSTEM]
        assert len(sys_blocks) == 1

    @pytest.mark.asyncio
    async def test_remaining_budget_accurate(self):
        engine = ContextEngine(token_budget=100000)
        bundle = await engine.compose_context(
            query="test",
            system_prompt="prompt",
        )
        assert bundle.token_usage.remaining == 100000 - bundle.token_usage.system
        assert bundle.token_usage.remaining > 0

    @pytest.mark.asyncio
    async def test_repo_map_trimmed_to_category_budget(self):
        """A huge repo map should be trimmed to its category allocation."""
        engine = ContextEngine(token_budget=1000)
        huge_map = "file.py: def func\n" * 500
        bundle = await engine.compose_context(query="test", repo_map=huge_map)
        repo_blocks = [b for b in bundle.blocks if b.priority == BlockPriority.REPO_MAP]
        assert len(repo_blocks) == 1
        # Should be trimmed significantly (15% of 1000 = 150 tokens max)
        assert repo_blocks[0].token_count <= 200


# ---------------------------------------------------------------------------
# compact
# ---------------------------------------------------------------------------


class TestCompact:
    @pytest.mark.asyncio
    async def test_compact_no_op_when_under_budget(self):
        engine = ContextEngine()
        msgs = [Message(role="user", content="hi")]
        result = await engine.compact(msgs, target_tokens=10000)
        assert len(result) == 1
        assert result[0].content == "hi"

    @pytest.mark.asyncio
    async def test_compact_preserves_system_message(self):
        engine = ContextEngine()
        msgs = [
            Message(role="system", content="system"),
            Message(role="user", content="x" * 1000),
            Message(role="assistant", content="y" * 1000),
            Message(role="user", content="recent"),
        ]
        result = await engine.compact(msgs, target_tokens=200)
        assert result[0].role == "system"
        assert result[-1].content == "recent"

    @pytest.mark.asyncio
    async def test_compact_empty(self):
        engine = ContextEngine()
        result = await engine.compact([], target_tokens=1000)
        assert result == []

    @pytest.mark.asyncio
    async def test_compact_keeps_recent_messages(self):
        engine = ContextEngine()
        msgs = [Message(role="user", content=f"msg {i} " + "x" * 100) for i in range(20)]
        result = await engine.compact(msgs, target_tokens=500)
        # Should keep at least the last message
        assert len(result) >= 1
        assert "msg 19" in result[-1].content


# ---------------------------------------------------------------------------
# ContextBundle.to_messages
# ---------------------------------------------------------------------------


class TestContextBundleToMessages:
    def test_to_messages_basic(self):
        bundle = ContextBundle(
            blocks=[
                ContextBlock(
                    priority=BlockPriority.REPO_MAP,
                    label="Repo Map",
                    content="src/main.py: class App",
                    token_count=10,
                ),
                ContextBlock(
                    priority=BlockPriority.CONVERSATION_RECENT,
                    label="conversation:user",
                    content="user|||hello",
                    token_count=5,
                ),
                ContextBlock(
                    priority=BlockPriority.CONVERSATION_RECENT,
                    label="conversation:assistant",
                    content="assistant|||hi there",
                    token_count=5,
                ),
            ]
        )
        messages = bundle.to_messages("You are helpful.")
        assert messages[0].role == "system"
        assert "Repo Map" in messages[0].content
        assert messages[1].role == "user"
        assert messages[1].content == "hello"
        assert messages[2].role == "assistant"
        assert messages[2].content == "hi there"

    def test_to_messages_empty_bundle(self):
        bundle = ContextBundle()
        messages = bundle.to_messages("system")
        assert len(messages) == 1
        assert messages[0].role == "system"


# ---------------------------------------------------------------------------
# Full integration
# ---------------------------------------------------------------------------


class TestFullComposition:
    @pytest.mark.asyncio
    async def test_all_sources_combined(self):
        """Test with all context sources provided."""
        engine = ContextEngine(token_budget=100000)

        class FakeChunk:
            def __init__(self, content, importance=0.5):
                self.content = content
                self.importance = importance

        bundle = await engine.compose_context(
            query="implement auth",
            system_prompt="You are a coding assistant.",
            repo_map="src/auth.py: class AuthService\nsrc/db.py: class Database",
            memory_chunks=[FakeChunk("Project uses JWT tokens", importance=0.9)],
            skills_metadata="Tools: bash, python, git",
            conversation=[
                Message(role="user", content="Add login feature"),
                Message(role="assistant", content="I'll implement login."),
            ],
        )

        # Should have blocks for each category
        priorities = {b.priority for b in bundle.blocks}
        assert BlockPriority.SYSTEM in priorities
        assert BlockPriority.REPO_MAP in priorities
        assert BlockPriority.MEMORY in priorities
        assert BlockPriority.SKILLS in priorities
        assert BlockPriority.CONVERSATION_RECENT in priorities

        # Budget should be tracked
        assert bundle.token_usage.total == 100000
        assert bundle.token_usage.used > 0
        assert bundle.token_usage.remaining > 0
        assert bundle.token_usage.remaining == bundle.token_usage.total - bundle.token_usage.used
