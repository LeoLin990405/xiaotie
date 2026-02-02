"""
LLM Provider 配置和能力矩阵

支持的 Provider:
- Anthropic Claude
- OpenAI GPT
- Google Gemini
- DeepSeek
- Qwen (通义千问)
- 智谱 GLM
- MiniMax
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ProviderCapability(str, Enum):
    """Provider 能力"""

    STREAMING = "streaming"  # 流式输出
    TOOL_CALLING = "tool_calling"  # 工具调用
    PARALLEL_TOOLS = "parallel_tools"  # 并行工具调用
    VISION = "vision"  # 视觉/图像理解
    THINKING = "thinking"  # 深度思考模式
    JSON_MODE = "json_mode"  # JSON 输出模式
    SYSTEM_PROMPT = "system_prompt"  # 系统提示词
    FUNCTION_CALLING = "function_calling"  # 函数调用 (OpenAI 风格)


@dataclass
class ProviderConfig:
    """Provider 配置"""

    name: str
    display_name: str
    api_base: str
    api_key_env: str  # 环境变量名
    default_model: str
    models: List[str] = field(default_factory=list)
    capabilities: List[ProviderCapability] = field(default_factory=list)
    # OpenAI 兼容性
    openai_compatible: bool = False
    # 特殊配置
    extra_headers: Dict[str, str] = field(default_factory=dict)
    # 描述
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


# Provider 配置注册表
PROVIDER_CONFIGS: Dict[str, ProviderConfig] = {
    # Anthropic Claude
    "anthropic": ProviderConfig(
        name="anthropic",
        display_name="Anthropic Claude",
        api_base="https://api.anthropic.com",
        api_key_env="ANTHROPIC_API_KEY",
        default_model="claude-sonnet-4-20250514",
        models=[
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.VISION,
            ProviderCapability.THINKING,
            ProviderCapability.SYSTEM_PROMPT,
        ],
        openai_compatible=False,
        description="Claude 系列模型，擅长复杂推理和代码生成",
    ),
    # OpenAI
    "openai": ProviderConfig(
        name="openai",
        display_name="OpenAI GPT",
        api_base="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        default_model="gpt-4o",
        models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.VISION,
            ProviderCapability.JSON_MODE,
            ProviderCapability.SYSTEM_PROMPT,
            ProviderCapability.FUNCTION_CALLING,
        ],
        openai_compatible=True,
        description="GPT 系列模型，通用能力强",
    ),
    # Google Gemini
    "gemini": ProviderConfig(
        name="gemini",
        display_name="Google Gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GOOGLE_API_KEY",
        default_model="gemini-2.0-flash",
        models=[
            "gemini-2.0-flash",
            "gemini-2.0-flash-thinking",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.VISION,
            ProviderCapability.THINKING,
            ProviderCapability.SYSTEM_PROMPT,
            ProviderCapability.FUNCTION_CALLING,
        ],
        openai_compatible=True,
        description="Gemini 系列模型，多模态能力强",
    ),
    # DeepSeek
    "deepseek": ProviderConfig(
        name="deepseek",
        display_name="DeepSeek",
        api_base="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        models=[
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.THINKING,
            ProviderCapability.SYSTEM_PROMPT,
            ProviderCapability.FUNCTION_CALLING,
        ],
        openai_compatible=True,
        description="DeepSeek 模型，深度推理能力强，性价比高",
    ),
    # Qwen (通义千问)
    "qwen": ProviderConfig(
        name="qwen",
        display_name="Qwen (通义千问)",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        default_model="qwen-plus",
        models=[
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-coder-plus",
            "qwen-vl-plus",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.PARALLEL_TOOLS,
            ProviderCapability.VISION,
            ProviderCapability.SYSTEM_PROMPT,
            ProviderCapability.FUNCTION_CALLING,
        ],
        openai_compatible=True,
        description="通义千问系列，中文能力强",
    ),
    # 智谱 GLM
    "zhipu": ProviderConfig(
        name="zhipu",
        display_name="智谱 GLM",
        api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        default_model="GLM-4.7",
        models=[
            "GLM-4.7",
            "GLM-4-Plus",
            "GLM-4-Air",
            "GLM-4-Flash",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.THINKING,
            ProviderCapability.SYSTEM_PROMPT,
        ],
        openai_compatible=True,
        description="GLM 系列，支持深度思考模式",
    ),
    # MiniMax
    "minimax": ProviderConfig(
        name="minimax",
        display_name="MiniMax",
        api_base="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        default_model="abab6.5s-chat",
        models=[
            "abab6.5s-chat",
            "abab6.5-chat",
            "abab5.5-chat",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.TOOL_CALLING,
            ProviderCapability.SYSTEM_PROMPT,
        ],
        openai_compatible=True,
        description="MiniMax abab 系列模型",
    ),
    # Ollama (本地)
    "ollama": ProviderConfig(
        name="ollama",
        display_name="Ollama (Local)",
        api_base="http://localhost:11434/v1",
        api_key_env="OLLAMA_API_KEY",  # 通常不需要
        default_model="llama3.2",
        models=[
            "llama3.2",
            "llama3.1",
            "codellama",
            "mistral",
            "qwen2.5",
        ],
        capabilities=[
            ProviderCapability.STREAMING,
            ProviderCapability.SYSTEM_PROMPT,
        ],
        openai_compatible=True,
        description="本地运行的开源模型",
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

    # 表头
    header = "| Provider |" + "|".join(f" {c[:8]:^8} " for c in caps) + "|"
    separator = "|" + "-" * 10 + "|" + "|".join("-" * 10 for _ in caps) + "|"

    print(header)
    print(separator)

    # 数据行
    for provider, cap_dict in matrix.items():
        row = f"| {provider:8} |"
        for cap in caps:
            val = "✅" if cap_dict[cap] else "❌"
            row += f" {val:^8} |"
        print(row)
