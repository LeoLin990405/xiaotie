"""LLM客户端测试"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from xiaotie.retry import RetryConfig
from xiaotie.schema import Message
from xiaotie.llm.base import LLMClientBase
from xiaotie.llm.anthropic_client import AnthropicClient
from xiaotie.llm.openai_client import OpenAIClient


class DummyClient(LLMClientBase):
    async def generate(self, messages, tools=None):
        return None

    async def generate_stream(self, messages, tools=None, on_thinking=None, on_content=None, enable_thinking=True):
        return None
        
    def _convert_messages(self, messages):
        return None, []
        
    def _convert_tools(self, tools):
        return []


class TestLLMClientBase:
    def test_init_sets_defaults(self):
        client = DummyClient("fake-key", "fake-base", "fake-model")
        assert client.api_key == "fake-key"
        assert client.api_base == "fake-base"
        assert client.model == "fake-model"
        assert isinstance(client.retry_config, RetryConfig)
        assert client.circuit_breaker is not None

    def test_retry_callback(self):
        client = DummyClient("fake-key", "fake-base", "fake-model")
        # Ensure it doesn't crash (logging/printing)
        client.retry_callback(ValueError("Test error"), 1)


class TestAnthropicClient:
    def test_init(self):
        client = AnthropicClient("test-key")
        assert client.model == "claude-sonnet-4-20250514"

    def test_convert_messages(self):
        client = AnthropicClient("test-key")
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi")
        ]
        system, api_messages = client._convert_messages(messages)
        assert system == "System prompt"
        assert len(api_messages) == 2
        assert api_messages[0]["role"] == "user"
        assert api_messages[1]["role"] == "assistant"

    @pytest.mark.asyncio
    @patch("xiaotie.llm.anthropic_client.AsyncAnthropic")
    async def test_generate_success(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello AI!")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        
        # Async mock for messages.create
        mock_create = AsyncMock(return_value=mock_response)
        mock_client.messages.create = mock_create

        client = AnthropicClient("test-key", retry_config=RetryConfig(enabled=False))
        # Ensure client uses mocked api
        client.client = mock_client

        messages = [Message(role="user", content="Test")]
        resp = await client.generate(messages)

        assert resp.content == "Hello AI!"
        assert resp.finish_reason == "end_turn"
        assert resp.usage.input_tokens == 10
        assert resp.usage.output_tokens == 5
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch("xiaotie.llm.anthropic_client.AsyncAnthropic")
    async def test_generate_stream(self, mock_anthropic_class):
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock stream event
        mock_event = MagicMock()
        mock_event.type = "content_block_delta"
        mock_event.delta.type = "text_delta"
        mock_event.delta.text = "Part 1 Part 2"
        
        # Mock final message
        mock_final = MagicMock()
        mock_final.stop_reason = "end_turn"
        mock_final.usage.input_tokens = 5
        mock_final.usage.output_tokens = 5
        
        # Create an async generator for the stream
        async def mock_stream_generator():
            yield mock_event
            
        # The object returned by `client.messages.stream(...)` is an async context manager
        # that yields a stream object.
        mock_context_manager = AsyncMock()
        mock_stream_obj = AsyncMock()
        mock_stream_obj.__aiter__.side_effect = mock_stream_generator
        mock_stream_obj.get_final_message = AsyncMock(return_value=mock_final)
        
        mock_context_manager.__aenter__.return_value = mock_stream_obj
        mock_client.messages.stream.return_value = mock_context_manager

        client = AnthropicClient("test-key", retry_config=RetryConfig(enabled=False))
        client.client = mock_client

        messages = [Message(role="user", content="Stream Test")]
        
        content_received = []
        def on_content(text):
            content_received.append(text)

        resp = await client.generate_stream(messages, on_content=on_content)
        assert "Part 1 Part 2" in content_received
        assert resp.content == "Part 1 Part 2"


class TestOpenAIClient:
    def test_init(self):
        client = OpenAIClient("test-key")
        assert client.model == "gpt-4o"

    def test_convert_messages(self):
        client = OpenAIClient("test-key")
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User")
        ]
        system, api_messages = client._convert_messages(messages)
        assert system is None
        assert len(api_messages) == 2
        assert api_messages[0]["role"] == "system"

    @pytest.mark.asyncio
    @patch("xiaotie.llm.openai_client.AsyncOpenAI")
    async def test_generate(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "OpenAI response"
        mock_choice.message.tool_calls = None
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 2
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 5

        mock_create = AsyncMock(return_value=mock_response)
        mock_client.chat.completions.create = mock_create

        client = OpenAIClient("test-key", retry_config=RetryConfig(enabled=False))
        client.client = mock_client

        messages = [Message(role="user", content="Test")]
        resp = await client.generate(messages)

        assert resp.content == "OpenAI response"
        assert resp.usage.total_tokens == 5
        mock_create.assert_called_once()
