"""小铁 TUI 模块

基于 Textual 构建的现代化终端界面
参考 OpenCode 设计
"""

from .app import XiaoTieApp
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
    "XiaoTieApp",
    "ChatMessage",
    "MessageList",
    "Editor",
    "SessionList",
    "StatusLine",
    "ThinkingIndicator",
    "SplitPane",
    "BorderedContainer",
    "Panel",
]
