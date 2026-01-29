"""LLM 客户端统一包装器"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Union

from .base import LLMClientBase
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient
from ..retry import RetryConfig
from ..schema import Message, LLMResponse


class LLMProvider(str, Enum):
    """LLM 提供商"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class LLMClient:
    """统一 LLM 客户端入口"""

    # MiniMax API 域名
    MINIMAX_DOMAINS = ("api.minimax.io", "api.minimaxi.com")

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-20250514",
        provider: LLMProvider | str = LLMProvider.ANTHROPIC,
        retry_config: RetryConfig | None = None,
    ):
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        # 处理 MiniMax API 的特殊 URL
        full_api_base = self._process_api_base(api_base, provider)

        # 根据 provider 创建对应客户端
        self._client: LLMClientBase
        if provider == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(
                api_key=api_key,
                api_base=full_api_base,
                model=model,
                retry_config=retry_config,
            )
        elif provider == LLMProvider.OPENAI:
            self._client = OpenAIClient(
                api_key=api_key,
                api_base=full_api_base,
                model=model,
                retry_config=retry_config,
            )
        else:
            raise ValueError(f"不支持的 provider: {provider}")

    def _process_api_base(self, api_base: str, provider: LLMProvider) -> str:
        """处理 API base URL"""
        is_minimax = any(domain in api_base for domain in self.MINIMAX_DOMAINS)

        if is_minimax:
            # MiniMax 需要根据 provider 添加正确的后缀
            api_base = api_base.replace("/anthropic", "").replace("/v1", "")
            if provider == LLMProvider.ANTHROPIC:
                return f"{api_base}/anthropic"
            elif provider == LLMProvider.OPENAI:
                return f"{api_base}/v1"

        return api_base

    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
    ) -> LLMResponse:
        """生成响应"""
        return await self._client.generate(messages, tools)
