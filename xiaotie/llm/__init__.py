"""LLM 模块

Provider SDKs are imported lazily so core runtime tests can import the LLM
facade without requiring every optional provider package to be installed.
"""

from .base import LLMClientBase
from .providers import (
    PROVIDER_CONFIGS,
    ProviderCapability,
    ProviderConfig,
    get_capability_matrix,
    get_provider_config,
    list_providers,
    print_capability_matrix,
)
from .wrapper import LLMClient, LLMProvider


def __getattr__(name: str):
    if name == "AnthropicClient":
        from .anthropic_client import AnthropicClient

        return AnthropicClient
    if name == "OpenAIClient":
        from .openai_client import OpenAIClient

        return OpenAIClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base
    "LLMClientBase",
    # Clients
    "LLMClient",
    "LLMProvider",
    "AnthropicClient",
    "OpenAIClient",
    # Providers
    "ProviderConfig",
    "ProviderCapability",
    "PROVIDER_CONFIGS",
    "get_provider_config",
    "list_providers",
    "get_capability_matrix",
    "print_capability_matrix",
]
