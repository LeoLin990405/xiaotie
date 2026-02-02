"""
国际化 (i18n) 模块测试
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from xiaotie.i18n import (
    I18n,
    I18nConfig,
    BUILTIN_TRANSLATIONS,
    get_i18n,
    set_i18n,
    reset_i18n,
    set_language,
    get_language,
    t,
    translate,
    add_translations,
    available_languages,
)


@pytest.fixture(autouse=True)
def reset_global_i18n():
    """每个测试前重置全局 i18n"""
    reset_i18n()
    yield
    reset_i18n()


class TestI18nConfig:
    """测试 I18n 配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = I18nConfig()
        assert config.default_language == "en"
        assert config.fallback_language == "en"
        assert config.auto_detect is False

    def test_custom_config(self):
        """测试自定义配置"""
        config = I18nConfig(
            default_language="zh",
            fallback_language="en",
            auto_detect=True,
        )
        assert config.default_language == "zh"
        assert config.auto_detect is True


class TestI18n:
    """测试 I18n 类"""

    def test_create_i18n(self):
        """测试创建 I18n"""
        i18n = I18n()
        assert i18n.current_language == "en"

    def test_create_with_config(self):
        """测试使用配置创建"""
        config = I18nConfig(default_language="zh")
        i18n = I18n(config)
        assert i18n.current_language == "zh"

    def test_available_languages(self):
        """测试可用语言"""
        i18n = I18n()
        languages = i18n.available_languages
        assert "en" in languages
        assert "zh" in languages

    def test_set_language(self):
        """测试设置语言"""
        i18n = I18n()
        assert i18n.set_language("zh") is True
        assert i18n.current_language == "zh"

    def test_set_invalid_language(self):
        """测试设置无效语言"""
        i18n = I18n()
        assert i18n.set_language("invalid") is False
        assert i18n.current_language == "en"

    def test_translate_simple(self):
        """测试简单翻译"""
        i18n = I18n()
        assert i18n.translate("welcome") == "Welcome"

        i18n.set_language("zh")
        assert i18n.translate("welcome") == "欢迎"

    def test_translate_with_params(self):
        """测试带参数的翻译"""
        i18n = I18n()
        result = i18n.translate("hello", name="World")
        assert result == "Hello, World"

        i18n.set_language("zh")
        result = i18n.translate("hello", name="世界")
        assert result == "你好, 世界"

    def test_translate_missing_key(self):
        """测试缺失的键"""
        i18n = I18n()
        result = i18n.translate("nonexistent_key")
        assert result == "nonexistent_key"

    def test_translate_fallback(self):
        """测试回退语言"""
        i18n = I18n()
        # 添加一个只有英文的翻译
        i18n.add_translations("en", {"english_only": "English Only"})

        i18n.set_language("zh")
        result = i18n.translate("english_only")
        assert result == "English Only"

    def test_t_shortcut(self):
        """测试 t 快捷方式"""
        i18n = I18n()
        assert i18n.t("welcome") == "Welcome"
        assert i18n.t("hello", name="Test") == "Hello, Test"

    def test_has_translation(self):
        """测试检查翻译是否存在"""
        i18n = I18n()
        assert i18n.has_translation("welcome") is True
        assert i18n.has_translation("nonexistent") is False

    def test_get_all_keys(self):
        """测试获取所有键"""
        i18n = I18n()
        keys = i18n.get_all_keys()
        assert "welcome" in keys
        assert "hello" in keys

    def test_add_translations(self):
        """测试添加翻译"""
        i18n = I18n()
        i18n.add_translations("en", {"custom_key": "Custom Value"})
        assert i18n.translate("custom_key") == "Custom Value"

    def test_add_new_language(self):
        """测试添加新语言"""
        i18n = I18n()
        i18n.add_translations("ja", {"welcome": "ようこそ"})
        assert i18n.set_language("ja") is True
        assert i18n.translate("welcome") == "ようこそ"

    def test_on_language_change(self):
        """测试语言变更回调"""
        i18n = I18n()
        changes = []

        def callback(lang):
            changes.append(lang)

        i18n.on_language_change(callback)
        i18n.set_language("zh")

        assert len(changes) == 1
        assert changes[0] == "zh"

    def test_no_callback_on_same_language(self):
        """测试相同语言不触发回调"""
        i18n = I18n()
        changes = []

        def callback(lang):
            changes.append(lang)

        i18n.on_language_change(callback)
        i18n.set_language("en")  # 已经是 en

        assert len(changes) == 0

    def test_load_from_dir(self, tmp_path):
        """测试从目录加载翻译"""
        # 创建翻译文件
        translations = {"custom": "Custom from file"}
        (tmp_path / "en.json").write_text(json.dumps(translations))

        config = I18nConfig(translations_dir=str(tmp_path))
        i18n = I18n(config)

        assert i18n.translate("custom") == "Custom from file"

    def test_load_from_dir_merge(self, tmp_path):
        """测试从目录加载合并翻译"""
        # 创建翻译文件，覆盖内置翻译
        translations = {"welcome": "Custom Welcome"}
        (tmp_path / "en.json").write_text(json.dumps(translations))

        config = I18nConfig(translations_dir=str(tmp_path))
        i18n = I18n(config)

        assert i18n.translate("welcome") == "Custom Welcome"

    def test_singleton(self):
        """测试单例模式"""
        i18n1 = I18n.get_instance()
        i18n2 = I18n.get_instance()
        assert i18n1 is i18n2

    def test_reset_singleton(self):
        """测试重置单例"""
        i18n1 = I18n.get_instance()
        I18n.reset_instance()
        i18n2 = I18n.get_instance()
        assert i18n1 is not i18n2


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_i18n(self):
        """测试获取全局实例"""
        i18n = get_i18n()
        assert i18n is not None

    def test_set_language_global(self):
        """测试全局设置语言"""
        assert set_language("zh") is True
        assert get_language() == "zh"

    def test_t_global(self):
        """测试全局翻译"""
        assert t("welcome") == "Welcome"
        set_language("zh")
        assert t("welcome") == "欢迎"

    def test_translate_global(self):
        """测试全局翻译（别名）"""
        assert translate("hello", name="Test") == "Hello, Test"

    def test_add_translations_global(self):
        """测试全局添加翻译"""
        add_translations("en", {"global_key": "Global Value"})
        assert t("global_key") == "Global Value"

    def test_available_languages_global(self):
        """测试全局获取可用语言"""
        languages = available_languages()
        assert "en" in languages
        assert "zh" in languages


