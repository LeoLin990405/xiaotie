"""主题系统 - OpenCode 风格

支持多种终端主题配色，参考 OpenCode 设计。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class Theme:
    """主题配置 - OpenCode 风格"""

    name: str
    # 基础颜色
    primary: str
    secondary: str
    accent: str = ""
    success: str = ""
    warning: str = ""
    error: str = ""
    info: str = ""
    # 背景颜色
    background: str = ""
    background_panel: str = ""
    background_element: str = ""
    surface: str = ""
    # 文本颜色
    text: str = ""
    text_muted: str = ""
    # 边框颜色
    border: str = ""
    border_active: str = ""
    border_subtle: str = ""
    # Diff 颜色
    diff_added: str = ""
    diff_removed: str = ""
    diff_context: str = ""
    # Markdown 颜色
    markdown_heading: str = ""
    markdown_link: str = ""
    markdown_code: str = ""
    markdown_quote: str = ""
    # 语法高亮
    syntax_keyword: str = ""
    syntax_function: str = ""
    syntax_string: str = ""
    syntax_number: str = ""
    syntax_comment: str = ""

    def __post_init__(self):
        """设置默认值"""
        if not self.accent:
            self.accent = self.primary
        if not self.success:
            self.success = "#22c55e"
        if not self.warning:
            self.warning = "#f59e0b"
        if not self.error:
            self.error = "#ef4444"
        if not self.info:
            self.info = self.primary
        if not self.background:
            self.background = "#0f172a"
        if not self.background_panel:
            self.background_panel = "#1e293b"
        if not self.background_element:
            self.background_element = "#1e293b"
        if not self.surface:
            self.surface = "#1e293b"
        if not self.text:
            self.text = "#f8fafc"
        if not self.text_muted:
            self.text_muted = "#94a3b8"
        if not self.border:
            self.border = "#334155"
        if not self.border_active:
            self.border_active = self.primary
        if not self.border_subtle:
            self.border_subtle = "#1e293b"
        if not self.diff_added:
            self.diff_added = self.success
        if not self.diff_removed:
            self.diff_removed = self.error
        if not self.diff_context:
            self.diff_context = self.text_muted
        if not self.markdown_heading:
            self.markdown_heading = self.primary
        if not self.markdown_link:
            self.markdown_link = self.secondary
        if not self.markdown_code:
            self.markdown_code = self.success
        if not self.markdown_quote:
            self.markdown_quote = self.text_muted
        if not self.syntax_keyword:
            self.syntax_keyword = self.secondary
        if not self.syntax_function:
            self.syntax_function = self.primary
        if not self.syntax_string:
            self.syntax_string = self.success
        if not self.syntax_number:
            self.syntax_number = self.warning
        if not self.syntax_comment:
            self.syntax_comment = self.text_muted

    def to_css_vars(self) -> str:
        """转换为 Textual CSS 变量"""
        return f"""
        $primary: {self.primary};
        $secondary: {self.secondary};
        $accent: {self.accent};
        $success: {self.success};
        $warning: {self.warning};
        $error: {self.error};
        $info: {self.info};
        $background: {self.background};
        $background-panel: {self.background_panel};
        $background-element: {self.background_element};
        $surface: {self.surface};
        $text: {self.text};
        $text-muted: {self.text_muted};
        $border: {self.border};
        $border-active: {self.border_active};
        $border-subtle: {self.border_subtle};
        """


# 预定义主题 - OpenCode 风格
THEMES: Dict[str, Theme] = {
    "default": Theme(
        name="默认",
        primary="#0ea5e9",
        secondary="#8b5cf6",
        accent="#06b6d4",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        info="#0ea5e9",
        background="#0f172a",
        background_panel="#1e293b",
        background_element="#334155",
        surface="#1e293b",
        text="#f8fafc",
        text_muted="#94a3b8",
        border="#334155",
        border_active="#0ea5e9",
        border_subtle="#1e293b",
    ),
    "nord": Theme(
        name="Nord",
        primary="#88c0d0",
        secondary="#b48ead",
        accent="#8fbcbb",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
        info="#88c0d0",
        background="#2e3440",
        background_panel="#3b4252",
        background_element="#434c5e",
        surface="#3b4252",
        text="#eceff4",
        text_muted="#4c566a",
        border="#434c5e",
        border_active="#88c0d0",
        border_subtle="#3b4252",
        diff_added="#a3be8c",
        diff_removed="#bf616a",
        markdown_heading="#88c0d0",
        markdown_link="#81a1c1",
        markdown_code="#a3be8c",
        syntax_keyword="#81a1c1",
        syntax_function="#88c0d0",
        syntax_string="#a3be8c",
        syntax_number="#b48ead",
        syntax_comment="#4c566a",
    ),
    "dracula": Theme(
        name="Dracula",
        primary="#bd93f9",
        secondary="#ff79c6",
        accent="#8be9fd",
        success="#50fa7b",
        warning="#ffb86c",
        error="#ff5555",
        info="#8be9fd",
        background="#282a36",
        background_panel="#44475a",
        background_element="#6272a4",
        surface="#44475a",
        text="#f8f8f2",
        text_muted="#6272a4",
        border="#44475a",
        border_active="#bd93f9",
        border_subtle="#282a36",
        diff_added="#50fa7b",
        diff_removed="#ff5555",
        markdown_heading="#bd93f9",
        markdown_link="#8be9fd",
        markdown_code="#50fa7b",
        syntax_keyword="#ff79c6",
        syntax_function="#50fa7b",
        syntax_string="#f1fa8c",
        syntax_number="#bd93f9",
        syntax_comment="#6272a4",
    ),
    "monokai": Theme(
        name="Monokai",
        primary="#66d9ef",
        secondary="#ae81ff",
        accent="#a6e22e",
        success="#a6e22e",
        warning="#fd971f",
        error="#f92672",
        info="#66d9ef",
        background="#272822",
        background_panel="#3e3d32",
        background_element="#49483e",
        surface="#3e3d32",
        text="#f8f8f2",
        text_muted="#75715e",
        border="#49483e",
        border_active="#66d9ef",
        border_subtle="#3e3d32",
        diff_added="#a6e22e",
        diff_removed="#f92672",
        markdown_heading="#66d9ef",
        markdown_link="#ae81ff",
        markdown_code="#a6e22e",
        syntax_keyword="#f92672",
        syntax_function="#a6e22e",
        syntax_string="#e6db74",
        syntax_number="#ae81ff",
        syntax_comment="#75715e",
    ),
    "solarized-dark": Theme(
        name="Solarized Dark",
        primary="#268bd2",
        secondary="#6c71c4",
        accent="#2aa198",
        success="#859900",
        warning="#b58900",
        error="#dc322f",
        info="#268bd2",
        background="#002b36",
        background_panel="#073642",
        background_element="#586e75",
        surface="#073642",
        text="#839496",
        text_muted="#586e75",
        border="#073642",
        border_active="#268bd2",
        border_subtle="#002b36",
    ),
    "gruvbox": Theme(
        name="Gruvbox",
        primary="#83a598",
        secondary="#d3869b",
        accent="#8ec07c",
        success="#b8bb26",
        warning="#fabd2f",
        error="#fb4934",
        info="#83a598",
        background="#282828",
        background_panel="#3c3836",
        background_element="#504945",
        surface="#3c3836",
        text="#ebdbb2",
        text_muted="#928374",
        border="#504945",
        border_active="#83a598",
        border_subtle="#3c3836",
        diff_added="#b8bb26",
        diff_removed="#fb4934",
        markdown_heading="#83a598",
        markdown_link="#d3869b",
        markdown_code="#b8bb26",
        syntax_keyword="#fb4934",
        syntax_function="#b8bb26",
        syntax_string="#b8bb26",
        syntax_number="#d3869b",
        syntax_comment="#928374",
    ),
    "catppuccin": Theme(
        name="Catppuccin Mocha",
        primary="#89b4fa",
        secondary="#cba6f7",
        accent="#94e2d5",
        success="#a6e3a1",
        warning="#f9e2af",
        error="#f38ba8",
        info="#89dceb",
        background="#1e1e2e",
        background_panel="#313244",
        background_element="#45475a",
        surface="#313244",
        text="#cdd6f4",
        text_muted="#6c7086",
        border="#45475a",
        border_active="#89b4fa",
        border_subtle="#313244",
        diff_added="#a6e3a1",
        diff_removed="#f38ba8",
        markdown_heading="#89b4fa",
        markdown_link="#f5c2e7",
        markdown_code="#a6e3a1",
        syntax_keyword="#cba6f7",
        syntax_function="#89b4fa",
        syntax_string="#a6e3a1",
        syntax_number="#fab387",
        syntax_comment="#6c7086",
    ),
    "tokyo-night": Theme(
        name="Tokyo Night",
        primary="#7aa2f7",
        secondary="#bb9af7",
        accent="#7dcfff",
        success="#9ece6a",
        warning="#e0af68",
        error="#f7768e",
        info="#7dcfff",
        background="#1a1b26",
        background_panel="#24283b",
        background_element="#414868",
        surface="#24283b",
        text="#c0caf5",
        text_muted="#565f89",
        border="#414868",
        border_active="#7aa2f7",
        border_subtle="#24283b",
        diff_added="#9ece6a",
        diff_removed="#f7768e",
        markdown_heading="#7aa2f7",
        markdown_link="#bb9af7",
        markdown_code="#9ece6a",
        syntax_keyword="#bb9af7",
        syntax_function="#7aa2f7",
        syntax_string="#9ece6a",
        syntax_number="#ff9e64",
        syntax_comment="#565f89",
    ),
    "one-dark": Theme(
        name="One Dark",
        primary="#61afef",
        secondary="#c678dd",
        accent="#56b6c2",
        success="#98c379",
        warning="#e5c07b",
        error="#e06c75",
        info="#61afef",
        background="#282c34",
        background_panel="#21252b",
        background_element="#3e4451",
        surface="#21252b",
        text="#abb2bf",
        text_muted="#5c6370",
        border="#3e4451",
        border_active="#61afef",
        border_subtle="#21252b",
        diff_added="#98c379",
        diff_removed="#e06c75",
        markdown_heading="#61afef",
        markdown_link="#c678dd",
        markdown_code="#98c379",
        syntax_keyword="#c678dd",
        syntax_function="#61afef",
        syntax_string="#98c379",
        syntax_number="#d19a66",
        syntax_comment="#5c6370",
    ),
    "github-dark": Theme(
        name="GitHub Dark",
        primary="#58a6ff",
        secondary="#bc8cff",
        accent="#39d353",
        success="#3fb950",
        warning="#d29922",
        error="#f85149",
        info="#58a6ff",
        background="#0d1117",
        background_panel="#161b22",
        background_element="#21262d",
        surface="#161b22",
        text="#c9d1d9",
        text_muted="#8b949e",
        border="#30363d",
        border_active="#58a6ff",
        border_subtle="#21262d",
        diff_added="#3fb950",
        diff_removed="#f85149",
        markdown_heading="#58a6ff",
        markdown_link="#bc8cff",
        markdown_code="#3fb950",
        syntax_keyword="#ff7b72",
        syntax_function="#d2a8ff",
        syntax_string="#a5d6ff",
        syntax_number="#79c0ff",
        syntax_comment="#8b949e",
    ),
}


class ThemeManager:
    """主题管理器 - 单例模式"""

    _instance = None
    _current_theme: str = "default"
    _callbacks: list[Callable[[str], None]] = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_current_theme(self) -> str:
        return self._current_theme

    def set_theme(self, name: str) -> bool:
        """设置主题并通知所有监听器"""
        if name not in THEMES:
            return False
        self._current_theme = name
        for callback in self._callbacks:
            callback(name)
        return True

    def subscribe(self, callback: Callable[[str], None]):
        """订阅主题变更事件"""
        self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[str], None]):
        """取消订阅"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)


def get_theme(name: str) -> Theme:
    """获取主题"""
    return THEMES.get(name, THEMES["default"])


def list_themes() -> list[str]:
    """列出所有主题"""
    return list(THEMES.keys())


def get_theme_display_name(name: str) -> str:
    """获取主题显示名称"""
    theme = THEMES.get(name)
    return theme.name if theme else name
