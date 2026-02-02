"""
国际化 (i18n) 模块

提供多语言支持，包括：
- 消息翻译
- 语言切换
- 动态加载翻译文件

使用示例:
    from xiaotie.i18n import I18n, set_language, t

    # 设置语言
    set_language("zh")

    # 翻译
    print(t("welcome"))  # 欢迎
    print(t("hello", name="World"))  # 你好, World
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
import json
import os
from pathlib import Path
import threading


# 内置翻译
BUILTIN_TRANSLATIONS = {
    "en": {
        # 通用
        "welcome": "Welcome",
        "hello": "Hello, {name}",
        "goodbye": "Goodbye",
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "error": "Error",
        "warning": "Warning",
        "info": "Info",
        "success": "Success",

        # 状态
        "loading": "Loading...",
        "processing": "Processing...",
        "completed": "Completed",
        "failed": "Failed",
        "pending": "Pending",
        "running": "Running",
        "stopped": "Stopped",

        # 操作
        "save": "Save",
        "load": "Load",
        "delete": "Delete",
        "edit": "Edit",
        "create": "Create",
        "update": "Update",
        "search": "Search",
        "filter": "Filter",
        "sort": "Sort",
        "refresh": "Refresh",
        "retry": "Retry",
        "submit": "Submit",
        "reset": "Reset",

        # 消息
        "not_found": "{item} not found",
        "already_exists": "{item} already exists",
        "invalid_input": "Invalid input: {reason}",
        "operation_failed": "Operation failed: {reason}",
        "operation_success": "Operation completed successfully",
        "confirm_delete": "Are you sure you want to delete {item}?",
        "no_results": "No results found",
        "items_found": "{count} items found",

        # Agent 相关
        "agent_started": "Agent started",
        "agent_stopped": "Agent stopped",
        "thinking": "Thinking...",
        "generating": "Generating response...",
        "tool_calling": "Calling tool: {tool}",
        "tool_result": "Tool result received",

        # 错误
        "connection_error": "Connection error: {reason}",
        "timeout_error": "Request timed out",
        "auth_error": "Authentication failed",
        "permission_denied": "Permission denied",
        "rate_limit": "Rate limit exceeded, please try again later",
    },
    "zh": {
        # 通用
        "welcome": "欢迎",
        "hello": "你好, {name}",
        "goodbye": "再见",
        "yes": "是",
        "no": "否",
        "ok": "确定",
        "cancel": "取消",
        "confirm": "确认",
        "error": "错误",
        "warning": "警告",
        "info": "信息",
        "success": "成功",

        # 状态
        "loading": "加载中...",
        "processing": "处理中...",
        "completed": "已完成",
        "failed": "失败",
        "pending": "等待中",
        "running": "运行中",
        "stopped": "已停止",

        # 操作
        "save": "保存",
        "load": "加载",
        "delete": "删除",
        "edit": "编辑",
        "create": "创建",
        "update": "更新",
        "search": "搜索",
        "filter": "筛选",
        "sort": "排序",
        "refresh": "刷新",
        "retry": "重试",
        "submit": "提交",
        "reset": "重置",

        # 消息
        "not_found": "未找到 {item}",
        "already_exists": "{item} 已存在",
        "invalid_input": "无效输入: {reason}",
        "operation_failed": "操作失败: {reason}",
        "operation_success": "操作成功",
        "confirm_delete": "确定要删除 {item} 吗？",
        "no_results": "未找到结果",
        "items_found": "找到 {count} 个项目",

        # Agent 相关
        "agent_started": "Agent 已启动",
        "agent_stopped": "Agent 已停止",
        "thinking": "思考中...",
        "generating": "生成响应中...",
        "tool_calling": "调用工具: {tool}",
        "tool_result": "工具结果已返回",

        # 错误
        "connection_error": "连接错误: {reason}",
        "timeout_error": "请求超时",
        "auth_error": "认证失败",
        "permission_denied": "权限不足",
        "rate_limit": "请求过于频繁，请稍后重试",
    },
}


@dataclass
class I18nConfig:
    """国际化配置"""
    default_language: str = "en"
    fallback_language: str = "en"
    translations_dir: Optional[str] = None
    auto_detect: bool = False


class TranslationNotFoundError(Exception):
    """翻译未找到错误"""
    pass


class I18n:
    """国际化管理器"""

    _instance: Optional["I18n"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[I18nConfig] = None):
        self.config = config or I18nConfig()
        self._current_language = self.config.default_language
        self._translations: Dict[str, Dict[str, str]] = {}
        self._callbacks: List[Callable[[str], None]] = []

        # 加载内置翻译
        self._load_builtin_translations()

        # 加载外部翻译
        if self.config.translations_dir:
            self._load_translations_from_dir(self.config.translations_dir)

        # 自动检测语言
        if self.config.auto_detect:
            self._auto_detect_language()

    @classmethod
    def get_instance(cls) -> "I18n":
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例"""
        with cls._lock:
            cls._instance = None

    def _load_builtin_translations(self):
        """加载内置翻译"""
        for lang, translations in BUILTIN_TRANSLATIONS.items():
            self._translations[lang] = translations.copy()

    def _load_translations_from_dir(self, dir_path: str):
        """从目录加载翻译文件"""
        path = Path(dir_path)
        if not path.exists():
            return

        for file_path in path.glob("*.json"):
            lang = file_path.stem
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    if lang in self._translations:
                        self._translations[lang].update(translations)
                    else:
                        self._translations[lang] = translations
            except (json.JSONDecodeError, IOError):
                pass

    def _auto_detect_language(self):
        """自动检测系统语言"""
        import locale
        try:
            lang, _ = locale.getdefaultlocale()
            if lang:
                lang_code = lang.split('_')[0].lower()
                if lang_code in self._translations:
                    self._current_language = lang_code
        except Exception:
            pass

    @property
    def current_language(self) -> str:
        """获取当前语言"""
        return self._current_language

    @property
    def available_languages(self) -> List[str]:
        """获取可用语言列表"""
        return list(self._translations.keys())

    def set_language(self, language: str) -> bool:
        """设置当前语言"""
        if language in self._translations:
            old_language = self._current_language
            self._current_language = language
            if old_language != language:
                self._notify_callbacks(language)
            return True
        return False

    def on_language_change(self, callback: Callable[[str], None]) -> "I18n":
        """注册语言变更回调"""
        self._callbacks.append(callback)
        return self

    def _notify_callbacks(self, language: str):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(language)
            except Exception:
                pass

    def add_translations(self, language: str, translations: Dict[str, str]):
        """添加翻译"""
        if language in self._translations:
            self._translations[language].update(translations)
        else:
            self._translations[language] = translations.copy()

    def get_translation(self, key: str, language: Optional[str] = None) -> Optional[str]:
        """获取翻译（不带格式化）"""
        lang = language or self._current_language

        # 尝试当前语言
        if lang in self._translations:
            if key in self._translations[lang]:
                return self._translations[lang][key]

        # 尝试回退语言
        fallback = self.config.fallback_language
        if fallback != lang and fallback in self._translations:
            if key in self._translations[fallback]:
                return self._translations[fallback][key]

        return None

    def translate(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """翻译并格式化"""
        translation = self.get_translation(key, language)

        if translation is None:
            # 返回 key 本身作为后备
            return key

        # 格式化
        if kwargs:
            try:
                return translation.format(**kwargs)
            except KeyError:
                return translation

        return translation

    def t(self, key: str, **kwargs) -> str:
        """翻译的快捷方式"""
        return self.translate(key, **kwargs)

    def has_translation(self, key: str, language: Optional[str] = None) -> bool:
        """检查是否有翻译"""
        return self.get_translation(key, language) is not None

    def get_all_keys(self, language: Optional[str] = None) -> List[str]:
        """获取所有翻译键"""
        lang = language or self._current_language
        if lang in self._translations:
            return list(self._translations[lang].keys())
        return []


# 全局实例和快捷函数
_i18n: Optional[I18n] = None


def get_i18n() -> I18n:
    """获取全局 I18n 实例"""
    global _i18n
    if _i18n is None:
        _i18n = I18n.get_instance()
    return _i18n


def set_i18n(i18n: I18n):
    """设置全局 I18n 实例"""
    global _i18n
    _i18n = i18n


def reset_i18n():
    """重置全局 I18n 实例"""
    global _i18n
    _i18n = None
    I18n.reset_instance()


def set_language(language: str) -> bool:
    """设置当前语言"""
    return get_i18n().set_language(language)


def get_language() -> str:
    """获取当前语言"""
    return get_i18n().current_language


def t(key: str, **kwargs) -> str:
    """翻译"""
    return get_i18n().translate(key, **kwargs)


def translate(key: str, **kwargs) -> str:
    """翻译（别名）"""
    return t(key, **kwargs)


def add_translations(language: str, translations: Dict[str, str]):
    """添加翻译"""
    get_i18n().add_translations(language, translations)


def available_languages() -> List[str]:
    """获取可用语言列表"""
    return get_i18n().available_languages
