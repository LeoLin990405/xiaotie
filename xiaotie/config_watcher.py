"""配置热重载系统

提供运行时配置更新功能：
- 文件系统监听
- 配置验证
- 平滑切换
- 回滚机制
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

import yaml

T = TypeVar("T")


@dataclass
class ConfigChange:
    """配置变更"""

    path: str
    old_value: Any
    new_value: Any
    timestamp: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        """获取配置键"""
        return self.path.split(".")[-1]


@dataclass
class ConfigSnapshot:
    """配置快照"""

    data: Dict[str, Any]
    hash: str
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source: str = "") -> "ConfigSnapshot":
        """从字典创建快照"""
        serialized = yaml.dump(data, sort_keys=True)
        hash_value = hashlib.md5(serialized.encode()).hexdigest()
        return cls(data=data, hash=hash_value, source=source)

    def get(self, path: str, default: Any = None) -> Any:
        """获取配置值（支持点分路径）"""
        keys = path.split(".")
        value = self.data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class ConfigValidationError(Exception):
    """配置验证错误"""

    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


class ConfigValidator:
    """配置验证器"""

    def __init__(self):
        self._rules: Dict[str, List[Callable[[Any], bool]]] = {}
        self._required: Set[str] = set()

    def require(self, path: str) -> "ConfigValidator":
        """标记必需字段"""
        self._required.add(path)
        return self

    def add_rule(self, path: str, rule: Callable[[Any], bool], message: str = "") -> "ConfigValidator":
        """添加验证规则"""
        if path not in self._rules:
            self._rules[path] = []
        self._rules[path].append((rule, message))
        return self

    def validate(self, snapshot: ConfigSnapshot) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []

        # 检查必需字段
        for path in self._required:
            value = snapshot.get(path)
            if value is None:
                errors.append(f"Missing required field: {path}")

        # 检查验证规则
        for path, rules in self._rules.items():
            value = snapshot.get(path)
            if value is not None:
                for rule, message in rules:
                    try:
                        if not rule(value):
                            errors.append(message or f"Validation failed for {path}")
                    except Exception as e:
                        errors.append(f"Validation error for {path}: {e}")

        return errors


class ConfigWatcher:
    """配置文件监听器

    监听配置文件变化并触发回调。

    使用示例:
    ```python
    watcher = ConfigWatcher("config/config.yaml")
    watcher.on_change(lambda snapshot: print(f"Config changed: {snapshot.hash}"))
    watcher.start()

    # 停止监听
    watcher.stop()
    ```
    """

    def __init__(
        self,
        path: Union[str, Path],
        poll_interval: float = 1.0,
        validator: Optional[ConfigValidator] = None,
    ):
        """
        Args:
            path: 配置文件路径
            poll_interval: 轮询间隔（秒）
            validator: 配置验证器
        """
        self.path = Path(path).expanduser().resolve()
        self.poll_interval = poll_interval
        self.validator = validator

        self._callbacks: List[Callable[[ConfigSnapshot], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_hash: Optional[str] = None
        self._last_snapshot: Optional[ConfigSnapshot] = None
        self._last_mtime: float = 0

    def on_change(self, callback: Callable[[ConfigSnapshot], None]) -> "ConfigWatcher":
        """注册变更回调"""
        self._callbacks.append(callback)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> "ConfigWatcher":
        """注册错误回调"""
        self._error_callbacks.append(callback)
        return self

    def start(self) -> None:
        """开始监听"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.poll_interval * 2)
            self._thread = None

    def _watch_loop(self) -> None:
        """监听循环"""
        while self._running:
            try:
                self._check_for_changes()
            except Exception as e:
                self._notify_error(e)
            time.sleep(self.poll_interval)

    def _check_for_changes(self) -> None:
        """检查文件变化"""
        if not self.path.exists():
            return

        # 检查修改时间
        mtime = self.path.stat().st_mtime
        if mtime <= self._last_mtime:
            return

        self._last_mtime = mtime

        # 加载配置
        snapshot = self._load_config()
        if snapshot is None:
            return

        # 检查是否有变化
        if self._last_hash == snapshot.hash:
            return

        # 验证配置
        if self.validator:
            errors = self.validator.validate(snapshot)
            if errors:
                raise ConfigValidationError(
                    f"Config validation failed: {len(errors)} errors",
                    errors=errors,
                )

        # 更新状态
        self._last_hash = snapshot.hash
        self._last_snapshot = snapshot

        # 通知回调
        self._notify_change(snapshot)

    def _load_config(self) -> Optional[ConfigSnapshot]:
        """加载配置文件"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return ConfigSnapshot.from_dict(data, source=str(self.path))
        except Exception as e:
            self._notify_error(e)
            return None

    def _notify_change(self, snapshot: ConfigSnapshot) -> None:
        """通知变更"""
        for callback in self._callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                self._notify_error(e)

    def _notify_error(self, error: Exception) -> None:
        """通知错误"""
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception:
                pass  # 忽略错误回调中的错误

    def get_current(self) -> Optional[ConfigSnapshot]:
        """获取当前配置快照"""
        if self._last_snapshot is None:
            self._last_snapshot = self._load_config()
        return self._last_snapshot

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


class ConfigManager:
    """配置管理器

    提供配置的加载、验证、热重载和回滚功能。

    使用示例:
    ```python
    manager = ConfigManager("config/config.yaml")
    manager.add_validator(
        ConfigValidator()
        .require("api_key")
        .add_rule("max_tokens", lambda x: x > 0, "max_tokens must be positive")
    )

    # 启动热重载
    manager.start_watching()

    # 获取配置
    api_key = manager.get("api_key")

    # 手动重载
    manager.reload()

    # 回滚到上一个版本
    manager.rollback()
    ```
    """

    def __init__(
        self,
        path: Union[str, Path],
        auto_reload: bool = True,
        max_history: int = 10,
    ):
        """
        Args:
            path: 配置文件路径
            auto_reload: 是否自动重载
            max_history: 最大历史版本数
        """
        self.path = Path(path).expanduser().resolve()
        self.auto_reload = auto_reload
        self.max_history = max_history

        self._validator: Optional[ConfigValidator] = None
        self._watcher: Optional[ConfigWatcher] = None
        self._current: Optional[ConfigSnapshot] = None
        self._history: List[ConfigSnapshot] = []
        self._change_callbacks: List[Callable[[ConfigSnapshot, ConfigSnapshot], None]] = []
        self._lock = threading.Lock()

    def add_validator(self, validator: ConfigValidator) -> "ConfigManager":
        """添加验证器"""
        self._validator = validator
        return self

    def on_change(self, callback: Callable[[ConfigSnapshot, ConfigSnapshot], None]) -> "ConfigManager":
        """注册变更回调（接收旧配置和新配置）"""
        self._change_callbacks.append(callback)
        return self

    def load(self) -> ConfigSnapshot:
        """加载配置"""
        with self._lock:
            if not self.path.exists():
                raise FileNotFoundError(f"Config file not found: {self.path}")

            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            snapshot = ConfigSnapshot.from_dict(data, source=str(self.path))

            # 验证
            if self._validator:
                errors = self._validator.validate(snapshot)
                if errors:
                    raise ConfigValidationError(
                        f"Config validation failed: {len(errors)} errors",
                        errors=errors,
                    )

            # 保存历史
            if self._current:
                self._history.append(self._current)
                if len(self._history) > self.max_history:
                    self._history.pop(0)

            old_config = self._current
            self._current = snapshot

            # 通知回调
            if old_config:
                for callback in self._change_callbacks:
                    try:
                        callback(old_config, snapshot)
                    except Exception:
                        pass

            return snapshot

    def reload(self) -> ConfigSnapshot:
        """重新加载配置"""
        return self.load()

    def rollback(self) -> Optional[ConfigSnapshot]:
        """回滚到上一个版本"""
        with self._lock:
            if not self._history:
                return None

            old_config = self._current
            self._current = self._history.pop()

            # 通知回调
            if old_config:
                for callback in self._change_callbacks:
                    try:
                        callback(old_config, self._current)
                    except Exception:
                        pass

            return self._current

    def get(self, path: str, default: Any = None) -> Any:
        """获取配置值"""
        if self._current is None:
            self.load()
        return self._current.get(path, default) if self._current else default

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        if self._current is None:
            self.load()
        return self._current.data if self._current else {}

    def start_watching(self, poll_interval: float = 1.0) -> None:
        """开始监听配置变化"""
        if self._watcher:
            return

        self._watcher = ConfigWatcher(
            self.path,
            poll_interval=poll_interval,
            validator=self._validator,
        )
        self._watcher.on_change(self._on_file_change)
        self._watcher.start()

    def stop_watching(self) -> None:
        """停止监听"""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _on_file_change(self, snapshot: ConfigSnapshot) -> None:
        """文件变化回调"""
        with self._lock:
            # 保存历史
            if self._current:
                self._history.append(self._current)
                if len(self._history) > self.max_history:
                    self._history.pop(0)

            old_config = self._current
            self._current = snapshot

            # 通知回调
            if old_config:
                for callback in self._change_callbacks:
                    try:
                        callback(old_config, snapshot)
                    except Exception:
                        pass

    @property
    def current_hash(self) -> Optional[str]:
        """当前配置哈希"""
        return self._current.hash if self._current else None

    @property
    def history_count(self) -> int:
        """历史版本数量"""
        return len(self._history)

    @property
    def is_watching(self) -> bool:
        """是否正在监听"""
        return self._watcher is not None and self._watcher.is_running
