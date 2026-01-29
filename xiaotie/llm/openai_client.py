"""OpenAI LLM 客户端"""

from __future__ import annotations

import json
from typing import Any, List, Tuple, Optional

from openai import AsyncOpenAI

from .base import LLMClientBase
from ..retry import RetryConfig, async_retry
from ..schema import Message, LLMResponse, ToolCall, FunctionCall, TokenUsage


class OpenAIClient(LLMClientBase):
    """OpenAI 兼容客户端"""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        retry_config: RetryConfig | None = None,
    ):
        super().__init__(api_key, api_base, model, retry_config)
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    def _convert_messages(
        self,
        messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """转换为 OpenAI 消息格式"""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                api_messages.append({"role": "system", "content": msg.content})

            elif msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                assistant_msg = {"role": "assistant"}

                if msg.content:
                    assistant_msg["content"] = msg.content

                if msg.tool_calls:
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        tool_calls_list.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": json.dumps(tc.function.arguments),
                            },
                        })
                    assistant_msg["tool_calls"] = tool_calls_list

                # 保留 reasoning_details (MiniMax 等支持)
                if msg.thinking:
                    assistant_msg["reasoning_details"] = [{"text": msg.thinking}]

                api_messages.append(assistant_msg)

            elif msg.role == "tool":
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

        return None, api_messages

    def _convert_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """转换工具为 OpenAI 格式"""
        result = []
        for tool in tools:
            if isinstance(tool, dict):
                if "type" in tool and tool["type"] == "function":
                    result.append(tool)
                else:
                    # Anthropic 格式转 OpenAI
                    result.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {}),
                        },
                    })
            elif hasattr(tool, "to_openai_schema"):
                result.append(tool.to_openai_schema())
            else:
                raise TypeError(f"不支持的工具类型: {type(tool)}")
        return result

    async def _make_api_request(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Any:
        """执行 API 请求"""
        params = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            params["tools"] = tools

        return await self.client.chat.completions.create(**params)

    def _parse_response(self, response: Any) -> LLMResponse:
        """解析 OpenAI 响应"""
        message = response.choices[0].message

        text_content = message.content or ""

        # 提取 reasoning_details (MiniMax 等)
        thinking_content = ""
        if hasattr(message, "reasoning_details") and message.reasoning_details:
            for detail in message.reasoning_details:
                if hasattr(detail, "text"):
                    thinking_content += detail.text

        # 解析工具调用
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                arguments = json.loads(tc.function.arguments)
                tool_calls.append(ToolCall(
                    id=tc.id,
                    type="function",
                    function=FunctionCall(
                        name=tc.function.name,
                        arguments=arguments,
                    ),
                ))

        usage = None
        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return LLMResponse(
            content=text_content,
            thinking=thinking_content if thinking_content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason="stop",
            usage=usage,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
    ) -> LLMResponse:
        """生成响应"""
        _, api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools) if tools else None

        if self.retry_config.enabled:
            retry_decorator = async_retry(
                config=self.retry_config,
                on_retry=self.retry_callback
            )
            api_call = retry_decorator(self._make_api_request)
            response = await api_call(api_messages, api_tools)
        else:
            response = await self._make_api_request(api_messages, api_tools)

        return self._parse_response(response)
