"""
快捷键自定义模块

提供快捷键绑定和自定义功能：
- 快捷键解析
- 快捷键绑定管理
- 配置文件加载

使用示例:
    from xiaotie.keybindings import KeyBindings, KeyBinding

    # 创建快捷键管理器
    kb = KeyBindings()

    # 注册快捷键
    kb.bind("ctrl+s", "save")
    kb.bind("ctrl+shift+p", "command_palette")

    # 检查快捷键
    action = kb.get_action("ctrl+s")  # "save"
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Set
import json
import re
from pathlib import Path


# 修饰键
MODIFIERS = {"ctrl", "alt", "shift", "meta", "cmd", "super"}

# 特殊键映射
SPECIAL_KEYS = {
    "enter": "enter",
    "return": "enter",
    "esc": "escape",
    "escape": "escape",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "insert": "insert",
    "ins": "insert",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}

# 默认快捷键
DEFAULT_BINDINGS = {
    # 文件操作
    "ctrl+s": "save",
    "ctrl+o": "open",
    "ctrl+n": "new",
    "ctrl+w": "close",

    # 编辑操作
    "ctrl+z": "undo",
    "ctrl+y": "redo",
    "ctrl+shift+z": "redo",
    "ctrl+c": "copy",
    "ctrl+x": "cut",
    "ctrl+v": "paste",
    "ctrl+a": "select_all",

    # 搜索
    "ctrl+f": "find",
    "ctrl+h": "replace",
    "ctrl+g": "goto_line",

    # 视图
    "ctrl+shift+p": "command_palette",
    "ctrl+`": "toggle_terminal",
    "ctrl+b": "toggle_sidebar",
    "ctrl+\\": "split_editor",

    # 导航
    "ctrl+p": "quick_open",
    "ctrl+tab": "next_tab",
    "ctrl+shift+tab": "prev_tab",

    # Agent 操作
    "ctrl+enter": "submit",
    "ctrl+shift+enter": "submit_and_run",
    "escape": "cancel",
    "ctrl+l": "clear",
}


@dataclass
class KeyBinding:
    """快捷键绑定"""
    key: str  # 标准化的快捷键字符串
    action: str  # 动作名称
    description: Optional[str] = None
    enabled: bool = True
    context: Optional[str] = None  # 上下文（如 "editor", "terminal"）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "action": self.action,
            "description": self.description,
            "enabled": self.enabled,
            "context": self.context,
        }


class KeyParseError(Exception):
    """快捷键解析错误"""
    pass


class KeyParser:
    """快捷键解析器"""

    @staticmethod
    def parse(key_string: str) -> tuple:
        """
        解析快捷键字符串

        Args:
            key_string: 如 "ctrl+shift+s", "alt+enter"

        Returns:
            (modifiers: frozenset, key: str)
        """
        parts = key_string.lower().strip().split("+")
        if not parts:
            raise KeyParseError("Empty key string")

        modifiers = set()
        key = None

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if part in MODIFIERS:
                # 标准化修饰键
                if part in ("cmd", "super"):
                    part = "meta"
                modifiers.add(part)
            else:
                if key is not None:
                    raise KeyParseError(f"Multiple keys specified: {key}, {part}")
                # 标准化特殊键
                key = SPECIAL_KEYS.get(part, part)

        if key is None:
            raise KeyParseError("No key specified")

        return frozenset(modifiers), key

    @staticmethod
    def normalize(key_string: str) -> str:
        """
        标准化快捷键字符串

        Args:
            key_string: 如 "Ctrl+Shift+S", "CTRL+s"

        Returns:
            标准化的字符串，如 "ctrl+shift+s"
        """
        modifiers, key = KeyParser.parse(key_string)

        # 按固定顺序排列修饰键
        modifier_order = ["ctrl", "alt", "shift", "meta"]
        sorted_modifiers = [m for m in modifier_order if m in modifiers]

        parts = sorted_modifiers + [key]
        return "+".join(parts)

    @staticmethod
    def matches(key_string1: str, key_string2: str) -> bool:
        """检查两个快捷键是否匹配"""
        try:
            return KeyParser.normalize(key_string1) == KeyParser.normalize(key_string2)
        except KeyParseError:
            return False


class KeyBindings:
    """快捷键绑定管理器"""

    def __init__(self, load_defaults: bool = True):
        self._bindings: Dict[str, KeyBinding] = {}
        self._action_to_key: Dict[str, str] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

        if load_defaults:
            self._load_defaults()

    def _load_defaults(self):
        """加载默认快捷键"""
        for key, action in DEFAULT_BINDINGS.items():
            self.bind(key, action)

    def bind(
        self,
        key: str,
        action: str,
        description: Optional[str] = None,
        context: Optional[str] = None,
    ) -> "KeyBindings":
        """
        绑定快捷键

        Args:
            key: 快捷键字符串
            action: 动作名称
            description: 描述
            context: 上下文
        """
        normalized_key = KeyParser.normalize(key)

        binding = KeyBinding(
            key=normalized_key,
            action=action,
            description=description,
            context=context,
        )

        self._bindings[normalized_key] = binding
        self._action_to_key[action] = normalized_key

        return self

    def unbind(self, key: str) -> bool:
        """解除快捷键绑定"""
        try:
            normalized_key = KeyParser.normalize(key)
        except KeyParseError:
            return False

        if normalized_key in self._bindings:
            binding = self._bindings[normalized_key]
            del self._bindings[normalized_key]
            if binding.action in self._action_to_key:
                del self._action_to_key[binding.action]
            return True
        return False

    def get_binding(self, key: str) -> Optional[KeyBinding]:
        """获取快捷键绑定"""
        try:
            normalized_key = KeyParser.normalize(key)
        except KeyParseError:
            return None

        return self._bindings.get(normalized_key)

    def get_action(self, key: str) -> Optional[str]:
        """获取快捷键对应的动作"""
        binding = self.get_binding(key)
        return binding.action if binding and binding.enabled else None

    def get_key(self, action: str) -> Optional[str]:
        """获取动作对应的快捷键"""
        return self._action_to_key.get(action)

    def is_bound(self, key: str) -> bool:
        """检查快捷键是否已绑定"""
        return self.get_binding(key) is not None

    def enable(self, key: str) -> bool:
        """启用快捷键"""
        binding = self.get_binding(key)
        if binding:
            binding.enabled = True
            return True
        return False

    def disable(self, key: str) -> bool:
        """禁用快捷键"""
        binding = self.get_binding(key)
        if binding:
            binding.enabled = False
            return True
        return False

    def on(self, action: str, callback: Callable) -> "KeyBindings":
        """注册动作回调"""
        if action not in self._callbacks:
            self._callbacks[action] = []
        self._callbacks[action].append(callback)
        return self

    def trigger(self, key: str, **kwargs) -> bool:
        """触发快捷键"""
        action = self.get_action(key)
        if action and action in self._callbacks:
            for callback in self._callbacks[action]:
                try:
                    callback(**kwargs)
                except Exception:
                    pass
            return True
        return False

    def get_all_bindings(self) -> List[KeyBinding]:
        """获取所有绑定"""
        return list(self._bindings.values())

    def get_bindings_by_context(self, context: str) -> List[KeyBinding]:
        """按上下文获取绑定"""
        return [b for b in self._bindings.values() if b.context == context]

    def to_dict(self) -> Dict[str, str]:
        """导出为字典"""
        return {b.key: b.action for b in self._bindings.values()}

    def to_json(self) -> str:
        """导出为 JSON"""
        return json.dumps(self.to_dict(), indent=2)

    def load_from_dict(self, bindings: Dict[str, str]):
        """从字典加载"""
        for key, action in bindings.items():
            self.bind(key, action)

    def load_from_json(self, json_string: str):
        """从 JSON 加载"""
        bindings = json.loads(json_string)
        self.load_from_dict(bindings)

    def load_from_file(self, file_path: str) -> bool:
        """从文件加载"""
        path = Path(file_path)
        if not path.exists():
            return False

        try:
            content = path.read_text()
            self.load_from_json(content)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def save_to_file(self, file_path: str) -> bool:
        """保存到文件"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.to_json())
            return True
        except IOError:
            return False

    def reset(self):
        """重置为默认"""
        self._bindings.clear()
        self._action_to_key.clear()
        self._load_defaults()


# 全局实例
_keybindings: Optional[KeyBindings] = None


def get_keybindings() -> KeyBindings:
    """获取全局快捷键管理器"""
    global _keybindings
    if _keybindings is None:
        _keybindings = KeyBindings()
    return _keybindings


def set_keybindings(kb: KeyBindings):
    """设置全局快捷键管理器"""
    global _keybindings
    _keybindings = kb


def reset_keybindings():
    """重置全局快捷键管理器"""
    global _keybindings
    _keybindings = None


def bind(key: str, action: str, **kwargs) -> KeyBindings:
    """绑定快捷键"""
    return get_keybindings().bind(key, action, **kwargs)


def unbind(key: str) -> bool:
    """解除绑定"""
    return get_keybindings().unbind(key)


def get_action(key: str) -> Optional[str]:
    """获取动作"""
    return get_keybindings().get_action(key)


def get_key(action: str) -> Optional[str]:
    """获取快捷键"""
    return get_keybindings().get_key(action)
