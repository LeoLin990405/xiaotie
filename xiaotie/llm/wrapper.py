"""LLM 客户端统一包装器"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Callable, Optional

from ..retry import RetryConfig
from ..schema import LLMResponse, Message
from .anthropic_client import AnthropicClient
from .base import LLMClientBase
from .openai_client import OpenAIClient
from .providers import PROVIDER_CONFIGS, ProviderConfig, get_provider_config


class LLMProvider(str, Enum):
    """LLM 提供商"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    ZHIPU = "zhipu"
    MINIMAX = "minimax"
    OLLAMA = "ollama"


class LLMClient:
    """统一 LLM 客户端入口"""

    # MiniMax API 域名
    MINIMAX_DOMAINS = ("api.minimax.io", "api.minimaxi.com")

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        provider: LLMProvider | str = LLMProvider.ANTHROPIC,
        retry_config: RetryConfig | None = None,
    ):
        # 标准化 provider
        if isinstance(provider, str):
            provider_str = provider.lower()
            try:
                provider = LLMProvider(provider_str)
            except ValueError:
                # 尝试作为别名处理
                provider = LLMProvider.OPENAI  # 默认使用 OpenAI 兼容

        self.provider = provider
        self.provider_config = get_provider_config(provider.value)

        # 从配置或参数获取值
        if self.provider_config:
            api_base = api_base or self.provider_config.api_base
            model = model or self.provider_config.default_model
            if not api_key:
                api_key = os.environ.get(self.provider_config.api_key_env, "")

        # 处理 MiniMax API 的特殊 URL
        full_api_base = self._process_api_base(api_base or "", provider)

        # 根据 provider 创建对应客户端
        self._client: LLMClientBase
        if provider == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(
                api_key=api_key or "",
                api_base=full_api_base,
                model=model or "claude-sonnet-4-20250514",
                retry_config=retry_config,
            )
        else:
            # 所有其他 provider 使用 OpenAI 兼容客户端
            self._client = OpenAIClient(
                api_key=api_key or "",
                api_base=full_api_base,
                model=model or "gpt-4o",
                retry_config=retry_config,
            )

        # 存储配置
        self.model = model
        self.api_base = full_api_base

    def _process_api_base(self, api_base: str, provider: LLMProvider) -> str:
        """处理 API base URL"""
        is_minimax = any(domain in api_base for domain in self.MINIMAX_DOMAINS)

        if is_minimax:
            # MiniMax 需要根据 provider 添加正确的后缀
            api_base = api_base.replace("/anthropic", "").replace("/v1", "")
            if provider == LLMProvider.ANTHROPIC:
                return f"{api_base}/anthropic"
            else:
                return f"{api_base}/v1"

        return api_base

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
        enable_thinking: bool = True,
    ) -> LLMResponse:
        """流式生成响应"""
        if hasattr(self._client, "generate_stream"):
            return await self._client.generate_stream(
                messages, tools, on_thinking, on_content, enable_thinking
            )
        # 回退到非流式
        return await self._client.generate(messages, tools)

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
            raise ValueError(f"Unknown provider: {provider}")

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
