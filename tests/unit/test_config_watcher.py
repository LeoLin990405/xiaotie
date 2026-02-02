"""配置热重载系统测试"""

import tempfile
import threading
import time
from pathlib import Path

import pytest
import yaml

from xiaotie.config_watcher import (
    ConfigChange,
    ConfigManager,
    ConfigSnapshot,
    ConfigValidationError,
    ConfigValidator,
    ConfigWatcher,
)


class TestConfigSnapshot:
    """ConfigSnapshot 测试"""

    def test_from_dict(self):
        """测试从字典创建"""
        data = {"key": "value", "nested": {"inner": 123}}
        snapshot = ConfigSnapshot.from_dict(data, source="test.yaml")
        assert snapshot.data == data
        assert snapshot.source == "test.yaml"
        assert len(snapshot.hash) == 32  # MD5 哈希

    def test_get_simple(self):
        """测试简单获取"""
        snapshot = ConfigSnapshot.from_dict({"key": "value"})
        assert snapshot.get("key") == "value"
        assert snapshot.get("missing") is None
        assert snapshot.get("missing", "default") == "default"

    def test_get_nested(self):
        """测试嵌套获取"""
        snapshot = ConfigSnapshot.from_dict({
            "level1": {
                "level2": {
                    "level3": "deep_value"
                }
            }
        })
        assert snapshot.get("level1.level2.level3") == "deep_value"
        assert snapshot.get("level1.level2") == {"level3": "deep_value"}
        assert snapshot.get("level1.missing") is None

    def test_hash_deterministic(self):
        """测试哈希确定性"""
        data = {"a": 1, "b": 2}
        snapshot1 = ConfigSnapshot.from_dict(data)
        snapshot2 = ConfigSnapshot.from_dict(data)
        assert snapshot1.hash == snapshot2.hash

    def test_hash_different_for_different_data(self):
        """测试不同数据产生不同哈希"""
        snapshot1 = ConfigSnapshot.from_dict({"key": "value1"})
        snapshot2 = ConfigSnapshot.from_dict({"key": "value2"})
        assert snapshot1.hash != snapshot2.hash


class TestConfigChange:
    """ConfigChange 测试"""

    def test_create_change(self):
        """测试创建变更"""
        change = ConfigChange(
            path="api.key",
            old_value="old",
            new_value="new",
        )
        assert change.path == "api.key"
        assert change.key == "key"
        assert change.old_value == "old"
        assert change.new_value == "new"


class TestConfigValidator:
    """ConfigValidator 测试"""

    def test_require(self):
        """测试必需字段"""
        validator = ConfigValidator().require("api_key")
        snapshot = ConfigSnapshot.from_dict({})
        errors = validator.validate(snapshot)
        assert len(errors) == 1
        assert "api_key" in errors[0]

    def test_require_present(self):
        """测试必需字段存在"""
        validator = ConfigValidator().require("api_key")
        snapshot = ConfigSnapshot.from_dict({"api_key": "test"})
        errors = validator.validate(snapshot)
        assert len(errors) == 0

    def test_add_rule(self):
        """测试添加规则"""
        validator = ConfigValidator().add_rule(
            "max_tokens",
            lambda x: x > 0,
            "max_tokens must be positive"
        )
        snapshot = ConfigSnapshot.from_dict({"max_tokens": -1})
        errors = validator.validate(snapshot)
        assert len(errors) == 1
        assert "positive" in errors[0]

    def test_rule_passes(self):
        """测试规则通过"""
        validator = ConfigValidator().add_rule(
            "max_tokens",
            lambda x: x > 0,
            "max_tokens must be positive"
        )
        snapshot = ConfigSnapshot.from_dict({"max_tokens": 100})
        errors = validator.validate(snapshot)
        assert len(errors) == 0

    def test_multiple_rules(self):
        """测试多个规则"""
        validator = (
            ConfigValidator()
            .require("api_key")
            .require("model")
            .add_rule("max_tokens", lambda x: x > 0, "must be positive")
            .add_rule("max_tokens", lambda x: x < 10000, "must be < 10000")
        )
        snapshot = ConfigSnapshot.from_dict({
            "api_key": "test",
            "max_tokens": 50000,
        })
        errors = validator.validate(snapshot)
        assert len(errors) == 2  # missing model + max_tokens > 10000


