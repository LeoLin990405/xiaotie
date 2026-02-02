"""
快捷键自定义模块测试
"""

import pytest
import json
import tempfile
from pathlib import Path

from xiaotie.keybindings import (
    KeyBindings,
    KeyBinding,
    KeyParser,
    KeyParseError,
    DEFAULT_BINDINGS,
    get_keybindings,
    set_keybindings,
    reset_keybindings,
    bind,
    unbind,
    get_action,
    get_key,
)


@pytest.fixture(autouse=True)
def reset_global_keybindings():
    """每个测试前重置全局快捷键"""
    reset_keybindings()
    yield
    reset_keybindings()


class TestKeyParser:
    """测试快捷键解析器"""

    def test_parse_simple(self):
        """测试简单解析"""
        modifiers, key = KeyParser.parse("a")
        assert modifiers == frozenset()
        assert key == "a"

    def test_parse_with_ctrl(self):
        """测试带 Ctrl 的解析"""
        modifiers, key = KeyParser.parse("ctrl+s")
        assert modifiers == frozenset({"ctrl"})
        assert key == "s"

    def test_parse_multiple_modifiers(self):
        """测试多个修饰键"""
        modifiers, key = KeyParser.parse("ctrl+shift+s")
        assert modifiers == frozenset({"ctrl", "shift"})
        assert key == "s"

    def test_parse_case_insensitive(self):
        """测试大小写不敏感"""
        modifiers, key = KeyParser.parse("CTRL+SHIFT+S")
        assert modifiers == frozenset({"ctrl", "shift"})
        assert key == "s"

    def test_parse_special_key(self):
        """测试特殊键"""
        modifiers, key = KeyParser.parse("ctrl+enter")
        assert key == "enter"

        modifiers, key = KeyParser.parse("ctrl+esc")
        assert key == "escape"

    def test_parse_cmd_to_meta(self):
        """测试 cmd 转换为 meta"""
        modifiers, key = KeyParser.parse("cmd+s")
        assert "meta" in modifiers

    def test_parse_empty_error(self):
        """测试空字符串错误"""
        with pytest.raises(KeyParseError):
            KeyParser.parse("")

    def test_parse_no_key_error(self):
        """测试无键错误"""
        with pytest.raises(KeyParseError):
            KeyParser.parse("ctrl+shift")

    def test_parse_multiple_keys_error(self):
        """测试多键错误"""
        with pytest.raises(KeyParseError):
            KeyParser.parse("ctrl+a+b")

    def test_normalize(self):
        """测试标准化"""
        assert KeyParser.normalize("ctrl+s") == "ctrl+s"
        assert KeyParser.normalize("CTRL+S") == "ctrl+s"
        assert KeyParser.normalize("shift+ctrl+s") == "ctrl+shift+s"
        assert KeyParser.normalize("s+ctrl") == "ctrl+s"

    def test_matches(self):
        """测试匹配"""
        assert KeyParser.matches("ctrl+s", "CTRL+S")
        assert KeyParser.matches("ctrl+shift+s", "shift+ctrl+s")
        assert not KeyParser.matches("ctrl+s", "ctrl+a")


class TestKeyBinding:
    """测试快捷键绑定"""

    def test_create_binding(self):
        """测试创建绑定"""
        binding = KeyBinding(key="ctrl+s", action="save")
        assert binding.key == "ctrl+s"
        assert binding.action == "save"
        assert binding.enabled is True

    def test_binding_with_description(self):
        """测试带描述的绑定"""
        binding = KeyBinding(
            key="ctrl+s",
            action="save",
            description="Save file",
        )
        assert binding.description == "Save file"

    def test_binding_with_context(self):
        """测试带上下文的绑定"""
        binding = KeyBinding(
            key="ctrl+s",
            action="save",
            context="editor",
        )
        assert binding.context == "editor"

    def test_to_dict(self):
        """测试转换为字典"""
        binding = KeyBinding(key="ctrl+s", action="save")
        d = binding.to_dict()
        assert d["key"] == "ctrl+s"
        assert d["action"] == "save"


