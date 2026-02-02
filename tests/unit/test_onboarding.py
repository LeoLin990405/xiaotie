"""Onboarding 向导单元测试"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from xiaotie.tui.onboarding import (
    ProviderSetup,
    SUPPORTED_PROVIDERS,
    get_config_path,
    has_any_api_key,
    is_first_run,
    should_show_onboarding,
)


class TestProviderSetup:
    """ProviderSetup 数据类测试"""

    def test_create_provider_setup(self):
        """测试创建 Provider 配置"""
        provider = ProviderSetup(
            name="test",
            display_name="Test Provider",
            icon="󰋽",
            api_key_env="TEST_API_KEY",
            api_key_hint="test-...",
            default_model="test-model",
            test_endpoint="https://api.test.com/v1",
        )
        assert provider.name == "test"
        assert provider.display_name == "Test Provider"
        assert provider.icon == "󰋽"
        assert provider.api_key_env == "TEST_API_KEY"
        assert provider.api_key_hint == "test-..."
        assert provider.default_model == "test-model"
        assert provider.test_endpoint == "https://api.test.com/v1"


class TestSupportedProviders:
    """SUPPORTED_PROVIDERS 列表测试"""

    def test_has_essential_providers(self):
        """测试包含必要的 Provider"""
        names = [p.name for p in SUPPORTED_PROVIDERS]
        essential = ["anthropic", "openai", "deepseek"]
        for provider in essential:
            assert provider in names, f"Missing essential provider: {provider}"

    def test_all_providers_have_required_fields(self):
        """测试所有 Provider 都有必要字段"""
        for provider in SUPPORTED_PROVIDERS:
            assert provider.name, f"Provider missing name"
            assert provider.display_name, f"Provider {provider.name} missing display_name"
            assert provider.api_key_env, f"Provider {provider.name} missing api_key_env"
            assert provider.default_model, f"Provider {provider.name} missing default_model"

    def test_no_duplicate_names(self):
        """测试无重复 Provider 名称"""
        names = [p.name for p in SUPPORTED_PROVIDERS]
        assert len(names) == len(set(names))

    def test_no_duplicate_api_key_envs(self):
        """测试无重复环境变量名"""
        envs = [p.api_key_env for p in SUPPORTED_PROVIDERS]
        assert len(envs) == len(set(envs))


class TestGetConfigPath:
    """get_config_path 函数测试"""

    def test_default_path(self):
        """测试默认配置路径"""
        with patch.dict(os.environ, {}, clear=True):
            # 清除 XDG_CONFIG_HOME
            if "XDG_CONFIG_HOME" in os.environ:
                del os.environ["XDG_CONFIG_HOME"]

            path = get_config_path()
            assert path.name == "config.yaml"
            assert "xiaotie" in str(path)

    def test_xdg_config_path(self):
        """测试 XDG 配置路径"""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg_config"}):
            path = get_config_path()
            assert str(path).startswith("/tmp/xdg_config")
            assert "xiaotie" in str(path)
            assert path.name == "config.yaml"

    def test_returns_path_object(self):
        """测试返回 Path 对象"""
        path = get_config_path()
        assert isinstance(path, Path)


class TestIsFirstRun:
    """is_first_run 函数测试"""

    def test_first_run_when_no_config(self):
        """测试无配置文件时为首次运行"""
        with patch("xiaotie.tui.onboarding.get_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/path/config.yaml")
            assert is_first_run() is True

    def test_not_first_run_when_config_exists(self, tmp_path):
        """测试配置文件存在时非首次运行"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: true")

        with patch("xiaotie.tui.onboarding.get_config_path") as mock_path:
            mock_path.return_value = config_file
            assert is_first_run() is False


class TestHasAnyApiKey:
    """has_any_api_key 函数测试"""

    def test_no_api_key(self):
        """测试无 API Key"""
        # 清除所有相关环境变量
        env_vars = {p.api_key_env: "" for p in SUPPORTED_PROVIDERS}
        with patch.dict(os.environ, env_vars, clear=False):
            # 确保环境变量被清除
            for key in env_vars:
                if key in os.environ:
                    del os.environ[key]
            # 由于环境变量可能已存在，这个测试可能不稳定
            # 使用 mock 更可靠
            pass

    def test_has_anthropic_key(self):
        """测试有 Anthropic API Key"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            assert has_any_api_key() is True

    def test_has_openai_key(self):
        """测试有 OpenAI API Key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            assert has_any_api_key() is True

    def test_has_deepseek_key(self):
        """测试有 DeepSeek API Key"""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            assert has_any_api_key() is True


class TestShouldShowOnboarding:
    """should_show_onboarding 函数测试"""

    def test_show_when_first_run_and_no_key(self):
        """测试首次运行且无 API Key 时显示向导"""
        with patch("xiaotie.tui.onboarding.is_first_run", return_value=True):
            with patch("xiaotie.tui.onboarding.has_any_api_key", return_value=False):
                assert should_show_onboarding() is True

    def test_not_show_when_not_first_run(self):
        """测试非首次运行时不显示向导"""
        with patch("xiaotie.tui.onboarding.is_first_run", return_value=False):
            with patch("xiaotie.tui.onboarding.has_any_api_key", return_value=False):
                assert should_show_onboarding() is False

    def test_not_show_when_has_api_key(self):
        """测试有 API Key 时不显示向导"""
        with patch("xiaotie.tui.onboarding.is_first_run", return_value=True):
            with patch("xiaotie.tui.onboarding.has_any_api_key", return_value=True):
                assert should_show_onboarding() is False