class TestConfigWatcher:
    """ConfigWatcher 测试"""

    @pytest.fixture
    def config_file(self):
        """创建临时配置文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"key": "value"}, f)
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_create_watcher(self, config_file):
        """测试创建监听器"""
        watcher = ConfigWatcher(config_file)
        # macOS: /var is symlink to /private/var, compare resolved paths
        assert watcher.path.resolve() == config_file.resolve()
        assert not watcher.is_running

    def test_start_stop(self, config_file):
        """测试启动和停止"""
        watcher = ConfigWatcher(config_file, poll_interval=0.1)
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_get_current(self, config_file):
        """测试获取当前配置"""
        watcher = ConfigWatcher(config_file)
        snapshot = watcher.get_current()
        assert snapshot is not None
        assert snapshot.get("key") == "value"

    def test_on_change_callback(self, config_file):
        """测试变更回调"""
        changes = []
        watcher = ConfigWatcher(config_file, poll_interval=0.1)
        watcher.on_change(lambda s: changes.append(s))
        watcher.start()

        # 等待初始加载
        time.sleep(0.2)

        # 修改文件
        with open(config_file, "w") as f:
            yaml.dump({"key": "new_value"}, f)

        # 等待检测变化
        time.sleep(0.3)
        watcher.stop()

        assert len(changes) >= 1
        assert changes[-1].get("key") == "new_value"

    def test_validation_error(self, config_file):
        """测试验证错误"""
        errors = []
        validator = ConfigValidator().require("required_field")
        watcher = ConfigWatcher(config_file, poll_interval=0.1, validator=validator)
        watcher.on_error(lambda e: errors.append(e))
        watcher.start()

        # 修改文件（缺少必需字段）
        time.sleep(0.2)
        with open(config_file, "w") as f:
            yaml.dump({"other": "value"}, f)

        time.sleep(0.3)
        watcher.stop()

        # 应该有验证错误
        assert any(isinstance(e, ConfigValidationError) for e in errors)


class TestConfigManager:
    """ConfigManager 测试"""

    @pytest.fixture
    def config_file(self):
        """创建临时配置文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "api_key": "test-key",
                "model": "gpt-4",
                "max_tokens": 1000,
            }, f)
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_load(self, config_file):
        """测试加载配置"""
        manager = ConfigManager(config_file)
        snapshot = manager.load()
        assert snapshot.get("api_key") == "test-key"
        assert snapshot.get("model") == "gpt-4"

    def test_get(self, config_file):
        """测试获取配置值"""
        manager = ConfigManager(config_file)
        assert manager.get("api_key") == "test-key"
        assert manager.get("missing", "default") == "default"

    def test_get_all(self, config_file):
        """测试获取所有配置"""
        manager = ConfigManager(config_file)
        all_config = manager.get_all()
        assert "api_key" in all_config
        assert "model" in all_config

    def test_reload(self, config_file):
        """测试重新加载"""
        manager = ConfigManager(config_file)
        manager.load()

        # 修改文件
        with open(config_file, "w") as f:
            yaml.dump({"api_key": "new-key"}, f)

        snapshot = manager.reload()
        assert snapshot.get("api_key") == "new-key"

    def test_rollback(self, config_file):
        """测试回滚"""
        manager = ConfigManager(config_file)
        manager.load()

        # 修改并重载
        with open(config_file, "w") as f:
            yaml.dump({"api_key": "new-key"}, f)
        manager.reload()

        assert manager.get("api_key") == "new-key"

        # 回滚
        snapshot = manager.rollback()
        assert snapshot is not None
        assert snapshot.get("api_key") == "test-key"

    def test_rollback_empty_history(self, config_file):
        """测试空历史回滚"""
        manager = ConfigManager(config_file)
        manager.load()
        result = manager.rollback()
        assert result is None

    def test_history_limit(self, config_file):
        """测试历史限制"""
        manager = ConfigManager(config_file, max_history=3)
        manager.load()

        # 多次重载
        for i in range(5):
            with open(config_file, "w") as f:
                yaml.dump({"version": i}, f)
            manager.reload()

        assert manager.history_count == 3

    def test_validator(self, config_file):
        """测试验证器"""
        manager = ConfigManager(config_file)
        manager.add_validator(
            ConfigValidator()
            .require("api_key")
            .add_rule("max_tokens", lambda x: x > 0, "must be positive")
        )
        snapshot = manager.load()
        assert snapshot is not None

    def test_validator_error(self, config_file):
        """测试验证错误"""
        # 写入无效配置
        with open(config_file, "w") as f:
            yaml.dump({"other": "value"}, f)

        manager = ConfigManager(config_file)
        manager.add_validator(ConfigValidator().require("api_key"))

        with pytest.raises(ConfigValidationError):
            manager.load()

    def test_on_change_callback(self, config_file):
        """测试变更回调"""
        changes = []
        manager = ConfigManager(config_file)
        manager.on_change(lambda old, new: changes.append((old, new)))
        manager.load()

        # 修改并重载
        with open(config_file, "w") as f:
            yaml.dump({"api_key": "new-key"}, f)
        manager.reload()

        assert len(changes) == 1
        old, new = changes[0]
        assert old.get("api_key") == "test-key"
        assert new.get("api_key") == "new-key"

    def test_start_stop_watching(self, config_file):
        """测试启动和停止监听"""
        manager = ConfigManager(config_file)
        manager.load()
        manager.start_watching(poll_interval=0.1)
        assert manager.is_watching
        manager.stop_watching()
        assert not manager.is_watching

    def test_auto_reload_on_change(self, config_file):
        """测试自动重载"""
        changes = []
        manager = ConfigManager(config_file)
        manager.on_change(lambda old, new: changes.append((old, new)))
        manager.load()
        manager.start_watching(poll_interval=0.1)

        # 等待初始化
        time.sleep(0.2)

        # 修改文件
        with open(config_file, "w") as f:
            yaml.dump({"api_key": "auto-reloaded"}, f)

        # 等待检测
        time.sleep(0.3)
        manager.stop_watching()

        assert manager.get("api_key") == "auto-reloaded"
        assert len(changes) >= 1

    def test_current_hash(self, config_file):
        """测试当前哈希"""
        manager = ConfigManager(config_file)
        assert manager.current_hash is None
        manager.load()
        assert manager.current_hash is not None
        assert len(manager.current_hash) == 32


class TestConfigIntegration:
    """配置集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "api_key": "initial-key",
                "model": "gpt-4",
                "settings": {
                    "max_tokens": 1000,
                    "temperature": 0.7,
                }
            }, f)
            config_path = Path(f.name)

        try:
            # 创建管理器
            manager = ConfigManager(config_path, max_history=5)
            manager.add_validator(
                ConfigValidator()
                .require("api_key")
                .add_rule("settings.max_tokens", lambda x: x > 0, "must be positive")
            )

            # 加载
            manager.load()
            assert manager.get("api_key") == "initial-key"
            assert manager.get("settings.max_tokens") == 1000

            # 修改并重载
            with open(config_path, "w") as f:
                yaml.dump({
                    "api_key": "updated-key",
                    "model": "gpt-4-turbo",
                    "settings": {
                        "max_tokens": 2000,
                        "temperature": 0.5,
                    }
                }, f)
            manager.reload()
            assert manager.get("api_key") == "updated-key"
            assert manager.get("settings.max_tokens") == 2000

            # 回滚
            manager.rollback()
            assert manager.get("api_key") == "initial-key"
            assert manager.get("settings.max_tokens") == 1000

        finally:
            config_path.unlink(missing_ok=True)
