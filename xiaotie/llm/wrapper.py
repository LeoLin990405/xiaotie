"""MIMO-only LLM client facade."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Callable, Optional

from ..retry import RetryConfig
from ..schema import LLMResponse, Message
from .base import LLMClientBase
from .providers import (
    MIMO_DEFAULT_MODEL,
    PROVIDER_CONFIGS,
    ProviderConfig,
    get_provider_config,
)


class LLMProvider(str, Enum):
    """LLM 提供商"""

    MIMO = "mimo"


class LLMClient:
    """统一 LLM 客户端入口。

    小铁 v3 有意只暴露 MIMO。底层 transport 复用 Anthropic-compatible
    message API，但 provider 边界和配置面都固定为 `mimo`。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        provider: LLMProvider | str = LLMProvider.MIMO,
        retry_config: RetryConfig | None = None,
    ):
        if isinstance(provider, str):
            try:
                provider = LLMProvider(provider.lower())
            except ValueError:
                raise ValueError("小铁 v3 只支持 MIMO provider，请设置 provider: mimo") from None

        if provider != LLMProvider.MIMO:
            raise ValueError("小铁 v3 只支持 MIMO provider，请设置 provider: mimo")

        self.provider = provider
        self.provider_config = get_provider_config(provider.value)

        if self.provider_config:
            api_base = api_base or self.provider_config.api_base
            model = model or self.provider_config.default_model
            if not api_key:
                api_key = os.environ.get(self.provider_config.api_key_env, "")

        from .mimo_client import MimoClient

        self._client: LLMClientBase = MimoClient(
            api_key=api_key or "",
            api_base=api_base or "",
            model=model or MIMO_DEFAULT_MODEL,
            retry_config=retry_config,
        )
        self.model = model or MIMO_DEFAULT_MODEL
        self.api_base = api_base or ""

    @property
    def capabilities(self) -> list:
        """获取当前 provider 的能力列表"""
        if self.provider_config:
            return self.provider_config.capabilities
        return []

    def has_capability(self, cap: str) -> bool:
        """检查是否支持某能力"""
        if self.provider_config:
            from .providers import ProviderCapability

            try:
                cap_enum = ProviderCapability(cap)
                return self.provider_config.has_capability(cap_enum)
            except ValueError:
                return False
        return False

    async def generate(
        self,
        messages: list[Message],
        tools: Optional[list[Any]] = None,
    ) -> LLMResponse:
        """生成响应"""
        return await self._client.generate(messages, tools)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: Optional[list[Any]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
        enable_thinking: bool = False,
    ) -> LLMResponse:
        """流式生成响应"""
        return await self._client.generate_stream(
            messages, tools, on_thinking, on_content, enable_thinking
        )

    @classmethod
    def from_provider(
        cls,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> "LLMClient":
        """从 provider 名称创建客户端"""
        config = get_provider_config(provider)
        if not config:
            raise ValueError("小铁 v3 只支持 MIMO provider，请设置 provider: mimo")

        return cls(
            provider=provider,
            model=model or config.default_model,
            api_key=api_key,
            api_base=config.api_base,
        )

    @staticmethod
    def list_providers() -> list[str]:
        """列出所有支持的 provider"""
        return list(PROVIDER_CONFIGS.keys())

    @staticmethod
    def get_provider_info(provider: str) -> Optional[ProviderConfig]:
        """获取 provider 信息"""
        return get_provider_config(provider)
