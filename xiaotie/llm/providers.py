"""MIMO-only provider configuration and capability matrix."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

MIMO_DEFAULT_API_BASE = "https://token-plan-sgp.xiaomimimo.com/anthropic"
MIMO_DEFAULT_MODEL = "mimo-v2-pro"
MIMO_SUPPORTED_MODELS = ["mimo-v2-pro", "mimo-v2-omni"]


class ProviderCapability(str, Enum):
    """Provider 能力"""

    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOLS = "parallel_tools"
    VISION = "vision"
    THINKING = "thinking"
    JSON_MODE = "json_mode"
    SYSTEM_PROMPT = "system_prompt"
    FUNCTION_CALLING = "function_calling"


@dataclass
class ProviderConfig:
    """Provider 配置"""

    name: str
    display_name: str
    api_base: str
    api_key_env: str
    default_model: str
    models: List[str] = field(default_factory=list)
    capabilities: List[ProviderCapability] = field(default_factory=list)
    openai_compatible: bool = False
    extra_headers: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    def has_capability(self, cap: ProviderCapability) -> bool:
        """检查是否支持某能力"""
        return cap in self.capabilities

    @property
    def supports_streaming(self) -> bool:
        return self.has_capability(ProviderCapability.STREAMING)

    @property
    def supports_tools(self) -> bool:
        return self.has_capability(ProviderCapability.TOOL_CALLING)

    @property
    def supports_parallel_tools(self) -> bool:
        return self.has_capability(ProviderCapability.PARALLEL_TOOLS)

    @property
    def supports_vision(self) -> bool:
        return self.has_capability(ProviderCapability.VISION)


PROVIDER_CONFIGS: Dict[str, ProviderConfig] = {
    "mimo": ProviderConfig(
        name="mimo",
        display_name="Xiaomi MIMO",
        api_base=MIMO_DEFAULT_API_BASE,
        api_key_env="MIMO_API_KEY",
        default_model=MIMO_DEFAULT_MODEL,
        models=MIMO_SUPPORTED_MODELS,
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.VISION,
            ProviderCapability.SYSTEM_PROMPT,
        ],
        openai_compatible=False,
        description="小铁 v3 唯一支持的 Anthropic-compatible MIMO provider",
    ),
}


def get_provider_config(name: str) -> Optional[ProviderConfig]:
    """获取 Provider 配置"""
    return PROVIDER_CONFIGS.get(name.lower())


def list_providers() -> List[str]:
    """列出所有支持的 Provider"""
    return list(PROVIDER_CONFIGS.keys())


def get_capability_matrix() -> Dict[str, Dict[str, bool]]:
    """获取能力矩阵"""
    matrix = {}
    all_caps = list(ProviderCapability)

    for name, config in PROVIDER_CONFIGS.items():
        matrix[name] = {cap.value: config.has_capability(cap) for cap in all_caps}

    return matrix


def print_capability_matrix():
    """打印能力矩阵表格"""
    matrix = get_capability_matrix()
    caps = [cap.value for cap in ProviderCapability]

    header = "| Provider |" + "|".join(f" {c[:8]:^8} " for c in caps) + "|"
    separator = "|" + "-" * 10 + "|" + "|".join("-" * 10 for _ in caps) + "|"

    print(header)
    print(separator)

    for provider, cap_dict in matrix.items():
        row = f"| {provider:8} |"
        for cap in caps:
            val = "yes" if cap_dict[cap] else "no"
            row += f" {val:^8} |"
        print(row)
