"""ResponseHandler 单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent.response import ResponseHandler
from xiaotie.schema import LLMResponse, Message, TokenUsage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            content="response",
            tool_calls=None,
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )
    )
    return llm


@pytest.fixture
def telemetry():
    t = MagicMock()
    t.record_stream_flush = MagicMock()
    return t


@pytest.fixture
def handler(mock_llm, telemetry):
    return ResponseHandler(
        llm=mock_llm,
        telemetry=telemetry,
        session_id="test-resp",
        token_limit=1000,
        summary_threshold=0.8,
        summary_keep_recent=3,
        enable_thinking=True,
        quiet=True,
    )


# ---------------------------------------------------------------------------
# estimate_tokens - with tiktoken
# ---------------------------------------------------------------------------

class TestEstimateTokensTiktoken:
    def test_with_tiktoken_encoding(self, handler):
        """If tiktoken is available, should use encoder"""
        if handler._encoding is None:
            pytest.skip("tiktoken not installed")
        msgs = [Message(role="user", content="hello world")]
        tokens = handler.estimate_tokens(msgs)
        assert tokens > 0

    def test_incremental_calculation(self, handler):
        """Adding messages should increase token count incrementally"""
        if handler._encoding is None:
            pytest.skip("tiktoken not installed")
        msgs = [Message(role="user", content="hello")]
        t1 = handler.estimate_tokens(msgs)
        msgs.append(Message(role="assistant", content="world"))
        t2 = handler.estimate_tokens(msgs)
        assert t2 > t1

    def test_cache_reset_on_shorter_list(self, handler):
        """If message count shrinks, cache should reset"""
        msgs = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="world"),
        ]
        handler.estimate_tokens(msgs)
        assert handler._cached_message_count == 2

        shorter = [Message(role="user", content="new")]
        handler.estimate_tokens(shorter)
        assert handler._cached_message_count == 1


# ---------------------------------------------------------------------------
# estimate_tokens - without tiktoken (char-based)
# ---------------------------------------------------------------------------

class TestEstimateTokensCharBased:
    def test_char_based_fallback(self, handler):
        """Without tiktoken, should use char/4 estimate"""
        handler._encoding = None
        handler._cached_token_count = 0
        handler._cached_message_count = 0
        msgs = [Message(role="user", content="a" * 100)]
        tokens = handler.estimate_tokens(msgs)
        assert tokens == 25  # 100 chars / 4

    def test_char_based_with_thinking(self, handler):
        handler._encoding = None
        handler._cached_token_count = 0
        handler._cached_message_count = 0
        msgs = [Message(role="user", content="a" * 40, thinking="b" * 40)]
        tokens = handler.estimate_tokens(msgs)
        assert tokens == 20  # (40 + 40) / 4


# ---------------------------------------------------------------------------
# maybe_summarize - under threshold
# ---------------------------------------------------------------------------

class TestMaybeSummarizeUnderThreshold:
    async def test_no_summary_when_under(self, handler, mock_llm):
        """Should return messages unchanged when under threshold"""
        msgs = [
            Message(role="system", content="system"),
            Message(role="user", content="hello"),
        ]
        result = await handler.maybe_summarize(msgs)
        assert result is msgs  # Same object, not modified
        mock_llm.generate.assert_not_awaited()


# ---------------------------------------------------------------------------
# maybe_summarize - over threshold
# ---------------------------------------------------------------------------

class TestMaybeSummarizeOverThreshold:
    async def test_summary_triggered(self, handler, mock_llm):
        """Should trigger summary when tokens exceed threshold"""
        # Set a very low token limit to force summarization
        handler.token_limit = 10
        handler.summary_threshold = 0.1  # threshold = 1 token

        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(content="摘要内容", tool_calls=None)
        )

        msgs = [Message(role="system", content="system prompt")]
        for i in range(20):
            msgs.append(Message(role="user", content=f"message {i} " * 50))
            msgs.append(Message(role="assistant", content=f"reply {i} " * 50))

        result = await handler.maybe_summarize(msgs)
        # Result should be shorter than original
        assert len(result) < len(msgs)
        # Cache should be reset
        assert handler._cached_token_count == 0
        assert handler._cached_message_count == 0


# ---------------------------------------------------------------------------
# generate() non-streaming
# ---------------------------------------------------------------------------

class TestGenerateNonStreaming:
    async def test_generate_returns_response(self, handler, mock_llm):
        msgs = [Message(role="user", content="hi")]
        tools = [{"type": "function", "function": {"name": "test"}}]
        response = await handler.generate(msgs, tools, stream=False)
        assert response.content == "response"
        mock_llm.generate.assert_awaited_once()

    async def test_generate_no_tools(self, handler, mock_llm):
        msgs = [Message(role="user", content="hi")]
        response = await handler.generate(msgs, [], stream=False)
        assert response.content == "response"
        # tools arg should be None when empty
        call_kwargs = mock_llm.generate.call_args
        assert call_kwargs.kwargs.get("tools") is None or call_kwargs[1].get("tools") is None


# ---------------------------------------------------------------------------
# Token stats update after generate()
# ---------------------------------------------------------------------------

class TestTokenStatsUpdate:
    async def test_token_stats_updated(self, handler, mock_llm):
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="hi",
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            )
        )
        msgs = [Message(role="user", content="hi")]
        await handler.generate(msgs, [], stream=False)
        assert handler.api_total_tokens == 150
        assert handler.api_input_tokens == 100
        assert handler.api_output_tokens == 50

    async def test_no_usage_no_update(self, handler, mock_llm):
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(content="hi", usage=None)
        )
        handler.api_total_tokens = 0
        msgs = [Message(role="user", content="hi")]
        await handler.generate(msgs, [], stream=False)
        assert handler.api_total_tokens == 0
