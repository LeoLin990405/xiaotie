"""SecretManager 集成测试 - 配置加载与 CLI 注册"""

from __future__ import annotations

import os
import sys
from typing import Optional
from unittest.mock import MagicMock, patch

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_keyring(storage: Optional[dict] = None):
    """Create a mock keyring with optional pre-loaded storage"""
    store = storage or {}
    mock_kr = MagicMock()
    mock_kr.get_keyring = MagicMock()
    mock_kr.get_password = MagicMock(side_effect=lambda svc, key: store.get(key))
    mock_kr.set_password = MagicMock()
    mock_kr.delete_password = MagicMock()
    return mock_kr


# ---------------------------------------------------------------------------
# Config loading resolves ${secret:...}
# ---------------------------------------------------------------------------


class TestConfigSecretResolution:
    """Test that Config.from_yaml resolves secret placeholders"""

    def test_resolve_secret_in_config(self, tmp_path):
        """${secret:api_key} should be resolved from keyring during config load"""
        mock_kr = _make_mock_keyring({"api_key": "sk-resolved-from-keyring"})

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {
                        "api_key": "${secret:api_key}",
                        "api_base": "https://token-plan-sgp.xiaomimimo.com/anthropic",
                        "model": "mimo-v2-pro",
                        "provider": "mimo",
                    },
                    "agent": {
                        "max_steps": 10,
                        "workspace_dir": str(tmp_path),
                    },
                }
            )
        )

        with patch.dict(sys.modules, {"keyring": mock_kr}):
            with patch("xiaotie.secrets._keyring_available", return_value=True):
                from xiaotie.config import Config

                cfg = Config.from_yaml(config_file)

        assert cfg.llm.api_key == "sk-resolved-from-keyring"

    def test_resolve_env_in_config(self, tmp_path):
        """${env:MY_API_KEY} should be resolved from environment"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {
                        "api_key": "${env:TEST_XIAOTIE_API_KEY}",
                        "api_base": "https://token-plan-sgp.xiaomimimo.com/anthropic",
                        "model": "mimo-v2-pro",
                        "provider": "mimo",
                    },
                    "agent": {
                        "max_steps": 10,
                        "workspace_dir": str(tmp_path),
                    },
                }
            )
        )

        with patch.dict(os.environ, {"TEST_XIAOTIE_API_KEY": "sk-from-env-var"}):
            with patch("xiaotie.secrets._keyring_available", return_value=False):
                from xiaotie.config import Config

                cfg = Config.from_yaml(config_file)

        assert cfg.llm.api_key == "sk-from-env-var"

    def test_graceful_fallback_when_secret_manager_fails(self, tmp_path):
        """If SecretManager raises, config loading should continue with raw values"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {
                        "api_key": "raw-key-value",
                        "api_base": "https://token-plan-sgp.xiaomimimo.com/anthropic",
                        "model": "mimo-v2-pro",
                        "provider": "mimo",
                    },
                    "agent": {
                        "max_steps": 10,
                        "workspace_dir": str(tmp_path),
                    },
                }
            )
        )

        with patch("xiaotie.secrets.get_secret_manager", side_effect=RuntimeError("boom")):
            from xiaotie.config import Config

            cfg = Config.from_yaml(config_file)

        assert cfg.llm.api_key == "raw-key-value"

    def test_unresolved_placeholder_stays_as_is(self, tmp_path):
        """If secret not found, placeholder stays in config value"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "llm": {
                        "api_key": "${secret:nonexistent}",
                        "api_base": "https://token-plan-sgp.xiaomimimo.com/anthropic",
                        "model": "mimo-v2-pro",
                        "provider": "mimo",
                    },
                    "agent": {
                        "max_steps": 10,
                        "workspace_dir": str(tmp_path),
                    },
                }
            )
        )

        # The placeholder stays unresolved since the secret doesn't exist
        with patch("xiaotie.secrets._keyring_available", return_value=False):
            from xiaotie.config import Config

            cfg = Config.from_yaml(config_file)

        # Unresolved placeholder remains as the api_key value
        assert cfg.llm.api_key == "${secret:nonexistent}"


# ---------------------------------------------------------------------------
# CLI command registration
# ---------------------------------------------------------------------------


class TestSecretCommandRegistration:
    """Test that SecretCommands is registered in the Commands mixin chain"""

    def test_secret_command_exists(self):
        """Commands class should have cmd_secret method"""
        from xiaotie.commands import Commands

        assert hasattr(Commands, "cmd_secret"), "cmd_secret not found in Commands"

    def test_secret_alias_exists(self):
        """SecretCommands should contribute 'sec' alias"""
        from xiaotie.commands.secret_cmd import SecretCommands

        assert "sec" in SecretCommands.ALIASES
        assert SecretCommands.ALIASES["sec"] == "secret"
