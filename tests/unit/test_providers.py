"""MIMO-only provider 配置和能力矩阵测试"""

import os
from unittest.mock import patch

import pytest

from xiaotie.llm import (
    PROVIDER_CONFIGS,
    LLMClient,
    LLMProvider,
    ProviderCapability,
    ProviderConfig,
    get_capability_matrix,
    get_provider_config,
    list_providers,
)
from xiaotie.llm.providers import MIMO_DEFAULT_API_BASE, MIMO_DEFAULT_MODEL


class TestProviderCapability:
    def test_all_capabilities_defined(self):
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
        assert isinstance(ProviderCapability.STREAMING, str)
        assert ProviderCapability.STREAMING == "streaming"


class TestProviderConfig:
    def test_create_config(self):
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

    def test_property_shortcuts(self):
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


class TestProviderConfigs:
    def test_only_mimo_registered(self):
        assert list(PROVIDER_CONFIGS) == ["mimo"]

    def test_mimo_config(self):
        config = PROVIDER_CONFIGS["mimo"]
        assert config.name == "mimo"
        assert config.api_base == MIMO_DEFAULT_API_BASE
        assert config.api_key_env == "MIMO_API_KEY"
        assert config.default_model == MIMO_DEFAULT_MODEL
        assert config.openai_compatible is False
        assert config.has_capability(ProviderCapability.STREAMING)
        assert config.has_capability(ProviderCapability.TOOL_CALLING)
        assert not config.has_capability(ProviderCapability.THINKING)


class TestProviderFunctions:
    def test_get_provider_config(self):
        config = get_provider_config("mimo")
        assert config is not None
        assert config.name == "mimo"

    def test_get_provider_config_case_insensitive(self):
        config = get_provider_config("MIMO")
        assert config is not None
        assert config.name == "mimo"

    def test_get_provider_config_unknown(self):
        assert get_provider_config("openai") is None

    def test_list_providers(self):
        assert list_providers() == ["mimo"]

    def test_get_capability_matrix(self):
        matrix = get_capability_matrix()
        assert list(matrix) == ["mimo"]
        assert matrix["mimo"]["streaming"] is True
        assert matrix["mimo"]["thinking"] is False


class TestLLMProvider:
    def test_only_mimo_in_enum(self):
        assert [p.value for p in LLMProvider] == ["mimo"]

    def test_provider_is_string_enum(self):
        assert isinstance(LLMProvider.MIMO, str)
        assert LLMProvider.MIMO == "mimo"


class TestLLMClientProviderIntegration:
    def test_client_list_providers(self):
        assert LLMClient.list_providers() == ["mimo"]

    def test_client_get_provider_info(self):
        info = LLMClient.get_provider_info("mimo")
        assert info is not None
        assert info.name == "mimo"

    def test_client_from_provider(self):
        with patch.dict(os.environ, {"MIMO_API_KEY": "test-key"}):
            client = LLMClient.from_provider("mimo")
            assert client.provider == LLMProvider.MIMO
            assert client.provider_config is not None

    def test_client_from_provider_with_model(self):
        with patch.dict(os.environ, {"MIMO_API_KEY": "test-key"}):
            client = LLMClient.from_provider("mimo", model="mimo-v2-omni")
            assert client.model == "mimo-v2-omni"

    def test_client_from_unknown_provider(self):
        with pytest.raises(ValueError, match="MIMO"):
            LLMClient.from_provider("openai")

    def test_client_rejects_non_mimo_string_provider(self):
        with pytest.raises(ValueError, match="MIMO"):
            LLMClient(provider="anthropic")

    def test_client_capabilities(self):
        with patch.dict(os.environ, {"MIMO_API_KEY": "test-key"}):
            client = LLMClient(provider=LLMProvider.MIMO)
            assert client.has_capability("streaming")
            assert client.has_capability("tool_calling")
            assert not client.has_capability("thinking")
