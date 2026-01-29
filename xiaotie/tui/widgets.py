"""自定义 Widgets

聊天消息、输入区域、状态栏等组件
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static, Input, Label, Button, Footer
from textual.widget import Widget
from textual.reactive import reactive
from textual.message import Message
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text


class ChatMessage(Static):
    """聊天消息组件"""

    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    ChatMessage.user {
        background: $primary-darken-2;
        border-left: thick $primary;
    }

    ChatMessage.assistant {
        background: $surface;
        border-left: thick $success;
    }

    ChatMessage.tool {
        background: $surface-darken-1;
        border-left: thick $warning;
    }

    ChatMessage.thinking {
        background: $surface-darken-2;
        border-left: thick $secondary;
        color: $text-muted;
    }

    ChatMessage .message-header {
        color: $text-muted;
        text-style: dim;
    }

    ChatMessage .message-content {
        margin-top: 1;
    }
    """

    def __init__(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.thinking = thinking
        self.tool_name = tool_name
        self.timestamp = timestamp or datetime.now()
        self.add_class(role)

    def compose(self) -> ComposeResult:
        # 角色图标
        role_icons = {
            "user": "👤",
            "assistant": "🤖",
            "tool": "🔧",
            "thinking": "💭",
            "system": "⚙️",
        }
        icon = role_icons.get(self.role, "❓")

        # 角色名称
        role_names = {
            "user": "你",
            "assistant": "小铁",
            "tool": self.tool_name or "工具",
            "thinking": "思考中",
            "system": "系统",
        }
        name = role_names.get(self.role, self.role)

        # 时间戳
        time_str = self.timestamp.strftime("%H:%M")

        # 头部
        header = f"{icon} {name}  {time_str}"
        yield Static(header, classes="message-header")

        # 内容
        if self.role == "assistant":
            # 渲染 Markdown
            yield Static(Markdown(self.content), classes="message-content")
        elif self.role == "tool":
            # 代码块样式
            yield Static(
                Panel(self.content[:500] + ("..." if len(self.content) > 500 else ""),
                      title=self.tool_name,
                      border_style="dim"),
                classes="message-content"
            )
        else:
            yield Static(self.content, classes="message-content")


class ThinkingIndicator(Static):
    """思考指示器"""

    DEFAULT_CSS = """
    ThinkingIndicator {
        width: 100%;
        height: 3;
        padding: 0 1;
        background: $surface-darken-2;
        border-left: thick $secondary;
    }
    """

    thinking_text = reactive("思考中...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dots = 0

    def on_mount(self) -> None:
        self.set_interval(0.5, self._animate)

    def _animate(self) -> None:
        self._dots = (self._dots + 1) % 4
        dots = "." * self._dots
        self.thinking_text = f"💭 思考中{dots}"

    def watch_thinking_text(self, text: str) -> None:
        self.update(text)


class InputArea(Widget):
    """输入区域组件"""

    DEFAULT_CSS = """
    InputArea {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 10;
        dock: bottom;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary-darken-1;
    }

    InputArea Input {
        width: 100%;
        border: none;
        background: transparent;
    }

    InputArea .input-hint {
        color: $text-muted;
        text-style: dim;
    }
    """

    class Submitted(Message):
        """输入提交消息"""
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("输入消息 (Enter 发送, Ctrl+C 取消)", classes="input-hint")
        yield Input(placeholder="输入你的问题...")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.post_message(self.Submitted(event.value))
            event.input.value = ""


class StatusBar(Static):
    """状态栏组件"""

    DEFAULT_CSS = """
    StatusBar {
        width: 100%;
        height: 1;
        dock: bottom;
        background: $primary-darken-3;
        color: $text;
        padding: 0 1;
    }

    StatusBar .status-item {
        margin-right: 2;
    }
    """

    model = reactive("claude-sonnet-4")
    tokens = reactive(0)
    session = reactive("新会话")
    parallel = reactive(True)

    def render(self) -> Text:
        text = Text()
        text.append("⚙️ ", style="bold")
        text.append(f"{self.model}", style="cyan")
        text.append(" │ ", style="dim")
        text.append(f"📊 {self.tokens:,} tokens", style="yellow")
        text.append(" │ ", style="dim")
        text.append(f"💾 {self.session}", style="green")
        text.append(" │ ", style="dim")
        parallel_status = "⚡并行" if self.parallel else "📝串行"
        text.append(parallel_status, style="magenta")
        return text


class SessionItem(Static):
    """会话列表项"""

    DEFAULT_CSS = """
    SessionItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        border-bottom: solid $surface-darken-1;
    }

    SessionItem:hover {
        background: $primary-darken-2;
    }

    SessionItem.selected {
        background: $primary-darken-1;
        border-left: thick $primary;
    }

    SessionItem .session-title {
        text-style: bold;
    }

    SessionItem .session-meta {
        color: $text-muted;
        text-style: dim;
    }
    """

    class Selected(Message):
        """会话选中消息"""
        def __init__(self, session_id: str) -> None:
            self.session_id = session_id
            super().__init__()

    def __init__(
        self,
        session_id: str,
        title: str,
        message_count: int,
        is_current: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.title = title
        self.message_count = message_count
        if is_current:
            self.add_class("selected")

    def compose(self) -> ComposeResult:
        yield Static(self.title[:20], classes="session-title")
        yield Static(f"{self.message_count} 条消息", classes="session-meta")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.session_id))


class FileChangeItem(Static):
    """文件变更项"""

    DEFAULT_CSS = """
    FileChangeItem {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    FileChangeItem.added {
        color: $success;
    }

    FileChangeItem.modified {
        color: $warning;
    }

    FileChangeItem.deleted {
        color: $error;
    }
    """

    def __init__(self, path: str, change_type: str, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.change_type = change_type
        self.add_class(change_type)

    def render(self) -> Text:
        icons = {"added": "+", "modified": "~", "deleted": "-"}
        icon = icons.get(self.change_type, "?")
        return Text(f"{icon} {self.path}")


class CommandPalette(Widget):
    """命令面板"""

    DEFAULT_CSS = """
    CommandPalette {
        width: 60;
        height: auto;
        max-height: 20;
        background: $surface;
        border: solid $primary;
        padding: 1;
        layer: overlay;
        align: center middle;
    }

    CommandPalette Input {
        width: 100%;
        margin-bottom: 1;
    }

    CommandPalette .command-list {
        width: 100%;
        height: auto;
        max-height: 15;
    }

    CommandPalette .command-item {
        width: 100%;
        padding: 0 1;
    }

    CommandPalette .command-item:hover {
        background: $primary-darken-2;
    }

    CommandPalette .command-name {
        text-style: bold;
    }

    CommandPalette .command-desc {
        color: $text-muted;
    }
    """

    class CommandSelected(Message):
        """命令选中消息"""
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    COMMANDS = [
        ("help", "显示帮助信息"),
        ("quit", "退出程序"),
        ("reset", "重置对话"),
        ("tools", "显示可用工具"),
        ("save", "保存当前会话"),
        ("sessions", "列出所有会话"),
        ("new", "创建新会话"),
        ("stream", "切换流式输出"),
        ("think", "切换深度思考"),
        ("parallel", "切换并行执行"),
        ("tokens", "显示 Token 使用"),
        ("tree", "显示目录结构"),
        ("map", "显示代码库概览"),
        ("find", "搜索相关文件"),
        ("plugins", "显示已加载插件"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filtered_commands = self.COMMANDS.copy()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="输入命令...")
        with ScrollableContainer(classes="command-list"):
            for name, desc in self.COMMANDS:
                with Horizontal(classes="command-item"):
                    yield Static(f"/{name}", classes="command-name")
                    yield Static(f" - {desc}", classes="command-desc")

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if query:
            self.filtered_commands = [
                (name, desc) for name, desc in self.COMMANDS
                if query in name.lower() or query in desc.lower()
            ]
        else:
            self.filtered_commands = self.COMMANDS.copy()
        self._refresh_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filtered_commands:
            self.post_message(self.CommandSelected(self.filtered_commands[0][0]))

    def _refresh_list(self) -> None:
        # 刷新命令列表
        pass
