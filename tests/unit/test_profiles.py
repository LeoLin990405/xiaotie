"""profiles.py 单元测试"""

import os
import tempfile

import pytest

from xiaotie.profiles import (
    ProfileConfig,
    ProfileManager,
    PRESET_PROFILES,
    create_preset_profiles,
)


@pytest.fixture
def profiles_dir(tmp_path):
    return str(tmp_path / "profiles")


@pytest.fixture
def manager(profiles_dir):
    return ProfileManager(profiles_dir=profiles_dir)


# ---------------------------------------------------------------------------
# ProfileConfig
# ---------------------------------------------------------------------------


class TestProfileConfig:
    def test_defaults(self):
        cfg = ProfileConfig()
        assert cfg.name == "default"
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096
        assert cfg.stream is True
        assert cfg.enable_thinking is True
        assert "bash" in cfg.enabled_tools
        assert cfg.disabled_tools == []

    def test_custom_values(self):
        cfg = ProfileConfig(
            name="test",
            provider="anthropic",
            model="claude-3",
            temperature=0.3,
        )
        assert cfg.name == "test"
        assert cfg.provider == "anthropic"
        assert cfg.temperature == 0.3


# ---------------------------------------------------------------------------
# ProfileManager
# ---------------------------------------------------------------------------


class TestProfileManager:
    def test_creates_profiles_dir(self, profiles_dir):
        ProfileManager(profiles_dir=profiles_dir)
        assert os.path.isdir(profiles_dir)

    def test_default_profiles_dir(self):
        mgr = ProfileManager()
        assert "xiaotie" in str(mgr.profiles_dir)

    def test_list_profiles_empty(self, manager):
        assert manager.list_profiles() == []

    def test_save_and_load_profile(self, manager):
        cfg = ProfileConfig(name="test", description="Test profile")
        manager.save_profile(cfg)
        loaded = manager.load_profile("test")
        assert loaded.name == "test"
        assert loaded.description == "Test profile"

    def test_load_cached(self, manager):
        cfg = ProfileConfig(name="cached")
        manager.save_profile(cfg)
        # First load populates cache
        manager.load_profile("cached")
        # Second load should hit cache
        loaded = manager.load_profile("cached")
        assert loaded.name == "cached"

    def test_load_nonexistent_raises(self, manager):
        with pytest.raises(FileNotFoundError, match="Profile"):
            manager.load_profile("nonexistent")

    def test_list_profiles(self, manager):
        manager.save_profile(ProfileConfig(name="alpha"))
        manager.save_profile(ProfileConfig(name="beta"))
        profiles = manager.list_profiles()
        assert "alpha" in profiles
        assert "beta" in profiles
        assert profiles == sorted(profiles)

    def test_delete_profile(self, manager):
        manager.save_profile(ProfileConfig(name="del_me"))
        assert "del_me" in manager.list_profiles()
        manager.delete_profile("del_me")
        assert "del_me" not in manager.list_profiles()

    def test_delete_nonexistent_does_not_raise(self, manager):
        manager.delete_profile("does_not_exist")  # should not raise

    def test_create_default_profile(self, manager):
        cfg = manager.create_default_profile()
        assert cfg.name == "default"
        assert "default" in manager.list_profiles()

    def test_get_or_create_default_creates(self, manager):
        cfg = manager.get_or_create_default()
        assert cfg.name == "default"
        assert "default" in manager.list_profiles()

    def test_get_or_create_default_loads_existing(self, manager):
        manager.save_profile(ProfileConfig(name="default", description="existing"))
        cfg = manager.get_or_create_default()
        assert cfg.description == "existing"

    def test_set_current_profile(self, manager):
        manager.save_profile(ProfileConfig(name="active"))
        manager.set_current_profile("active")
        current = manager.get_current_profile()
        assert current is not None
        assert current.name == "active"

    def test_set_current_nonexistent_raises(self, manager):
        with pytest.raises(ValueError, match="Profile"):
            manager.set_current_profile("nonexistent")

    def test_get_current_profile_none(self, manager):
        assert manager.get_current_profile() is None

    def test_save_with_optional_fields(self, manager):
        cfg = ProfileConfig(
            name="full",
            api_key="sk-xxx",
            api_base="https://api.example.com",
            system_prompt="You are helpful.",
            system_prompt_path="/tmp/prompt.txt",
            lint_cmd="ruff check",
            test_cmd="pytest",
            env={"FOO": "bar"},
        )
        manager.save_profile(cfg)
        loaded = manager.load_profile("full")
        assert loaded.system_prompt == "You are helpful."
        assert loaded.env == {"FOO": "bar"}


# ---------------------------------------------------------------------------
# Environment variable expansion
# ---------------------------------------------------------------------------


class TestEnvExpansion:
    def test_expand_env_var(self, manager):
        os.environ["XIAOTIE_TEST_KEY"] = "secret123"
        try:
            data = {"api_key": "${XIAOTIE_TEST_KEY}", "model": "gpt-4"}
            result = manager._expand_env_vars(data)
            assert result["api_key"] == "secret123"
            assert result["model"] == "gpt-4"
        finally:
            del os.environ["XIAOTIE_TEST_KEY"]

    def test_expand_missing_env_var(self, manager):
        data = {"api_key": "${MISSING_VAR_XYZ}"}
        result = manager._expand_env_vars(data)
        assert result["api_key"] == ""

    def test_expand_nested_dict(self, manager):
        os.environ["XIAOTIE_NESTED"] = "value"
        try:
            data = {"outer": {"inner": "${XIAOTIE_NESTED}"}}
            result = manager._expand_env_vars(data)
            assert result["outer"]["inner"] == "value"
        finally:
            del os.environ["XIAOTIE_NESTED"]


# ---------------------------------------------------------------------------
# Merge with config
# ---------------------------------------------------------------------------


class TestMergeWithConfig:
    def test_merge_overrides(self, manager):
        base = ProfileConfig(name="base", model="gpt-4", temperature=0.7)
        merged = manager.merge_with_config(base, {"model": "claude-3", "temperature": 0.1})
        assert merged.model == "claude-3"
        assert merged.temperature == 0.1
        assert merged.name == "base"

    def test_merge_keeps_defaults(self, manager):
        base = ProfileConfig(name="base", model="gpt-4")
        merged = manager.merge_with_config(base, {})
        assert merged.model == "gpt-4"

    def test_merge_env(self, manager):
        base = ProfileConfig(name="base", env={"A": "1"})
        merged = manager.merge_with_config(base, {"env": {"B": "2"}})
        assert merged.env == {"A": "1", "B": "2"}


# ---------------------------------------------------------------------------
# Preset profiles
# ---------------------------------------------------------------------------


class TestPresetProfiles:
    def test_presets_exist(self):
        assert "coding" in PRESET_PROFILES
        assert "research" in PRESET_PROFILES
        assert "safe" in PRESET_PROFILES

    def test_coding_profile(self):
        cfg = PRESET_PROFILES["coding"]
        assert cfg.auto_lint is True
        assert cfg.auto_test is True

    def test_safe_profile(self):
        cfg = PRESET_PROFILES["safe"]
        assert cfg.auto_approve_low_risk is False

    def test_create_preset_profiles(self, manager):
        create_preset_profiles(manager)
        profiles = manager.list_profiles()
        assert "coding" in profiles
        assert "research" in profiles
        assert "safe" in profiles

    def test_create_presets_idempotent(self, manager):
        create_preset_profiles(manager)
        create_preset_profiles(manager)  # should not fail
        assert len(manager.list_profiles()) == 3
