"""LLM 客户端基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..retry import RetryConfig
from ..schema import LLMResponse, Message


class LLMClientBase(ABC):
    """LLM 客户端抽象基类"""

    def __init__(
        self,
        api_key: str,
        api_base: str,
        model: str,
        retry_config: RetryConfig | None = None,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.retry_config = retry_config or RetryConfig()

    def retry_callback(self, exception: Exception, attempt: int):
        """重试回调"""
        print(f"⚠️ 请求失败，第 {attempt} 次重试: {exception}")

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
    ) -> LLMResponse:
        """生成响应"""
        pass

    @abstractmethod
    def _convert_messages(
        self,
        messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """转换消息格式"""
        pass

    @abstractmethod
    def _convert_tools(self, tools: list[Any]) -> list[dict[str, Any]]:
        """转换工具格式"""
        pass
