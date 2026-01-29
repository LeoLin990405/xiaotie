"""小铁 TUI 主应用

参考 OpenCode 设计：
- 分割面板布局（消息区 + 侧边栏）
- 底部编辑器
- 命令面板 (Ctrl+K)
- 状态行
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer, Container
from textual.widgets import Header, Footer, Static, Input, Label, Button
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .widgets import (
    ChatMessage,
    MessageList,
    Editor,
    SessionList,
    StatusLine,
    ThinkingIndicator,
    CommandPaletteItem,
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
        color: $primary;
    }

    HelpScreen .help-section {
        margin-top: 1;
        text-style: bold;
        color: $secondary;
    }

    HelpScreen .help-item {
        margin-left: 2;
    }

    HelpScreen .help-key {
        color: $warning;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⚙️ 小铁帮助", classes="help-title")

            yield Static("快捷键", classes="help-section")
            yield Static("Ctrl+K  命令面板", classes="help-item")
            yield Static("Ctrl+B  切换侧边栏", classes="help-item")
            yield Static("Ctrl+N  新会话", classes="help-item")
            yield Static("Ctrl+S  保存会话", classes="help-item")
            yield Static("Ctrl+L  清屏", classes="help-item")
            yield Static("Ctrl+Q  退出", classes="help-item")
            yield Static("F1      帮助", classes="help-item")

            yield Static("命令", classes="help-section")
            yield Static("/help     显示帮助", classes="help-item")
            yield Static("/quit     退出程序", classes="help-item")
            yield Static("/reset    重置对话", classes="help-item")
            yield Static("/tools    显示工具", classes="help-item")
            yield Static("/save     保存会话", classes="help-item")
            yield Static("/sessions 会话列表", classes="help-item")
            yield Static("/new      新建会话", classes="help-item")
            yield Static("/config   显示配置", classes="help-item")
            yield Static("/status   系统状态", classes="help-item")

            yield Static("\n按 ESC 或 Q 关闭", classes="help-item")


class CommandPaletteScreen(ModalScreen):
    """命令面板 - Ctrl+K 风格"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center top;
        padding-top: 5;
    }

    CommandPaletteScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: solid $primary;
        padding: 0;
    }

    CommandPaletteScreen .palette-header {
        width: 100%;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
        color: $text-muted;
    }

    CommandPaletteScreen Input {
        width: 100%;
        border: none;
        background: $surface;
        padding: 0 1;
    }

    CommandPaletteScreen Input:focus {
        border: none;
    }

    CommandPaletteScreen .command-list {
        width: 100%;
        height: auto;
        max-height: 20;
        padding: 0;
    }

    CommandPaletteScreen .cmd-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    CommandPaletteScreen .cmd-item:hover {
        background: $primary-darken-2;
    }

    CommandPaletteScreen .cmd-item.selected {
        background: $primary-darken-1;
    }

    CommandPaletteScreen .no-results {
        width: 100%;
        padding: 1;
        text-align: center;
        color: $text-muted;
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
        ("config", "显示当前配置", ""),
        ("status", "显示系统状态", ""),
        ("tree", "显示目录结构", ""),
        ("map", "显示代码库概览", ""),
        ("find", "搜索相关文件", ""),
        ("plugins", "显示已加载插件", ""),
        ("compact", "压缩对话历史", ""),
        ("copy", "复制最后回复", ""),
        ("undo", "撤销最后对话", ""),
        ("retry", "重试最后请求", ""),
    ]

    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.filtered_commands = self.COMMANDS.copy()
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⌘ 命令面板 (输入搜索)", classes="palette-header")
            yield Input(placeholder="输入命令...", id="cmd-input")
            with ScrollableContainer(classes="command-list"):
                for i, (name, desc, shortcut) in enumerate(self.COMMANDS):
                    classes = "cmd-item selected" if i == 0 else "cmd-item"
                    yield Static(
                        self._format_cmd(name, desc, shortcut),
                        classes=classes,
                        id=f"cmd-{name}",
                    )

    def _format_cmd(self, name: str, desc: str, shortcut: str) -> Text:
        text = Text()
        text.append(f"/{name}", style="bold cyan")
        text.append(f"  {desc}", style="dim")
        if shortcut:
            text.append(f"  [{shortcut}]", style="yellow dim")
        return text

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "cmd-input":
            return
        query = event.value.lower().strip()
        if query:
            self.filtered_commands = [
                cmd for cmd in self.COMMANDS
                if query in cmd[0].lower() or query in cmd[1].lower()
            ]
        else:
            self.filtered_commands = self.COMMANDS.copy()
        self.selected_index = 0
        self._update_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd-input":
            return
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

    def _update_list(self) -> None:
        """更新命令列表显示"""
        command_list = self.query_one(".command-list")
        # 清空
        for child in list(command_list.children):
            child.remove()

        if self.filtered_commands:
            for i, (name, desc, shortcut) in enumerate(self.filtered_commands):
                classes = "cmd-item selected" if i == 0 else "cmd-item"
                command_list.mount(Static(
                    self._format_cmd(name, desc, shortcut),
                    classes=classes,
                    id=f"cmd-{name}",
                ))
        else:
            command_list.mount(Static("无匹配命令", classes="no-results"))

    def _update_selection(self) -> None:
        """更新选中状态"""
        items = self.query(".cmd-item")
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
            else:
                item.remove_class("selected")


