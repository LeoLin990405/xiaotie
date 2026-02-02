"""Provider 配置和能力矩阵测试"""

import os
from unittest.mock import patch

import pytest

from xiaotie.llm import (
    LLMClient,
    LLMProvider,
    PROVIDER_CONFIGS,
    ProviderCapability,
    ProviderConfig,
    get_capability_matrix,
    get_provider_config,
    list_providers,
)


class TestProviderCapability:
    """ProviderCapability 枚举测试"""

    def test_all_capabilities_defined(self):
        """测试所有能力都已定义"""
        expected = [
            "streaming",
            "tool_calling",
            "parallel_tools",
            "vision",
            "thinking",
            "json_mode",
            "system_prompt",
            "function_calling",
        ]
        actual = [cap.value for cap in ProviderCapability]
        assert set(expected) == set(actual)

    def test_capability_is_string_enum(self):
        """测试能力枚举是字符串类型"""
        assert isinstance(ProviderCapability.STREAMING, str)
        assert ProviderCapability.STREAMING == "streaming"


class TestProviderConfig:
    """ProviderConfig 数据类测试"""

    def test_create_config(self):
        """测试创建配置"""
        config = ProviderConfig(
            name="test",
            display_name="Test Provider",
            api_base="https://api.test.com",
            api_key_env="TEST_API_KEY",
            default_model="test-model",
            models=["test-model", "test-model-2"],
            capabilities=[ProviderCapability.STREAMING, ProviderCapability.TOOL_CALLING],
        )
        assert config.name == "test"
        assert config.display_name == "Test Provider"
        assert config.api_base == "https://api.test.com"
        assert config.api_key_env == "TEST_API_KEY"
        assert config.default_model == "test-model"
        assert len(config.models) == 2

    def test_has_capability(self):
        """测试能力检查"""
        config = ProviderConfig(
            name="test",
            display_name="Test",
            api_base="https://api.test.com",
            api_key_env="TEST_KEY",
            default_model="model",
            capabilities=[ProviderCapability.STREAMING, ProviderCapability.VISION],
        )
        assert config.has_capability(ProviderCapability.STREAMING)
        assert config.has_capability(ProviderCapability.VISION)
        assert not config.has_capability(ProviderCapability.THINKING)

    def test_property_shortcuts(self):
        """测试属性快捷方式"""
        config = ProviderConfig(
            name="test",
            display_name="Test",
            api_base="https://api.test.com",
            api_key_env="TEST_KEY",
            default_model="model",
            capabilities=[
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
                ProviderCapability.PARALLEL_TOOLS,
                ProviderCapability.VISION,
            ],
        )
        assert config.supports_streaming
        assert config.supports_tools
        assert config.supports_parallel_tools
        assert config.supports_vision

    def test_openai_compatible_default(self):
        """测试 OpenAI 兼容性默认值"""
        config = ProviderConfig(
            name="test",
            display_name="Test",
            api_base="https://api.test.com",
            api_key_env="TEST_KEY",
            default_model="model",
        )
        assert config.openai_compatible is False


class TestProviderConfigs:
    """PROVIDER_CONFIGS 注册表测试"""

    def test_all_providers_registered(self):
        """测试所有 provider 都已注册"""
        expected_providers = [
            "anthropic",
            "openai",
            "gemini",
            "deepseek",
            "qwen",
            "zhipu",
            "minimax",
            "ollama",
        ]
        for provider in expected_providers:
            assert provider in PROVIDER_CONFIGS, f"Missing provider: {provider}"

    def test_anthropic_config(self):
        """测试 Anthropic 配置"""
        config = PROVIDER_CONFIGS["anthropic"]
        assert config.name == "anthropic"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.openai_compatible is False
        assert config.has_capability(ProviderCapability.STREAMING)
        assert config.has_capability(ProviderCapability.TOOL_CALLING)
        assert config.has_capability(ProviderCapability.THINKING)

    def test_openai_config(self):
        """测试 OpenAI 配置"""
        config = PROVIDER_CONFIGS["openai"]
        assert config.name == "openai"
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.openai_compatible is True
        assert config.has_capability(ProviderCapability.JSON_MODE)
        assert config.has_capability(ProviderCapability.FUNCTION_CALLING)

    def test_gemini_config(self):
        """测试 Gemini 配置"""
        config = PROVIDER_CONFIGS["gemini"]
        assert config.name == "gemini"
        assert config.api_key_env == "GOOGLE_API_KEY"
        assert config.openai_compatible is True
        assert "openai" in config.api_base  # 使用 OpenAI 兼容端点

    def test_deepseek_config(self):
        """测试 DeepSeek 配置"""
        config = PROVIDER_CONFIGS["deepseek"]
        assert config.name == "deepseek"
        assert config.api_key_env == "DEEPSEEK_API_KEY"
        assert config.openai_compatible is True
        assert config.has_capability(ProviderCapability.THINKING)

    def test_qwen_config(self):
        """测试 Qwen 配置"""
        config = PROVIDER_CONFIGS["qwen"]
        assert config.name == "qwen"
        assert config.api_key_env == "DASHSCOPE_API_KEY"
        assert config.openai_compatible is True

    def test_ollama_config(self):
        """测试 Ollama 配置"""
        config = PROVIDER_CONFIGS["ollama"]
        assert config.name == "ollama"
        assert "localhost" in config.api_base
        assert config.openai_compatible is True


