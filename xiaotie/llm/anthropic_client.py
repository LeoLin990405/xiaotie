"""Anthropic LLM 客户端"""

from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from ..retry import RetryConfig, async_retry
from ..schema import FunctionCall, LLMResponse, Message, TokenUsage, ToolCall
from .base import LLMClientBase


class AnthropicClient(LLMClientBase):
    """Anthropic Claude 客户端"""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-20250514",
        retry_config: RetryConfig | None = None,
    ):
        super().__init__(api_key, api_base, model, retry_config)
        self.client = AsyncAnthropic(api_key=api_key, base_url=api_base)

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """转换为 Anthropic 消息格式"""
        system_message = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
                continue

            if msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                if msg.thinking or msg.tool_calls:
                    content_blocks = []
                    if msg.thinking:
                        content_blocks.append({"type": "thinking", "thinking": msg.thinking})
                    if msg.content:
                        content_blocks.append({"type": "text", "text": msg.content})
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            content_blocks.append(
                                {
                                    "type": "tool_use",
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "input": tc.function.arguments,
                                }
                            )
                    api_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    api_messages.append({"role": "assistant", "content": msg.content})

            elif msg.role == "tool":
                # Anthropic: tool 结果用 user role + tool_result
                api_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )

        return system_message, api_messages

    def _convert_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """转换工具为 Anthropic 格式"""
        result = []
        for tool in tools:
            if isinstance(tool, dict):
                result.append(tool)
            elif hasattr(tool, "to_schema"):
                result.append(tool.to_schema())
            else:
                raise TypeError(f"不支持的工具类型: {type(tool)}")
        return result

    async def _make_api_request(
        self,
        system: str | None,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        """执行 API 请求"""
        params = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": messages,
        }

        if system:
            params["system"] = system

        if tools:
            params["tools"] = tools

        return await self.client.messages.create(**params)

    def _parse_response(self, response: Any) -> LLMResponse:
        """解析 Anthropic 响应"""
        text_content = ""
        thinking_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "thinking":
                thinking_content += block.thinking
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        type="function",
                        function=FunctionCall(
                            name=block.name,
                            arguments=block.input,
                        ),
                    )
                )

        usage = None
        if hasattr(response, "usage"):
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

        return LLMResponse(
            content=text_content,
            thinking=thinking_content if thinking_content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=response.stop_reason or "stop",
            usage=usage,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
    ) -> LLMResponse:
        """生成响应"""
        system, api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools) if tools else None

        if self.retry_config.enabled:
            retry_decorator = async_retry(config=self.retry_config, on_retry=self.retry_callback)
            api_call = retry_decorator(self._make_api_request)
            response = await api_call(system, api_messages, api_tools)
        else:
            response = await self._make_api_request(system, api_messages, api_tools)

        return self._parse_response(response)
