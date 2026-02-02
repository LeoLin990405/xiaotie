"""自定义 Widgets - OpenCode 风格

参考 OpenCode 设计：
- ChatMessage: 聊天消息
- MessageList: 消息列表
- Editor: 输入编辑器
- SessionList: 会话列表
- StatusLine: 状态行
- Toast: 消息提示
- ModelSelector: 模型选择器
- ThemeSelector: 主题选择器
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from .themes import get_theme, get_theme_display_name, list_themes


class ChatMessage(Static):
    """聊天消息组件 - OpenCode 风格"""

    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
    }

    ChatMessage.user {
        background: $primary 10%;
        border-left: thick $primary;
    }

    ChatMessage.assistant {
        background: $surface;
        border-left: thick $success;
    }

    ChatMessage.tool {
        background: $surface-darken-1;
        border-left: thick $warning;
        padding: 0 2;
    }

    ChatMessage.system {
        background: $surface-darken-2;
        border-left: thick $secondary;
        color: $text-muted;
    }

    ChatMessage.error {
        background: $error 10%;
        border-left: thick $error;
    }

    ChatMessage .msg-header {
        height: 1;
        margin-bottom: 1;
    }

    ChatMessage .msg-role {
        text-style: bold;
    }

    ChatMessage .msg-time {
        color: $text-muted;
        text-style: dim;
    }

    ChatMessage .msg-content {
        width: 100%;
    }

    ChatMessage .msg-thinking {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
        padding: 0 1;
        border-left: solid $secondary;
    }

    ChatMessage .msg-tool-name {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        is_error: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.thinking = thinking
        self.tool_name = tool_name
        self.timestamp = timestamp or datetime.now()
        self.is_error = is_error
        self.add_class(role)
        if is_error:
            self.add_class("error")

    def compose(self) -> ComposeResult:
        # 角色配置
        role_config = {
            "user": ("󰀄", "你", "cyan"),
            "assistant": ("󰚩", "小铁", "green"),
            "tool": ("󰒓", self.tool_name or "工具", "yellow"),
            "system": ("󰒔", "系统", "dim"),
        }
        icon, name, style = role_config.get(self.role, ("?", self.role, "white"))
        time_str = self.timestamp.strftime("%H:%M:%S")

        # 头部
        with Horizontal(classes="msg-header"):
            yield Static(f"{icon} {name}", classes="msg-role")
            yield Static(f"  {time_str}", classes="msg-time")

        # 工具名称
        if self.role == "tool" and self.tool_name:
            yield Static(f"󰒓 {self.tool_name}", classes="msg-tool-name")

        # 内容
        if self.role == "assistant":
            yield Static(Markdown(self.content), classes="msg-content")
        elif self.role == "tool":
            # 工具结果 - 截断显示
            preview = self.content[:500]
            if len(self.content) > 500:
                preview += f"\n... ({len(self.content)} 字符)"
            yield Static(preview, classes="msg-content")
        else:
            yield Static(self.content, classes="msg-content")

        # 思考过程
        if self.thinking:
            thinking_preview = self.thinking[:300]
            if len(self.thinking) > 300:
                thinking_preview += "..."
            yield Static(f"󰔚 {thinking_preview}", classes="msg-thinking")


class MessageList(ScrollableContainer):
    """消息列表 - 可滚动"""

    DEFAULT_CSS = """
    MessageList {
        width: 100%;
        height: 100%;
        padding: 0 1;
        background: $background;
    }

    MessageList .welcome {
        width: 100%;
        height: auto;
        padding: 3;
        margin: 2;
        background: $surface;
        border: round $primary 50%;
        text-align: center;
    }

    MessageList .welcome-logo {
        text-style: bold;
        color: $primary;
    }

    MessageList .welcome-title {
        text-style: bold;
        margin-top: 1;
        color: $text;
    }

    MessageList .welcome-hint {
        color: $text-muted;
        margin-top: 1;
    }

    MessageList .welcome-shortcuts {
        color: $text-muted;
        margin-top: 2;
        text-style: dim;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._has_messages = False

    def compose(self) -> ComposeResult:
        # 欢迎消息
        with Vertical(classes="welcome", id="welcome-msg"):
            yield Static(
                "  ▄███▄\n  █ ⚙ █\n  ▀███▀",
                classes="welcome-logo",
            )
            yield Static("欢迎使用小铁 XiaoTie", classes="welcome-title")
            yield Static(
                "AI 编程助手 · 智能代码分析 · 多模型支持",
                classes="welcome-hint",
            )
            yield Static(
                "Ctrl+K 命令面板 · Ctrl+B 侧边栏 · Ctrl+T 主题 · Ctrl+M 模型",
                classes="welcome-shortcuts",
            )

    def add_message(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
        is_error: bool = False,
    ) -> ChatMessage:
        """添加消息"""
        # 移除欢迎消息
        if not self._has_messages:
            welcome = self.query("#welcome-msg")
            for w in welcome:
                w.remove()
            self._has_messages = True

        # 添加消息
        msg = ChatMessage(
            role=role,
            content=content,
            thinking=thinking,
            tool_name=tool_name,
            is_error=is_error,
        )
        self.mount(msg)
        self.scroll_end(animate=False)
        return msg

    def clear_messages(self) -> None:
        """清空消息"""
        for child in list(self.children):
            child.remove()
        self._has_messages = False
        # 重新显示欢迎消息
        self._compose_welcome()

    def _compose_welcome(self) -> None:
        """组合欢迎消息"""
        welcome = Vertical(classes="welcome", id="welcome-msg")
        self.mount(welcome)
        welcome.mount(
            Static(
                "  ▄███▄\n  █ ⚙ █\n  ▀███▀",
                classes="welcome-logo",
            )
        )
        welcome.mount(Static("欢迎使用小铁 XiaoTie", classes="welcome-title"))
        welcome.mount(
            Static(
                "AI 编程助手 · 智能代码分析 · 多模型支持",
                classes="welcome-hint",
            )
        )
        welcome.mount(
            Static(
                "Ctrl+K 命令面板 · Ctrl+B 侧边栏 · Ctrl+T 主题 · Ctrl+M 模型",
                classes="welcome-shortcuts",
            )
        )


class Editor(Widget):
    """输入编辑器 - OpenCode 风格"""

    DEFAULT_CSS = """
    Editor {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 10;
        background: $surface;
        border-top: solid $border;
        padding: 0;
    }

    Editor .editor-hint {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: dim;
        background: $surface-darken-1;
    }

    Editor Input {
        width: 100%;
        height: auto;
        min-height: 2;
        border: none;
        background: transparent;
        padding: 0 1;
    }

    Editor Input:focus {
        border: none;
    }

    Editor .editor-status {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
    }

    Editor.processing {
        border-top: solid $warning;
    }

    Editor.processing Input {
        color: $text-muted;
    }
    """

    class Submitted(Message):
        """输入提交"""

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_processing = False

    def compose(self) -> ComposeResult:
        yield Static(
            "󰌌 输入消息 · Enter 发送 · / 命令 · Ctrl+K 面板",
            classes="editor-hint",
        )
        yield Input(
            placeholder="输入你的问题...",
            id="editor-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip() and not self._is_processing:
            self.post_message(self.Submitted(event.value))
            event.input.value = ""

    def set_processing(self, processing: bool) -> None:
        """设置处理状态"""
        self._is_processing = processing
        input_widget = self.query_one("#editor-input", Input)
        if processing:
            self.add_class("processing")
            input_widget.placeholder = "󰦖 处理中..."
            input_widget.disabled = True
        else:
            self.remove_class("processing")
            input_widget.placeholder = "输入你的问题..."
            input_widget.disabled = False

    def focus_input(self) -> None:
        """聚焦输入框"""
        self.query_one("#editor-input", Input).focus()


class SessionItem(Static):
    """会话列表项"""

    DEFAULT_CSS = """
    SessionItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        border-bottom: solid $border-subtle;
    }

    SessionItem:hover {
        background: $primary 20%;
    }

    SessionItem.current {
        background: $primary 30%;
        border-left: thick $primary;
    }

    SessionItem .session-title {
        text-style: bold;
        width: 100%;
        height: 1;
    }

    SessionItem .session-meta {
        color: $text-muted;
        text-style: dim;
        height: 1;
    }
    """

    class Selected(Message):
        def __init__(self, session_id: str) -> None:
            self.session_id = session_id
            super().__init__()

    def __init__(
        self,
        session_id: str,
        title: str,
        message_count: int = 0,
        is_current: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.title = title
        self.message_count = message_count
        if is_current:
            self.add_class("current")

    def compose(self) -> ComposeResult:
        yield Static(self.title[:25], classes="session-title")
        yield Static(f"󰍡 {self.message_count} 条消息", classes="session-meta")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.session_id))


class SessionList(ScrollableContainer):
    """会话列表侧边栏"""

    DEFAULT_CSS = """
    SessionList {
        width: 100%;
        height: 100%;
        background: $surface-darken-1;
    }

    SessionList .sidebar-header {
        width: 100%;
        height: 2;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $border;
    }

    SessionList .sidebar-title {
        text-style: bold;
        height: 1;
    }

    SessionList .sidebar-hint {
        color: $text-muted;
        text-style: dim;
        height: 1;
    }

    SessionList .session-list {
        width: 100%;
        height: auto;
    }

    SessionList .empty-hint {
        width: 100%;
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, sessions: List[dict] = None, **kwargs):
        super().__init__(**kwargs)
        self._sessions = sessions or []

    def compose(self) -> ComposeResult:
        with Vertical(classes="sidebar-header"):
            yield Static("󰆼 会话", classes="sidebar-title")
            yield Static("Ctrl+N 新建", classes="sidebar-hint")

        if self._sessions:
            with Vertical(classes="session-list"):
                for session in self._sessions:
                    yield SessionItem(
                        session_id=session.get("id", ""),
                        title=session.get("title", "未命名"),
                        message_count=session.get("message_count", 0),
                        is_current=session.get("is_current", False),
                    )
        else:
            yield Static("暂无会话", classes="empty-hint")

    def update_sessions(self, sessions: List[dict]) -> None:
        """更新会话列表"""
        self._sessions = sessions
        # 移除旧的会话项
        for item in self.query(SessionItem):
            item.remove()
        empty = self.query(".empty-hint")
        for e in empty:
            e.remove()

        # 查找或创建 session-list 容器
        session_list = self.query(".session-list")
        if session_list:
            container = session_list.first()
        else:
            container = Vertical(classes="session-list")
            self.mount(container)

        # 添加新的会话项
        if sessions:
            for session in sessions:
                container.mount(
                    SessionItem(
                        session_id=session.get("id", ""),
                        title=session.get("title", "未命名"),
                        message_count=session.get("message_count", 0),
                        is_current=session.get("is_current", False),
                    )
                )
        else:
            self.mount(Static("暂无会话", classes="empty-hint"))


class StatusLine(Static):
    """状态行 - OpenCode 风格"""

    DEFAULT_CSS = """
    StatusLine {
        width: 100%;
        height: 1;
        background: $primary 20%;
        padding: 0 1;
    }
    """

    model = reactive("claude-sonnet-4")
    tokens = reactive(0)
    session = reactive("新会话")
    status = reactive("就绪")
    parallel = reactive(True)
    thinking = reactive(True)
    theme_name = reactive("default")

    def render(self) -> Text:
        text = Text()

        # 模型
        text.append("󰚩 ", style="bold cyan")
        text.append(f"{self.model}", style="cyan")
        text.append(" │ ", style="dim")

        # Token
        text.append(f"󰊤 {self.tokens:,}", style="yellow")
        text.append(" │ ", style="dim")

        # 会话
        text.append(f"󰆼 {self.session[:15]}", style="green")
        text.append(" │ ", style="dim")

        # 状态
        if self.status == "就绪":
            text.append("● 就绪", style="green")
        elif self.status == "处理中...":
            text.append("󰦖 处理中", style="yellow")
        else:
            text.append(f"● {self.status}", style="yellow")
        text.append(" │ ", style="dim")

        # 模式
        modes = []
        if self.parallel:
            modes.append("󱐋 并行")
        if self.thinking:
            modes.append("󰔚 思考")
        text.append(" ".join(modes) if modes else "󰏫 串行", style="magenta")

        return text


class ThinkingIndicator(Static):
    """思考指示器"""

    DEFAULT_CSS = """
    ThinkingIndicator {
        width: 100%;
        height: 2;
        padding: 0 2;
        background: $surface-darken-1;
        border-left: thick $secondary;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dots = 0
        self._frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._frame_idx = 0

    def on_mount(self) -> None:
        self.set_interval(0.1, self._animate)

    def _animate(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        frame = self._frames[self._frame_idx]
        self.update(f"{frame} 思考中...")


class Toast(Static):
    """Toast 消息提示 - OpenCode 风格"""

    DEFAULT_CSS = """
    Toast {
        width: auto;
        max-width: 60;
        height: auto;
        padding: 1 2;
        margin: 1;
        background: $surface;
        border: solid $border;
        layer: notification;
    }

    Toast.success {
        border: solid $success;
        background: $success 10%;
    }

    Toast.error {
        border: solid $error;
        background: $error 10%;
    }

    Toast.warning {
        border: solid $warning;
        background: $warning 10%;
    }

    Toast.info {
        border: solid $info;
        background: $info 10%;
    }

    Toast .toast-title {
        text-style: bold;
        margin-bottom: 1;
    }

    Toast .toast-message {
        color: $text;
    }
    """

    def __init__(
        self,
        title: str,
        message: str,
        variant: str = "info",
        duration: float = 3.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.title = title
        self.message = message
        self.variant = variant
        self.duration = duration
        self.add_class(variant)

    def compose(self) -> ComposeResult:
        icons = {
            "success": "󰄬",
            "error": "󰅚",
            "warning": "󰀦",
            "info": "󰋽",
        }
        icon = icons.get(self.variant, "󰋽")
        yield Static(f"{icon} {self.title}", classes="toast-title")
        yield Static(self.message, classes="toast-message")

    def on_mount(self) -> None:
        if self.duration > 0:
            self.set_timer(self.duration, self.remove)


class SelectorItem(Static):
    """选择器列表项"""

    DEFAULT_CSS = """
    SelectorItem {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    SelectorItem:hover {
        background: $primary 30%;
    }

    SelectorItem.selected {
        background: $primary 40%;
    }
    """

    class Selected(Message):
        def __init__(self, value: str, display: str) -> None:
            self.value = value
            self.display = display
            super().__init__()

    def __init__(self, value: str, display: str, is_selected: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.value = value
        self.display = display
        if is_selected:
            self.add_class("selected")

    def compose(self) -> ComposeResult:
        yield Static(self.display)

    def on_click(self) -> None:
        self.post_message(self.Selected(self.value, self.display))


class ThemeSelectorItem(Static):
    """主题选择器项"""

    DEFAULT_CSS = """
    ThemeSelectorItem {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    ThemeSelectorItem:hover {
        background: $primary 30%;
    }

    ThemeSelectorItem.selected {
        background: $primary 40%;
    }

    ThemeSelectorItem .theme-row {
        width: 100%;
        height: 1;
    }

    ThemeSelectorItem .theme-name {
        width: 1fr;
    }

    ThemeSelectorItem .theme-swatch {
        width: 2;
        height: 1;
        margin-left: 1;
        border: solid $border;
    }
    """

    class Selected(Message):
        def __init__(self, value: str, display: str) -> None:
            self.value = value
            self.display = display
            super().__init__()

    def __init__(
        self,
        value: str,
        display: str,
        colors: list[str],
        is_selected: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.value = value
        self.display = display
        self.colors = colors
        if is_selected:
            self.add_class("selected")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="theme-row"):
            yield Static(self.display, classes="theme-name")
            for color in self.colors:
                swatch = Static("  ", classes="theme-swatch")
                swatch.styles.background = color
                yield swatch

    def on_click(self) -> None:
        self.post_message(self.Selected(self.value, self.display))


class ModelSelector(ScrollableContainer):
    """模型选择器"""

    DEFAULT_CSS = """
    ModelSelector {
        width: 50;
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $border;
        padding: 1;
    }

    ModelSelector .selector-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    """

    MODELS = [
        ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
        ("claude-opus-4-20250514", "Claude Opus 4"),
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
        ("gpt-4o", "GPT-4o"),
        ("gpt-4o-mini", "GPT-4o Mini"),
        ("GLM-4.7", "GLM-4.7"),
        ("deepseek-chat", "DeepSeek Chat"),
        ("deepseek-coder", "DeepSeek Coder"),
    ]

    def __init__(self, current_model: str = "", **kwargs):
        super().__init__(**kwargs)
        self.current_model = current_model

    def compose(self) -> ComposeResult:
        yield Static("󰚩 选择模型", classes="selector-title")
        for value, display in self.MODELS:
            is_selected = value == self.current_model
            yield SelectorItem(value, display, is_selected)


class ThemeSelector(ScrollableContainer):
    """主题选择器"""

    DEFAULT_CSS = """
    ThemeSelector {
        width: 40;
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $border;
        padding: 1;
    }

    ThemeSelector .selector-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    """

    def __init__(self, current_theme: str = "default", **kwargs):
        super().__init__(**kwargs)
        self.current_theme = current_theme

    def compose(self) -> ComposeResult:
        yield Static("󰏘 选择主题", classes="selector-title")
        for theme_id in list_themes():
            theme = get_theme(theme_id)
            display = get_theme_display_name(theme_id)
            is_selected = theme_id == self.current_theme
            colors = [theme.primary, theme.secondary, theme.accent]
            yield ThemeSelectorItem(theme_id, display, colors, is_selected)


class CommandPaletteItem(Static):
    """命令面板项"""

    DEFAULT_CSS = """
    CommandPaletteItem {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    CommandPaletteItem:hover {
        background: $primary 30%;
    }

    CommandPaletteItem.selected {
        background: $primary 40%;
    }
    """

    def __init__(
        self,
        name: str,
        description: str,
        shortcut: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cmd_name = name
        self.description = description
        self.shortcut = shortcut

    def render(self) -> Text:
        text = Text()
        text.append(f"/{self.cmd_name}", style="bold cyan")
        text.append(f"  {self.description}", style="dim")
        if self.shortcut:
            text.append(f"  [{self.shortcut}]", style="yellow dim")
        return text
