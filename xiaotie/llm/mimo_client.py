"""MIMO model gateway."""

from __future__ import annotations

from ..retry import RetryConfig
from .anthropic_client import AnthropicClient
from .providers import MIMO_DEFAULT_API_BASE, MIMO_DEFAULT_MODEL


class MimoClient(AnthropicClient):
    """MIMO gateway over its Anthropic-compatible message API."""

    def __init__(
        self,
        api_key: str,
        api_base: str = MIMO_DEFAULT_API_BASE,
        model: str = MIMO_DEFAULT_MODEL,
        retry_config: RetryConfig | None = None,
    ):
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model=model,
            retry_config=retry_config,
        )