class XiaoTieApp(App):
    """小铁 TUI 主应用 - OpenCode 风格"""

    TITLE = "小铁 XiaoTie"
    SUB_TITLE = "AI 编程助手"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr auto auto;
    }

    /* 主内容区 - 分割布局 */
    #main-container {
        width: 100%;
        height: 100%;
    }

    #main-container > Horizontal {
        width: 100%;
        height: 100%;
    }

    /* 消息区 */
    #messages-pane {
        width: 1fr;
        height: 100%;
        min-width: 40;
    }

    /* 侧边栏 */
    #sidebar {
        width: 30;
        height: 100%;
        background: $surface-darken-1;
        border-left: solid $surface-lighten-1;
    }

    #sidebar.hidden {
        display: none;
    }

    /* 分隔线 */
    #divider {
        width: 1;
        height: 100%;
        background: $surface-lighten-1;
    }

    #divider.hidden {
        display: none;
    }

    /* 编辑器区 */
    #editor-container {
        width: 100%;
        height: auto;
        min-height: 3;
        dock: bottom;
    }

    /* 状态行 */
    #status-line {
        width: 100%;
        height: 1;
        dock: bottom;
    }

    /* 思考指示器 */
    .thinking {
        width: 100%;
        height: 2;
        padding: 0 2;
        background: $surface-darken-1;
        border-left: thick $secondary;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("ctrl+k", "command_palette", "命令面板", show=True),
        Binding("ctrl+p", "command_palette", "命令面板", show=False),
        Binding("ctrl+b", "toggle_sidebar", "侧边栏", show=True),
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
    thinking_mode = reactive(True)
    is_processing = reactive(False)
    sidebar_visible = reactive(True)

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

        # 主内容区 - 分割布局
        with Container(id="main-container"):
            with Horizontal():
                # 消息区
                yield MessageList(id="messages-pane")
                # 分隔线
                yield Static("", id="divider")
                # 侧边栏
                yield SessionList(id="sidebar")

        # 编辑器
        yield Editor(id="editor-container")

        # 状态行
        yield StatusLine(id="status-line")

        yield Footer()

    def on_mount(self) -> None:
        """挂载时初始化"""
        self._update_status()
        # 聚焦编辑器
        self.query_one("#editor-container", Editor).focus_input()

    def watch_model_name(self, value: str) -> None:
        self._update_status()

    def watch_total_tokens(self, value: int) -> None:
        self._update_status()

    def watch_session_name(self, value: str) -> None:
        self._update_status()

    def watch_parallel_mode(self, value: bool) -> None:
        self._update_status()

    def watch_thinking_mode(self, value: bool) -> None:
        self._update_status()

    def watch_is_processing(self, value: bool) -> None:
        status_line = self.query_one("#status-line", StatusLine)
        status_line.status = "处理中..." if value else "就绪"
        editor = self.query_one("#editor-container", Editor)
        editor.set_processing(value)

        if value:
            self._show_thinking()
        else:
            self._hide_thinking()

    def watch_sidebar_visible(self, value: bool) -> None:
        sidebar = self.query_one("#sidebar")
        divider = self.query_one("#divider")
        if value:
            sidebar.remove_class("hidden")
            divider.remove_class("hidden")
        else:
            sidebar.add_class("hidden")
            divider.add_class("hidden")

    def _update_status(self) -> None:
        """更新状态行"""
        status_line = self.query_one("#status-line", StatusLine)
        status_line.model = self.model_name
        status_line.tokens = self.total_tokens
        status_line.session = self.session_name
        status_line.parallel = self.parallel_mode
        status_line.thinking = self.thinking_mode

    def _show_thinking(self) -> None:
        """显示思考指示器"""
        if self._thinking_widget is None:
            self._thinking_widget = ThinkingIndicator()
            messages = self.query_one("#messages-pane", MessageList)
            messages.mount(self._thinking_widget)
            messages.scroll_end()

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
        """添加消息"""
        messages = self.query_one("#messages-pane", MessageList)
        messages.add_message(role, content, thinking, tool_name)

    async def on_editor_submitted(self, event: Editor.Submitted) -> None:
        """处理编辑器提交"""
        user_input = event.value.strip()
        if not user_input:
            return

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
            self.add_message("system", "命令系统未初始化")

    async def _run_agent(self, user_input: str) -> None:
        """运行 Agent"""
        self.is_processing = True

        try:
            # 设置回调（TUI 模式下不使用流式回调）
            self.agent.on_thinking = lambda x: None
            self.agent.on_content = lambda x: None

            # 运行
            result = await self.agent.run(user_input)

            # 更新 token 统计
            self.total_tokens = self.agent.api_total_tokens

            # 获取最后的思考内容
            thinking = None
            if self.agent.messages:
                last_msg = self.agent.messages[-1]
                if hasattr(last_msg, 'thinking'):
                    thinking = last_msg.thinking

            # 添加回复
            self.add_message("assistant", result, thinking=thinking)

        except Exception as e:
            self.add_message("system", f"错误: {e}")

        finally:
            self.is_processing = False

    def action_command_palette(self) -> None:
        """打开命令面板"""
        def on_command(cmd: str):
            asyncio.create_task(self._handle_command(cmd))

        self.push_screen(CommandPaletteScreen(callback=on_command))

    def action_toggle_sidebar(self) -> None:
        """切换侧边栏"""
        self.sidebar_visible = not self.sidebar_visible

    def action_new_session(self) -> None:
        """新建会话"""
        asyncio.create_task(self._handle_command("new"))

    def action_save_session(self) -> None:
        """保存会话"""
        asyncio.create_task(self._handle_command("save"))

    def action_clear_screen(self) -> None:
        """清屏"""
        messages = self.query_one("#messages-pane", MessageList)
        messages.clear_messages()

    def action_help(self) -> None:
        """显示帮助"""
        self.push_screen(HelpScreen())

    def update_sessions(self, sessions: List[dict]) -> None:
        """更新会话列表"""
        sidebar = self.query_one("#sidebar", SessionList)
        sidebar.update_sessions(sessions)

    def on_session_item_selected(self, event: "SessionItem.Selected") -> None:
        """处理会话选择"""
        asyncio.create_task(self._handle_command(f"load {event.session_id}"))
