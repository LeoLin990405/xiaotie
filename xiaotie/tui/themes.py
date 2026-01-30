"""主题系统

支持多种终端主题配色
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Theme:
    """主题配置"""

    name: str
    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    background: str
    surface: str
    text: str
    text_muted: str

    def to_css(self) -> str:
        """转换为 Textual CSS 变量"""
        return f"""
        $primary: {self.primary};
        $secondary: {self.secondary};
        $success: {self.success};
        $warning: {self.warning};
        $error: {self.error};
        $background: {self.background};
        $surface: {self.surface};
        $text: {self.text};
        $text-muted: {self.text_muted};
        """


# 预定义主题
THEMES: Dict[str, Theme] = {
    "default": Theme(
        name="默认",
        primary="#0ea5e9",
        secondary="#8b5cf6",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        background="#0f172a",
        surface="#1e293b",
        text="#f8fafc",
        text_muted="#94a3b8",
    ),
    "dracula": Theme(
        name="Dracula",
        primary="#bd93f9",
        secondary="#ff79c6",
        success="#50fa7b",
        warning="#ffb86c",
        error="#ff5555",
        background="#282a36",
        surface="#44475a",
        text="#f8f8f2",
        text_muted="#6272a4",
    ),
    "nord": Theme(
        name="Nord",
        primary="#88c0d0",
        secondary="#b48ead",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
        background="#2e3440",
        surface="#3b4252",
        text="#eceff4",
        text_muted="#4c566a",
    ),
    "monokai": Theme(
        name="Monokai",
        primary="#66d9ef",
        secondary="#ae81ff",
        success="#a6e22e",
        warning="#fd971f",
        error="#f92672",
        background="#272822",
        surface="#3e3d32",
        text="#f8f8f2",
        text_muted="#75715e",
    ),
    "solarized-dark": Theme(
        name="Solarized Dark",
        primary="#268bd2",
        secondary="#6c71c4",
        success="#859900",
        warning="#b58900",
        error="#dc322f",
        background="#002b36",
        surface="#073642",
        text="#839496",
        text_muted="#586e75",
    ),
    "gruvbox": Theme(
        name="Gruvbox",
        primary="#83a598",
        secondary="#d3869b",
        success="#b8bb26",
        warning="#fabd2f",
        error="#fb4934",
        background="#282828",
        surface="#3c3836",
        text="#ebdbb2",
        text_muted="#928374",
    ),
    "catppuccin": Theme(
        name="Catppuccin",
        primary="#89b4fa",
        secondary="#cba6f7",
        success="#a6e3a1",
        warning="#f9e2af",
        error="#f38ba8",
        background="#1e1e2e",
        surface="#313244",
        text="#cdd6f4",
        text_muted="#6c7086",
    ),
    "tokyo-night": Theme(
        name="Tokyo Night",
        primary="#7aa2f7",
        secondary="#bb9af7",
        success="#9ece6a",
        warning="#e0af68",
        error="#f7768e",
        background="#1a1b26",
        surface="#24283b",
        text="#c0caf5",
        text_muted="#565f89",
    ),
}


def get_theme(name: str) -> Theme:
    """获取主题"""
    return THEMES.get(name, THEMES["default"])


def list_themes() -> list[str]:
    """列出所有主题"""
    return list(THEMES.keys())