class TestProviderFunctions:
    """Provider 辅助函数测试"""

    def test_get_provider_config(self):
        """测试获取 provider 配置"""
        config = get_provider_config("anthropic")
        assert config is not None
        assert config.name == "anthropic"

    def test_get_provider_config_case_insensitive(self):
        """测试大小写不敏感"""
        config = get_provider_config("ANTHROPIC")
        assert config is not None
        assert config.name == "anthropic"

    def test_get_provider_config_unknown(self):
        """测试未知 provider"""
        config = get_provider_config("unknown_provider")
        assert config is None

    def test_list_providers(self):
        """测试列出所有 provider"""
        providers = list_providers()
        assert isinstance(providers, list)
        assert "anthropic" in providers
        assert "openai" in providers
        assert len(providers) >= 8

    def test_get_capability_matrix(self):
        """测试获取能力矩阵"""
        matrix = get_capability_matrix()
        assert isinstance(matrix, dict)
        assert "anthropic" in matrix
        assert "openai" in matrix

        # 检查矩阵结构
        anthropic_caps = matrix["anthropic"]
        assert "streaming" in anthropic_caps
        assert anthropic_caps["streaming"] is True


class TestLLMProvider:
    """LLMProvider 枚举测试"""

    def test_all_providers_in_enum(self):
        """测试所有 provider 都在枚举中"""
        expected = [
            "anthropic",
            "openai",
            "gemini",
            "deepseek",
            "qwen",
            "zhipu",
            "minimax",
            "ollama",
        ]
        actual = [p.value for p in LLMProvider]
        assert set(expected) == set(actual)

    def test_provider_is_string_enum(self):
        """测试 provider 枚举是字符串类型"""
        assert isinstance(LLMProvider.ANTHROPIC, str)
        assert LLMProvider.ANTHROPIC == "anthropic"


class TestLLMClientProviderIntegration:
    """LLMClient 与 Provider 集成测试"""

    def test_client_list_providers(self):
        """测试客户端列出 provider"""
        providers = LLMClient.list_providers()
        assert "anthropic" in providers
        assert "openai" in providers

    def test_client_get_provider_info(self):
        """测试客户端获取 provider 信息"""
        info = LLMClient.get_provider_info("anthropic")
        assert info is not None
        assert info.name == "anthropic"

    def test_client_from_provider(self):
        """测试从 provider 创建客户端"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = LLMClient.from_provider("openai")
            assert client.provider == LLMProvider.OPENAI
            assert client.provider_config is not None

    def test_client_from_provider_with_model(self):
        """测试从 provider 创建客户端并指定模型"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            client = LLMClient.from_provider("deepseek", model="deepseek-coder")
            assert client.model == "deepseek-coder"

    def test_client_from_unknown_provider(self):
        """测试从未知 provider 创建客户端"""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClient.from_provider("unknown_provider")

    def test_client_capabilities(self):
        """测试客户端能力检查"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = LLMClient(provider=LLMProvider.ANTHROPIC)
            assert client.has_capability("streaming")
            assert client.has_capability("tool_calling")
            assert not client.has_capability("json_mode")  # Anthropic 不支持

    def test_client_capabilities_list(self):
        """测试客户端能力列表"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = LLMClient(provider=LLMProvider.OPENAI)
            caps = client.capabilities
            assert isinstance(caps, list)
            assert ProviderCapability.STREAMING in caps

    def test_client_auto_api_key_from_env(self):
        """测试自动从环境变量获取 API key"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key", "GOOGLE_API_KEY": "test-google-key"}):
            client = LLMClient(provider=LLMProvider.GEMINI)
            # 验证使用了正确的环境变量
            assert client.provider_config.api_key_env == "GOOGLE_API_KEY"

    def test_client_string_provider(self):
        """测试字符串 provider 参数"""
        with patch.dict(os.environ, {"QWEN_API_KEY": "test-key", "DASHSCOPE_API_KEY": "test-key"}):
            client = LLMClient(provider="qwen")
            assert client.provider == LLMProvider.QWEN