class TestBuiltinTranslations:
    """测试内置翻译"""

    def test_en_translations(self):
        """测试英文翻译"""
        i18n = I18n()
        i18n.set_language("en")

        assert i18n.t("yes") == "Yes"
        assert i18n.t("no") == "No"
        assert i18n.t("loading") == "Loading..."
        assert i18n.t("error") == "Error"

    def test_zh_translations(self):
        """测试中文翻译"""
        i18n = I18n()
        i18n.set_language("zh")

        assert i18n.t("yes") == "是"
        assert i18n.t("no") == "否"
        assert i18n.t("loading") == "加载中..."
        assert i18n.t("error") == "错误"

    def test_message_templates(self):
        """测试消息模板"""
        i18n = I18n()

        result = i18n.t("not_found", item="User")
        assert result == "User not found"

        result = i18n.t("items_found", count=5)
        assert result == "5 items found"

        i18n.set_language("zh")
        result = i18n.t("not_found", item="用户")
        assert result == "未找到 用户"


class TestAutoDetect:
    """测试自动检测语言"""

    @patch('locale.getdefaultlocale')
    def test_auto_detect_zh(self, mock_locale):
        """测试自动检测中文"""
        mock_locale.return_value = ('zh_CN', 'UTF-8')
        config = I18nConfig(auto_detect=True)
        i18n = I18n(config)
        assert i18n.current_language == "zh"

    @patch('locale.getdefaultlocale')
    def test_auto_detect_en(self, mock_locale):
        """测试自动检测英文"""
        mock_locale.return_value = ('en_US', 'UTF-8')
        config = I18nConfig(auto_detect=True)
        i18n = I18n(config)
        assert i18n.current_language == "en"

    @patch('locale.getdefaultlocale')
    def test_auto_detect_unknown(self, mock_locale):
        """测试自动检测未知语言"""
        mock_locale.return_value = ('fr_FR', 'UTF-8')
        config = I18nConfig(auto_detect=True, default_language="en")
        i18n = I18n(config)
        # 未知语言保持默认
        assert i18n.current_language == "en"


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, tmp_path):
        """测试完整工作流"""
        # 创建自定义翻译文件
        custom_en = {"app_name": "My App", "greeting": "Hello from {app}!"}
        custom_zh = {"app_name": "我的应用", "greeting": "来自 {app} 的问候！"}

        (tmp_path / "en.json").write_text(json.dumps(custom_en))
        (tmp_path / "zh.json").write_text(json.dumps(custom_zh))

        # 创建 I18n 实例
        config = I18nConfig(
            default_language="en",
            translations_dir=str(tmp_path),
        )
        i18n = I18n(config)

        # 英文
        assert i18n.t("app_name") == "My App"
        assert i18n.t("greeting", app="MyApp") == "Hello from MyApp!"

        # 切换到中文
        i18n.set_language("zh")
        assert i18n.t("app_name") == "我的应用"
        assert i18n.t("greeting", app="MyApp") == "来自 MyApp 的问候！"

        # 内置翻译仍然可用
        assert i18n.t("welcome") == "欢迎"

    def test_language_change_callback(self):
        """测试语言变更回调"""
        i18n = I18n()
        ui_updates = []

        def update_ui(lang):
            ui_updates.append(f"UI updated to {lang}")

        i18n.on_language_change(update_ui)

        i18n.set_language("zh")
        i18n.set_language("en")

        assert len(ui_updates) == 2
        assert "zh" in ui_updates[0]
        assert "en" in ui_updates[1]
