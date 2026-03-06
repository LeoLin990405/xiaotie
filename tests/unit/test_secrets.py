"""SecretManager 单元测试"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from xiaotie.secrets import SecretManager, _mask_value, _resolve_value, _resolve_dict


# ---------------------------------------------------------------------------
# Helpers - mock keyring module
# ---------------------------------------------------------------------------

def _make_mock_keyring():
    """Create a mock keyring module with controllable storage"""
    mock_kr = MagicMock()
    mock_kr.get_keyring = MagicMock()
    mock_kr.get_password = MagicMock(return_value=None)
    mock_kr.set_password = MagicMock()
    mock_kr.delete_password = MagicMock()
    return mock_kr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_keyring():
    return _make_mock_keyring()


@pytest.fixture
def mgr_with_keyring(mock_keyring):
    """SecretManager with keyring available"""
    with patch.dict(sys.modules, {"keyring": mock_keyring}):
        with patch("xiaotie.secrets._keyring_available", return_value=True):
            mgr = SecretManager()
            mgr._has_keyring = True
            yield mgr


@pytest.fixture
def mgr_no_keyring():
    """SecretManager without keyring"""
    with patch("xiaotie.secrets._keyring_available", return_value=False):
        mgr = SecretManager()
        mgr._has_keyring = False
        return mgr


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_from_keyring(self, mgr_with_keyring, mock_keyring):
        mock_keyring.get_password.return_value = "secret-value"
        result = mgr_with_keyring.get("api_key")
        assert result == "secret-value"
        mock_keyring.get_password.assert_called_with("xiaotie", "api_key")

    def test_get_fallback_to_env(self, mgr_with_keyring, mock_keyring):
        mock_keyring.get_password.return_value = None
        with patch.dict(os.environ, {"XIAOTIE_API_KEY": "env-value"}):
            result = mgr_with_keyring.get("api_key")
            assert result == "env-value"

    def test_get_from_env_no_keyring(self, mgr_no_keyring):
        with patch.dict(os.environ, {"XIAOTIE_TEST_KEY": "from-env"}):
            result = mgr_no_keyring.get("test_key")
            assert result == "from-env"

    def test_get_returns_none_when_not_found(self, mgr_with_keyring, mock_keyring):
        mock_keyring.get_password.return_value = None
        for k in ["XIAOTIE_MISSING_KEY", "MISSING_KEY"]:
            os.environ.pop(k, None)
        result = mgr_with_keyring.get("missing_key")
        assert result is None

    def test_get_uppercase_env_fallback(self, mgr_no_keyring):
        with patch.dict(os.environ, {"MY_TOKEN": "val"}):
            result = mgr_no_keyring.get("my_token")
            assert result == "val"


# ---------------------------------------------------------------------------
# set()
# ---------------------------------------------------------------------------

class TestSet:
    def test_set_to_keyring(self, mgr_with_keyring, mock_keyring):
        result = mgr_with_keyring.set("api_key", "new-value")
        assert result is True
        mock_keyring.set_password.assert_called_once_with("xiaotie", "api_key", "new-value")

    def test_set_to_keyring_unavailable(self, mgr_no_keyring):
        result = mgr_no_keyring.set("api_key", "value", backend="keyring")
        assert result is False

    def test_set_to_env(self, mgr_no_keyring):
        result = mgr_no_keyring.set("test_key", "env-val", backend="env")
        assert result is True
        assert os.environ.get("XIAOTIE_TEST_KEY") == "env-val"
        del os.environ["XIAOTIE_TEST_KEY"]

    def test_set_unknown_backend(self, mgr_no_keyring):
        result = mgr_no_keyring.set("key", "val", backend="unknown")
        assert result is False

    def test_set_keyring_exception(self, mgr_with_keyring, mock_keyring):
        mock_keyring.set_password.side_effect = Exception("keyring error")
        result = mgr_with_keyring.set("api_key", "value")
        assert result is False


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_from_keyring(self, mgr_with_keyring, mock_keyring):
        result = mgr_with_keyring.delete("api_key")
        assert result is True
        mock_keyring.delete_password.assert_called_once_with("xiaotie", "api_key")

    def test_delete_from_env(self, mgr_no_keyring):
        os.environ["XIAOTIE_MY_KEY"] = "val"
        result = mgr_no_keyring.delete("my_key")
        assert result is True
        assert "XIAOTIE_MY_KEY" not in os.environ

    def test_delete_not_found(self, mgr_no_keyring):
        for k in ["XIAOTIE_NONEXISTENT", "NONEXISTENT"]:
            os.environ.pop(k, None)
        result = mgr_no_keyring.delete("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# list_keys()
# ---------------------------------------------------------------------------

class TestListKeys:
    def test_list_keys_from_keyring(self, mgr_with_keyring, mock_keyring):
        def side_effect(service, key):
            if key == "api_key":
                return "sk-1234567890abcdef"
            return None
        mock_keyring.get_password.side_effect = side_effect
        keys = mgr_with_keyring.list_keys()
        found = [k for k in keys if k["key"] == "api_key"]
        assert len(found) == 1
        assert found[0]["source"] == "keyring"
        assert "****" in found[0]["masked_value"]

    def test_list_keys_from_env(self, mgr_no_keyring):
        with patch.dict(os.environ, {"XIAOTIE_API_KEY": "test-api-key-value"}):
            keys = mgr_no_keyring.list_keys()
            found = [k for k in keys if k["key"] == "api_key"]
            assert len(found) == 1
            assert found[0]["source"].startswith("env:")


# ---------------------------------------------------------------------------
# resolve_config()
# ---------------------------------------------------------------------------

class TestResolveConfig:
    def test_resolve_secret_placeholder(self, mgr_with_keyring, mock_keyring):
        mock_keyring.get_password.return_value = "resolved-secret"
        config = {"api_key": "${secret:my_api_key}"}
        result = mgr_with_keyring.resolve_config(config)
        assert result["api_key"] == "resolved-secret"

    def test_resolve_env_placeholder(self, mgr_no_keyring):
        with patch.dict(os.environ, {"MY_VAR": "env-resolved"}):
            config = {"host": "${env:MY_VAR}"}
            result = mgr_no_keyring.resolve_config(config)
            assert result["host"] == "env-resolved"

    def test_resolve_nested_dict(self, mgr_no_keyring):
        with patch.dict(os.environ, {"DB_HOST": "localhost"}):
            config = {
                "database": {
                    "host": "${env:DB_HOST}",
                    "port": 5432,
                }
            }
            result = mgr_no_keyring.resolve_config(config)
            assert result["database"]["host"] == "localhost"
            assert result["database"]["port"] == 5432

    def test_resolve_list_values(self, mgr_no_keyring):
        with patch.dict(os.environ, {"TOKEN_A": "a", "TOKEN_B": "b"}):
            config = {"tokens": ["${env:TOKEN_A}", "${env:TOKEN_B}"]}
            result = mgr_no_keyring.resolve_config(config)
            assert result["tokens"] == ["a", "b"]

    def test_resolve_missing_keeps_placeholder(self, mgr_no_keyring):
        for k in ["XIAOTIE_MISSING", "MISSING"]:
            os.environ.pop(k, None)
        config = {"key": "${secret:missing}"}
        result = mgr_no_keyring.resolve_config(config)
        assert result["key"] == "${secret:missing}"

    def test_resolve_non_string_passthrough(self, mgr_no_keyring):
        config = {"count": 42, "enabled": True}
        result = mgr_no_keyring.resolve_config(config)
        assert result == config


# ---------------------------------------------------------------------------
# _mask_value
# ---------------------------------------------------------------------------

class TestMaskValue:
    def test_short_string_fully_masked(self):
        assert _mask_value("12345678") == "****"

    def test_short_string_boundary(self):
        assert _mask_value("1234567") == "****"

    def test_long_string_partial_mask(self):
        result = _mask_value("abcdefghijk")
        assert result == "abcd****hijk"

    def test_exactly_9_chars(self):
        result = _mask_value("123456789")
        assert result == "1234****6789"


# ---------------------------------------------------------------------------
# migrate_config
# ---------------------------------------------------------------------------

class TestMigrateConfig:
    def test_migrate_no_keyring(self, mgr_no_keyring):
        result = mgr_no_keyring.migrate_config("/fake/config.yaml")
        assert result == []

    def test_migrate_config_success(self, mgr_with_keyring, mock_keyring, tmp_path):
        yaml = pytest.importorskip("yaml")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "api_key: sk1234567890abcdefghij\nname: test\n"
        )
        migrated = mgr_with_keyring.migrate_config(str(config_file))
        assert "api_key" in migrated
        mock_keyring.set_password.assert_called()
        updated = yaml.safe_load(config_file.read_text())
        assert "${secret:" in updated["api_key"]
        assert updated["name"] == "test"

    def test_migrate_skips_placeholders(self, mgr_with_keyring, mock_keyring, tmp_path):
        pytest.importorskip("yaml")
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: ${secret:already_migrated}\n")
        migrated = mgr_with_keyring.migrate_config(str(config_file))
        assert migrated == []

    def test_migrate_missing_file(self, mgr_with_keyring):
        result = mgr_with_keyring.migrate_config("/nonexistent/config.yaml")
        assert result == []