class TestKeyBindings:
    """测试快捷键绑定管理器"""

    def test_create_with_defaults(self):
        """测试创建带默认值"""
        kb = KeyBindings()
        assert kb.get_action("ctrl+s") == "save"

    def test_create_without_defaults(self):
        """测试创建不带默认值"""
        kb = KeyBindings(load_defaults=False)
        assert kb.get_action("ctrl+s") is None

    def test_bind(self):
        """测试绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        assert kb.get_action("ctrl+s") == "save"

    def test_bind_chain(self):
        """测试链式绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save").bind("ctrl+o", "open")
        assert kb.get_action("ctrl+s") == "save"
        assert kb.get_action("ctrl+o") == "open"

    def test_unbind(self):
        """测试解绑"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        assert kb.unbind("ctrl+s") is True
        assert kb.get_action("ctrl+s") is None

    def test_unbind_nonexistent(self):
        """测试解绑不存在的"""
        kb = KeyBindings(load_defaults=False)
        assert kb.unbind("ctrl+s") is False

    def test_get_binding(self):
        """测试获取绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save", description="Save file")
        binding = kb.get_binding("ctrl+s")
        assert binding is not None
        assert binding.action == "save"
        assert binding.description == "Save file"

    def test_get_key(self):
        """测试获取快捷键"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        assert kb.get_key("save") == "ctrl+s"

    def test_is_bound(self):
        """测试是否已绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        assert kb.is_bound("ctrl+s") is True
        assert kb.is_bound("ctrl+o") is False

    def test_enable_disable(self):
        """测试启用禁用"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")

        kb.disable("ctrl+s")
        assert kb.get_action("ctrl+s") is None

        kb.enable("ctrl+s")
        assert kb.get_action("ctrl+s") == "save"

    def test_on_callback(self):
        """测试回调"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")

        results = []
        kb.on("save", lambda: results.append("saved"))

        kb.trigger("ctrl+s")
        assert len(results) == 1
        assert results[0] == "saved"

    def test_trigger_disabled(self):
        """测试触发禁用的快捷键"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        kb.disable("ctrl+s")

        results = []
        kb.on("save", lambda: results.append("saved"))

        assert kb.trigger("ctrl+s") is False
        assert len(results) == 0

    def test_get_all_bindings(self):
        """测试获取所有绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        kb.bind("ctrl+o", "open")

        bindings = kb.get_all_bindings()
        assert len(bindings) == 2

    def test_get_bindings_by_context(self):
        """测试按上下文获取绑定"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save", context="editor")
        kb.bind("ctrl+c", "copy", context="editor")
        kb.bind("ctrl+l", "clear", context="terminal")

        editor_bindings = kb.get_bindings_by_context("editor")
        assert len(editor_bindings) == 2

    def test_to_dict(self):
        """测试导出为字典"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        kb.bind("ctrl+o", "open")

        d = kb.to_dict()
        assert d["ctrl+s"] == "save"
        assert d["ctrl+o"] == "open"

    def test_to_json(self):
        """测试导出为 JSON"""
        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")

        json_str = kb.to_json()
        data = json.loads(json_str)
        assert data["ctrl+s"] == "save"

    def test_load_from_dict(self):
        """测试从字典加载"""
        kb = KeyBindings(load_defaults=False)
        kb.load_from_dict({"ctrl+s": "save", "ctrl+o": "open"})

        assert kb.get_action("ctrl+s") == "save"
        assert kb.get_action("ctrl+o") == "open"

    def test_load_from_json(self):
        """测试从 JSON 加载"""
        kb = KeyBindings(load_defaults=False)
        kb.load_from_json('{"ctrl+s": "save"}')

        assert kb.get_action("ctrl+s") == "save"

    def test_load_from_file(self, tmp_path):
        """测试从文件加载"""
        file_path = tmp_path / "keybindings.json"
        file_path.write_text('{"ctrl+s": "save"}')

        kb = KeyBindings(load_defaults=False)
        assert kb.load_from_file(str(file_path)) is True
        assert kb.get_action("ctrl+s") == "save"

    def test_load_from_file_not_found(self):
        """测试加载不存在的文件"""
        kb = KeyBindings(load_defaults=False)
        assert kb.load_from_file("/nonexistent/file.json") is False

    def test_save_to_file(self, tmp_path):
        """测试保存到文件"""
        file_path = tmp_path / "keybindings.json"

        kb = KeyBindings(load_defaults=False)
        kb.bind("ctrl+s", "save")
        assert kb.save_to_file(str(file_path)) is True

        # 验证文件内容
        content = json.loads(file_path.read_text())
        assert content["ctrl+s"] == "save"

    def test_reset(self):
        """测试重置"""
        kb = KeyBindings()
        kb.bind("ctrl+q", "custom_action")

        kb.reset()
        assert kb.get_action("ctrl+q") is None
        assert kb.get_action("ctrl+s") == "save"  # 默认绑定恢复


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_keybindings(self):
        """测试获取全局实例"""
        kb = get_keybindings()
        assert kb is not None

    def test_bind_global(self):
        """测试全局绑定"""
        bind("ctrl+q", "quit")
        assert get_action("ctrl+q") == "quit"

    def test_unbind_global(self):
        """测试全局解绑"""
        bind("ctrl+q", "quit")
        unbind("ctrl+q")
        assert get_action("ctrl+q") is None

    def test_get_key_global(self):
        """测试全局获取快捷键"""
        assert get_key("save") == "ctrl+s"


class TestDefaultBindings:
    """测试默认绑定"""

    def test_default_bindings_exist(self):
        """测试默认绑定存在"""
        kb = KeyBindings()

        assert kb.get_action("ctrl+s") == "save"
        assert kb.get_action("ctrl+z") == "undo"
        assert kb.get_action("ctrl+c") == "copy"
        assert kb.get_action("ctrl+v") == "paste"
        assert kb.get_action("ctrl+shift+p") == "command_palette"

    def test_override_default(self):
        """测试覆盖默认"""
        kb = KeyBindings()
        kb.bind("ctrl+s", "custom_save")
        assert kb.get_action("ctrl+s") == "custom_save"


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, tmp_path):
        """测试完整工作流"""
        # 创建配置文件
        config_file = tmp_path / "keybindings.json"
        config_file.write_text(json.dumps({
            "ctrl+shift+s": "save_all",
            "ctrl+shift+n": "new_window",
        }))

        # 创建管理器并加载
        kb = KeyBindings()
        kb.load_from_file(str(config_file))

        # 验证默认和自定义都存在
        assert kb.get_action("ctrl+s") == "save"  # 默认
        assert kb.get_action("ctrl+shift+s") == "save_all"  # 自定义

        # 注册回调
        results = []
        kb.on("save_all", lambda: results.append("all saved"))

        # 触发
        kb.trigger("ctrl+shift+s")
        assert len(results) == 1

        # 保存修改
        kb.bind("ctrl+shift+q", "quit_all")
        kb.save_to_file(str(config_file))

        # 重新加载验证
        kb2 = KeyBindings(load_defaults=False)
        kb2.load_from_file(str(config_file))
        assert kb2.get_action("ctrl+shift+q") == "quit_all"
