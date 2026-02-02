"""小铁 TUI 模块

基于 Textual 构建的现代化终端界面
参考 OpenCode 设计
"""

from .app import XiaoTieApp
from .command_palette import (
    Command,
    CommandCategory,
    CommandPalette,
    QuickModelSelector,
    fuzzy_match,
    search_commands,
)
from .layout import BorderedContainer, Panel, SplitPane
from .widgets import (
    ChatMessage,
    Editor,
    MessageList,
    SessionList,
    StatusLine,
    ThinkingIndicator,
)

__all__ = [
    # App
    "XiaoTieApp",
    # Command Palette
    "CommandPalette",
    "QuickModelSelector",
    "Command",
    "CommandCategory",
    "fuzzy_match",
    "search_commands",
    # Widgets
    "ChatMessage",
    "MessageList",
    "Editor",
    "SessionList",
    "StatusLine",
    "ThinkingIndicator",
    # Layout
    "SplitPane",
    "BorderedContainer",
    "Panel",
]
