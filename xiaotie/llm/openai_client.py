"""OpenAI LLM 客户端 - 支持 GLM-4.7 / MiniMax / OpenAI"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from openai import AsyncOpenAI

from ..retry import RetryConfig, async_retry
from ..schema import FunctionCall, LLMResponse, Message, TokenUsage, ToolCall
from .base import LLMClientBase


class OpenAIClient(LLMClientBase):
    """OpenAI 兼容客户端

    支持:
    - OpenAI GPT 系列
    - 智谱 GLM-4.7 (深度思考 + 工具流式)
    - MiniMax abab 系列
    - 其他 OpenAI 兼容 API
    """

    # 智谱 GLM 域名
    GLM_DOMAINS = ("bigmodel.cn", "z.ai")
    # MiniMax 域名
    MINIMAX_DOMAINS = ("minimax.io", "minimaxi.com")

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(api_key, api_base, model, retry_config)
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)

        # 检测 API 类型
        self.is_glm = any(d in api_base for d in self.GLM_DOMAINS)
        self.is_minimax = any(d in api_base for d in self.MINIMAX_DOMAINS)

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
        tools: Optional[list[Any]] = None,
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

    async def generate_stream(
        self,
        messages: list[Message],
        tools: Optional[list[Any]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
        enable_thinking: bool = True,
    ) -> LLMResponse:
        """流式生成响应

        Args:
            messages: 消息列表
            tools: 工具列表
            on_thinking: 思考内容回调
            on_content: 回复内容回调
            enable_thinking: 是否启用深度思考 (GLM-4.7)
        """
        _, api_messages = self._convert_messages(messages)
        api_tools = self._convert_tools(tools) if tools else None

        params = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
        }

        if api_tools:
            params["tools"] = api_tools

        # GLM-4.7 特殊参数 (通过 extra_body 传递)
        if self.is_glm:
            extra_body = {}
            if api_tools:
                extra_body["tool_stream"] = True  # 工具流式输出
            if enable_thinking:
                extra_body["thinking"] = {"type": "enabled"}  # 深度思考
            if extra_body:
                params["extra_body"] = extra_body
            # GLM 推荐参数
            params["temperature"] = 1.0
            params["top_p"] = 0.95

        # MiniMax 特殊参数
        if self.is_minimax:
            # MiniMax 使用 reasoning_details
            pass

        try:
            stream = await self.client.chat.completions.create(**params)
        except Exception as e:
            # 如果 extra_body 参数不支持，回退到普通模式
            if "extra_body" in params:
                del params["extra_body"]
                try:
                    stream = await self.client.chat.completions.create(**params)
                except Exception:
                    raise e
            else:
                raise

        # 收集流式内容
        reasoning_content = ""
        content = ""
        tool_calls_dict = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 处理思考过程
            # GLM-4.7: delta.reasoning_content
            # MiniMax: delta.reasoning_details
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_content += delta.reasoning_content
                if on_thinking:
                    on_thinking(delta.reasoning_content)

            # 处理回复内容
            if hasattr(delta, "content") and delta.content:
                content += delta.content
                if on_content:
                    on_content(delta.content)

            # 处理工具调用 (流式拼接)
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "arguments": tc.function.arguments if tc.function and tc.function.arguments else "",
                        }
                    else:
                        if tc.id:
                            tool_calls_dict[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_dict[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_dict[idx]["arguments"] += tc.function.arguments

        # 构建工具调用列表
        tool_calls = []
        for idx in sorted(tool_calls_dict.keys()):
            tc_data = tool_calls_dict[idx]
            if tc_data["name"]:
                try:
                    arguments = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                except json.JSONDecodeError:
                    arguments = {}
                tool_calls.append(ToolCall(
                    id=tc_data["id"],
                    type="function",
                    function=FunctionCall(
                        name=tc_data["name"],
                        arguments=arguments,
                    ),
                ))

        return LLMResponse(
            content=content,
            thinking=reasoning_content if reasoning_content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason="stop",
            usage=None,
        )
