"""小铁 TUI 主应用

基于 Textual 的现代化终端界面
参考 OpenCode 设计
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Label, Button
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .widgets import (
    ChatMessage,
    ThinkingIndicator,
    InputArea,
    StatusBar,
    SessionItem,
    CommandPalette,
)


class HelpScreen(ModalScreen):
    """帮助屏幕"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("q", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    HelpScreen .help-title {
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    HelpScreen .help-section {
        margin-top: 1;
        text-style: bold;
        color: $primary;
    }

    HelpScreen .help-item {
        margin-left: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⚙️ 小铁帮助", classes="help-title")

            yield Static("快捷键", classes="help-section")
            yield Static("Ctrl+P  命令面板", classes="help-item")
            yield Static("Ctrl+N  新会话", classes="help-item")
            yield Static("Ctrl+S  保存会话", classes="help-item")
            yield Static("Ctrl+L  清屏", classes="help-item")
            yield Static("Ctrl+C  取消/退出", classes="help-item")
            yield Static("F1      帮助", classes="help-item")

            yield Static("命令", classes="help-section")
            yield Static("/help     显示帮助", classes="help-item")
            yield Static("/quit     退出程序", classes="help-item")
            yield Static("/reset    重置对话", classes="help-item")
            yield Static("/tools    显示工具", classes="help-item")
            yield Static("/save     保存会话", classes="help-item")
            yield Static("/sessions 会话列表", classes="help-item")
            yield Static("/new      新建会话", classes="help-item")
            yield Static("/parallel 切换并行", classes="help-item")
            yield Static("/plugins  插件列表", classes="help-item")

            yield Static("按 ESC 或 Q 关闭", classes="help-item")


class CommandPaletteScreen(ModalScreen):
    """命令面板屏幕"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center middle;
    }

    CommandPaletteScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    CommandPaletteScreen .palette-title {
        text-style: bold;
        margin-bottom: 1;
    }

    CommandPaletteScreen Input {
        width: 100%;
        margin-bottom: 1;
    }

    CommandPaletteScreen .command-list {
        height: auto;
        max-height: 20;
    }

    CommandPaletteScreen .command-item {
        width: 100%;
        padding: 0 1;
    }

    CommandPaletteScreen .command-item:hover {
        background: $primary-darken-2;
    }

    CommandPaletteScreen .command-item.selected {
        background: $primary-darken-1;
    }
    """

    COMMANDS = [
        ("help", "显示帮助信息", "F1"),
        ("quit", "退出程序", "Ctrl+Q"),
        ("reset", "重置对话", ""),
        ("tools", "显示可用工具", ""),
        ("save", "保存当前会话", "Ctrl+S"),
        ("sessions", "列出所有会话", ""),
        ("new", "创建新会话", "Ctrl+N"),
        ("stream", "切换流式输出", ""),
        ("think", "切换深度思考", ""),
        ("parallel", "切换并行执行", ""),
        ("tokens", "显示 Token 使用", ""),
        ("tree", "显示目录结构", ""),
        ("map", "显示代码库概览", ""),
        ("find", "搜索相关文件", ""),
        ("plugins", "显示已加载插件", ""),
        ("plugin-new", "创建插件模板", ""),
    ]

    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.filtered_commands = self.COMMANDS.copy()
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⌘ 命令面板", classes="palette-title")
            yield Input(placeholder="输入命令...", id="command-input")
            with ScrollableContainer(classes="command-list"):
                for i, (name, desc, shortcut) in enumerate(self.COMMANDS):
                    classes = "command-item selected" if i == 0 else "command-item"
                    shortcut_text = f"  [{shortcut}]" if shortcut else ""
                    yield Static(
                        f"/{name}  {desc}{shortcut_text}",
                        classes=classes,
                        id=f"cmd-{name}",
                    )

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if query:
            self.filtered_commands = [
                cmd for cmd in self.COMMANDS
                if query in cmd[0].lower() or query in cmd[1].lower()
            ]
        else:
            self.filtered_commands = self.COMMANDS.copy()
        self.selected_index = 0
        self._update_selection()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filtered_commands:
            command = self.filtered_commands[self.selected_index][0]
            if self.callback:
                self.callback(command)
            self.dismiss(command)

    def on_key(self, event) -> None:
        if event.key == "down":
            self.selected_index = min(
                self.selected_index + 1, len(self.filtered_commands) - 1
            )
            self._update_selection()
            event.prevent_default()
        elif event.key == "up":
            self.selected_index = max(self.selected_index - 1, 0)
            self._update_selection()
            event.prevent_default()

    def _update_selection(self) -> None:
        # 更新选中状态
        for i, (name, _, _) in enumerate(self.COMMANDS):
            widget = self.query_one(f"#cmd-{name}", Static)
            if i < len(self.filtered_commands) and self.filtered_commands[i][0] == name:
                if i == self.selected_index:
                    widget.add_class("selected")
                else:
                    widget.remove_class("selected")


class XiaoTieApp(App):
    """小铁 TUI 主应用"""

    TITLE = "小铁 XiaoTie"
    SUB_TITLE = "AI 编程助手"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr auto auto;
    }

    #chat-container {
        width: 100%;
        height: 100%;
        padding: 0 1;
        background: $background;
    }

    #input-container {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 8;
        dock: bottom;
        background: $surface;
        border-top: solid $primary-darken-2;
        padding: 0 1;
    }

    #input-container Input {
        width: 100%;
        border: none;
        background: transparent;
    }

    #input-hint {
        color: $text-muted;
        text-style: dim;
        height: 1;
    }

    #status-bar {
        width: 100%;
        height: 1;
        dock: bottom;
        background: $primary-darken-3;
        padding: 0 1;
    }

    .thinking-indicator {
        width: 100%;
        height: 2;
        padding: 0 1;
        background: $surface-darken-2;
        border-left: thick $secondary;
        color: $text-muted;
    }

    .welcome-message {
        width: 100%;
        height: auto;
        padding: 2;
        margin: 2;
        background: $surface;
        border: round $primary;
        text-align: center;
    }

    .welcome-logo {
        text-style: bold;
        color: $primary;
    }

    .welcome-title {
        text-style: bold;
        margin-top: 1;
    }

    .welcome-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "命令面板", show=True),
        Binding("ctrl+n", "new_session", "新会话", show=True),
        Binding("ctrl+s", "save_session", "保存", show=True),
        Binding("ctrl+l", "clear_screen", "清屏", show=False),
        Binding("f1", "help", "帮助", show=True),
        Binding("ctrl+q", "quit", "退出", show=True),
    ]

    # 响应式属性
    model_name = reactive("claude-sonnet-4")
    total_tokens = reactive(0)
    session_name = reactive("新会话")
    parallel_mode = reactive(True)
    is_thinking = reactive(False)

    def __init__(
        self,
        agent=None,
        session_mgr=None,
        plugin_mgr=None,
        commands=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent = agent
        self.session_mgr = session_mgr
        self.plugin_mgr = plugin_mgr
        self.commands = commands
        self._thinking_widget = None

    def compose(self) -> ComposeResult:
        yield Header()

        # 聊天区域
        with ScrollableContainer(id="chat-container"):
            # 欢迎消息
            with Vertical(classes="welcome-message"):
                yield Static(
                    " ▄███▄\n █ ⚙ █\n ▀███▀",
                    classes="welcome-logo",
                )
                yield Static("欢迎使用小铁 XiaoTie", classes="welcome-title")
                yield Static(
                    "输入问题开始对话，或按 Ctrl+P 打开命令面板",
                    classes="welcome-hint",
                )

        # 输入区域
        with Vertical(id="input-container"):
            yield Static(
                "输入消息 (Enter 发送, / 开头为命令)",
                id="input-hint",
            )
            yield Input(placeholder="输入你的问题...", id="user-input")

        # 状态栏
        yield Static(id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        """挂载时初始化"""
        self._update_status_bar()
        # 聚焦输入框
        self.query_one("#user-input", Input).focus()

    def watch_model_name(self, value: str) -> None:
        self._update_status_bar()

    def watch_total_tokens(self, value: int) -> None:
        self._update_status_bar()

    def watch_session_name(self, value: str) -> None:
        self._update_status_bar()

    def watch_parallel_mode(self, value: bool) -> None:
        self._update_status_bar()

    def watch_is_thinking(self, value: bool) -> None:
        if value:
            self._show_thinking()
        else:
            self._hide_thinking()

    def _update_status_bar(self) -> None:
        """更新状态栏"""
        status_bar = self.query_one("#status-bar", Static)
        text = Text()
        text.append("⚙️ ", style="bold")
        text.append(f"{self.model_name}", style="cyan")
        text.append(" │ ", style="dim")
        text.append(f"📊 {self.total_tokens:,} tokens", style="yellow")
        text.append(" │ ", style="dim")
        text.append(f"💾 {self.session_name}", style="green")
        text.append(" │ ", style="dim")
        parallel_status = "⚡并行" if self.parallel_mode else "📝串行"
        text.append(parallel_status, style="magenta")
        status_bar.update(text)

    def _show_thinking(self) -> None:
        """显示思考指示器"""
        if self._thinking_widget is None:
            self._thinking_widget = Static(
                "💭 思考中...",
                classes="thinking-indicator",
            )
            chat_container = self.query_one("#chat-container")
            chat_container.mount(self._thinking_widget)
            chat_container.scroll_end()

    def _hide_thinking(self) -> None:
        """隐藏思考指示器"""
        if self._thinking_widget is not None:
            self._thinking_widget.remove()
            self._thinking_widget = None

    def add_message(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> None:
        """添加消息到聊天区域"""
        chat_container = self.query_one("#chat-container")

        # 移除欢迎消息
        welcome = chat_container.query(".welcome-message")
        for w in welcome:
            w.remove()

        # 添加消息
        message = ChatMessage(
            role=role,
            content=content,
            thinking=thinking,
            tool_name=tool_name,
        )
        chat_container.mount(message)
        chat_container.scroll_end()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        if event.input.id != "user-input":
            return

        user_input = event.value.strip()
        if not user_input:
            return

        event.input.value = ""

        # 处理命令
        if user_input.startswith("/"):
            await self._handle_command(user_input[1:])
            return

        # 添加用户消息
        self.add_message("user", user_input)

        # 运行 Agent
        if self.agent:
            await self._run_agent(user_input)

    async def _handle_command(self, cmd_line: str) -> None:
        """处理命令"""
        if self.commands:
            should_continue, message = await self.commands.execute(cmd_line)
            if message:
                self.add_message("system", message)
            if not should_continue:
                self.exit()
        else:
            self.add_message("system", f"命令系统未初始化")

    async def _run_agent(self, user_input: str) -> None:
        """运行 Agent"""
        self.is_thinking = True

        try:
            # 设置回调
            def on_thinking(text: str):
                pass  # TUI 模式下不显示思考过程

            def on_content(text: str):
                pass  # 流式内容在最后统一显示

            self.agent.on_thinking = on_thinking
            self.agent.on_content = on_content

            # 运行
            result = await self.agent.run(user_input)

            # 更新 token 统计
            self.total_tokens = self.agent.api_total_tokens

            # 添加回复
            self.add_message("assistant", result)

        except Exception as e:
            self.add_message("system", f"❌ 错误: {e}")

        finally:
            self.is_thinking = False

    def action_command_palette(self) -> None:
        """打开命令面板"""
        def on_command(cmd: str):
            asyncio.create_task(self._handle_command(cmd))

        self.push_screen(CommandPaletteScreen(callback=on_command))

    def action_new_session(self) -> None:
        """新建会话"""
        asyncio.create_task(self._handle_command("new"))

    def action_save_session(self) -> None:
        """保存会话"""
        asyncio.create_task(self._handle_command("save"))

    def action_clear_screen(self) -> None:
        """清屏"""
        chat_container = self.query_one("#chat-container")
        for child in chat_container.children:
            child.remove()

    def action_help(self) -> None:
        """显示帮助"""
        self.push_screen(HelpScreen())
