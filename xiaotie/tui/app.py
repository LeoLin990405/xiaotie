"""小铁 TUI 主应用 - OpenCode 风格

参考 OpenCode 设计：
- 分割面板布局（消息区 + 侧边栏）
- 底部编辑器
- 命令面板 (Ctrl+K)
- 模型选择器 (Ctrl+M)
- 主题选择器 (Ctrl+T)
- Toast 通知
- 状态行
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Static

from ..i18n import set_language, t
from .command_palette import CommandPalette, QuickModelSelector
from .onboarding import OnboardingWizard, should_show_onboarding
from .themes import ThemeManager, get_theme, get_theme_display_name, list_themes
from .widgets import (
    Editor,
    MessageList,
    SessionItem,
    SessionList,
    StatusLine,
    ThinkingIndicator,
    Toast,
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
            yield Static("󰋽 小铁帮助", classes="help-title")

            yield Static("快捷键", classes="help-section")
            yield Static("Ctrl+K  命令面板", classes="help-item")
            yield Static("Ctrl+B  切换侧边栏", classes="help-item")
            yield Static("Ctrl+M  模型选择", classes="help-item")
            yield Static("Ctrl+T  主题选择", classes="help-item")
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
            yield Static("/themes   主题列表", classes="help-item")

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
        background: $primary 30%;
    }

    CommandPaletteScreen .cmd-item.selected {
        background: $primary 40%;
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
        ("themes", "主题列表", "Ctrl+T"),
        ("models", "模型列表", "Ctrl+M"),
        ("cache", "缓存管理", ""),
        ("system-info", "系统信息", ""),
        ("process-manager", "进程管理", ""),
        ("network-tools", "网络工具", ""),
    ]

    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.filtered_commands = self.COMMANDS.copy()
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰌌 命令面板 (输入搜索)", classes="palette-header")
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
                cmd for cmd in self.COMMANDS if query in cmd[0].lower() or query in cmd[1].lower()
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
            self.selected_index = min(self.selected_index + 1, len(self.filtered_commands) - 1)
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
                command_list.mount(
                    Static(
                        self._format_cmd(name, desc, shortcut),
                        classes=classes,
                        id=f"cmd-{name}",
                    )
                )
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


class ModelSelectorScreen(ModalScreen):
    """模型选择器屏幕"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    ModelSelectorScreen {
        align: center middle;
    }

    ModelSelectorScreen > Vertical {
        width: 50;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    ModelSelectorScreen .selector-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    ModelSelectorScreen .model-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    ModelSelectorScreen .model-item:hover {
        background: $primary 30%;
    }

    ModelSelectorScreen .model-item.selected {
        background: $primary 40%;
    }
    """

    MODELS = [
        ("mimo-v2-pro", "󰮯 MIMO v2 Pro"),
        ("mimo-v2-omni", "󰮯 MIMO v2 Omni"),
    ]

    def __init__(self, current_model: str = "", callback=None, **kwargs):
        super().__init__(**kwargs)
        self.current_model = current_model
        self.callback = callback
        self.selected_index = 0
        for i, (value, _) in enumerate(self.MODELS):
            if value == current_model:
                self.selected_index = i
                break

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰚩 选择模型", classes="selector-title")
            for value, display in self.MODELS:
                is_selected = value == self.current_model
                classes = "model-item selected" if is_selected else "model-item"
                yield Static(display, classes=classes, id=f"model-{value}")

    def on_key(self, event) -> None:
        if event.key == "down":
            self.selected_index = min(self.selected_index + 1, len(self.MODELS) - 1)
            self._update_selection()
            event.prevent_default()
        elif event.key == "up":
            self.selected_index = max(self.selected_index - 1, 0)
            self._update_selection()
            event.prevent_default()
        elif event.key == "enter":
            model = self.MODELS[self.selected_index][0]
            if self.callback:
                self.callback(model)
            self.dismiss(model)
            event.prevent_default()

    def _update_selection(self) -> None:
        items = list(self.query(".model-item"))
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
            else:
                item.remove_class("selected")

    def on_static_click(self, event) -> None:
        """处理模型点击"""
        widget_id = event.widget.id
        if widget_id and widget_id.startswith("model-"):
            model = widget_id[6:]  # 去掉 "model-" 前缀
            if self.callback:
                self.callback(model)
            self.dismiss(model)


class ThemeSelectorScreen(ModalScreen):
    """主题选择器屏幕"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    ThemeSelectorScreen {
        align: center middle;
    }

    ThemeSelectorScreen > Vertical {
        width: 76;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    ThemeSelectorScreen .selector-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    ThemeSelectorScreen .theme-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    ThemeSelectorScreen .theme-item:hover {
        background: $primary 30%;
    }

    ThemeSelectorScreen .theme-item.selected {
        background: $primary 40%;
    }

    ThemeSelectorScreen .theme-layout {
        width: 100%;
        height: auto;
    }

    ThemeSelectorScreen .theme-list {
        width: 34;
        height: auto;
        max-height: 20;
    }

    ThemeSelectorScreen .theme-preview {
        width: 1fr;
        height: auto;
        border: round $border;
        padding: 1;
        margin-left: 1;
    }

    ThemeSelectorScreen .preview-title {
        text-style: bold;
        color: $primary;
    }

    ThemeSelectorScreen .preview-status {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        current_theme: str = "default",
        callback=None,
        preview_callback=None,
        restore_callback=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._original_theme = current_theme
        self.current_theme = current_theme
        self.callback = callback
        self.preview_callback = preview_callback
        self.restore_callback = restore_callback
        self._theme_ids = list_themes()
        self.selected_index = (
            self._theme_ids.index(current_theme) if current_theme in self._theme_ids else 0
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰏘 选择主题", classes="selector-title")
            with Horizontal(classes="theme-layout"):
                with Vertical(classes="theme-list"):
                    for i, theme_id in enumerate(self._theme_ids):
                        display = get_theme_display_name(theme_id)
                        is_selected = i == self.selected_index
                        classes = "theme-item selected" if is_selected else "theme-item"
                        yield Static(f"󰏘 {display}", classes=classes, id=f"theme-{theme_id}")
                with Vertical(classes="theme-preview"):
                    yield Static("实时预览", classes="preview-title")
                    yield Static("", id="theme-preview-content")
                    yield Static("󰔟 准备就绪", classes="preview-status", id="theme-preview-status")

    def on_mount(self) -> None:
        self._render_preview(self._theme_ids[self.selected_index])

    def on_key(self, event) -> None:
        if event.key == "down":
            self.selected_index = min(self.selected_index + 1, len(self._theme_ids) - 1)
            self._update_selection()
            self._render_preview(self._theme_ids[self.selected_index])
            event.prevent_default()
        elif event.key == "up":
            self.selected_index = max(self.selected_index - 1, 0)
            self._update_selection()
            self._render_preview(self._theme_ids[self.selected_index])
            event.prevent_default()
        elif event.key == "enter":
            theme = self._theme_ids[self.selected_index]
            if self.callback:
                self.callback(theme)
            self.dismiss(theme)
            event.prevent_default()

    def _update_selection(self) -> None:
        items = list(self.query(".theme-item"))
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
            else:
                item.remove_class("selected")

    def on_static_click(self, event) -> None:
        """处理主题点击"""
        widget_id = event.widget.id
        if widget_id and widget_id.startswith("theme-"):
            theme = widget_id[6:]  # 去掉 "theme-" 前缀
            self.selected_index = self._theme_ids.index(theme)
            self._update_selection()
            self._render_preview(theme)
            if self.callback:
                self.callback(theme)
            self.dismiss(theme)

    def action_dismiss(self) -> None:
        if self.restore_callback:
            self.restore_callback(self._original_theme)
        self.dismiss(None)

    def _render_preview(self, theme_id: str) -> None:
        status = self.query_one("#theme-preview-status", Static)
        status.update("󰔟 切换预览中...")
        if self.preview_callback:
            self.preview_callback(theme_id)
        preview = self.query_one("#theme-preview-content", Static)
        preview.update(
            "\n".join(
                [
                    f"主题: {get_theme_display_name(theme_id)}",
                    "用户: 请帮我优化这个函数",
                    "小铁: 已完成重构建议并附上测试方案",
                    "状态: 处理中 → 已完成",
                    "命令: Ctrl+K / Ctrl+M / Ctrl+T",
                ]
            )
        )
        self.set_timer(0.15, lambda: status.update("✅ 预览已更新"))


class RiskConfirmScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    RiskConfirmScreen {
        align: center middle;
    }

    RiskConfirmScreen > Vertical {
        width: 78;
        height: auto;
        background: $surface;
        border: solid $error;
        padding: 1;
    }

    RiskConfirmScreen .risk-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    RiskConfirmScreen .risk-meta {
        color: $text-muted;
        margin-bottom: 1;
    }

    RiskConfirmScreen .risk-prompt {
        color: $warning;
        margin-top: 1;
    }

    RiskConfirmScreen Input {
        margin: 1 0;
    }

    RiskConfirmScreen .risk-status {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, command: str, intent: str, cooldown_seconds: int = 3, **kwargs):
        super().__init__(**kwargs)
        self.command = command
        self.intent = intent
        self.cooldown_seconds = cooldown_seconds
        self._remaining = cooldown_seconds

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⚠ 高风险操作确认", classes="risk-title")
            yield Static(f"意图识别: {self.intent}", classes="risk-meta")
            yield Static(f"操作命令: /{self.command}", classes="risk-meta")
            yield Static("请输入 CONFIRM 进行二次确认", classes="risk-prompt")
            yield Input(placeholder="输入 CONFIRM", id="risk-confirm-input")
            yield Static(f"冷却中: {self._remaining}s", classes="risk-status", id="risk-status")
            with Horizontal():
                yield Button("取消", variant="default", id="risk-cancel")
                yield Button("确认执行", variant="error", id="risk-confirm", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#risk-confirm-input", Input).focus()
        self.set_interval(1.0, self._tick_cooldown)

    def _tick_cooldown(self) -> None:
        if self._remaining <= 0:
            return
        self._remaining -= 1
        status = self.query_one("#risk-status", Static)
        if self._remaining <= 0:
            status.update("冷却完成，可确认执行")
            self._refresh_confirm_state()
        else:
            status.update(f"冷却中: {self._remaining}s")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "risk-confirm-input":
            self._refresh_confirm_state()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "risk-confirm-input":
            return
        typed = event.input.value.strip().upper() == "CONFIRM"
        if typed and self._remaining <= 0:
            self.dismiss(True)

    def _refresh_confirm_state(self) -> None:
        confirm_button = self.query_one("#risk-confirm", Button)
        typed = self.query_one("#risk-confirm-input", Input).value.strip().upper() == "CONFIRM"
        confirm_button.disabled = not (typed and self._remaining <= 0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "risk-cancel":
            self.dismiss(False)
        elif event.button.id == "risk-confirm":
            self.dismiss(True)


class XiaoTieApp(App):
    """小铁 TUI 主应用 - OpenCode 风格"""

    TITLE = "小铁 XiaoTie"
    SUB_TITLE = "AI 编程助手"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 1fr auto auto;
        background: $background;
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
        background: $background;
    }

    /* 侧边栏 */
    #sidebar {
        width: 30;
        height: 100%;
        background: $surface-darken-1;
        border-left: solid $border;
    }

    #sidebar.hidden {
        display: none;
    }

    #sidebar.compact {
        width: 24;
    }

    /* 分隔线 */
    #divider {
        width: 1;
        height: 100%;
        background: $border;
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

    /* Toast 容器 */
    #toast-container {
        dock: top;
        align: right top;
        width: auto;
        height: auto;
        layer: notification;
    }

    .compact-mode #messages-pane {
        min-width: 30;
    }

    .compact-mode #editor-container {
        min-height: 2;
    }

    .compact-mode #status-line {
        height: 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+k", "command_palette", "命令面板", show=True),
        Binding("ctrl+p", "command_palette", "命令面板", show=False),
        Binding("ctrl+b", "toggle_sidebar", "侧边栏", show=True),
        Binding("ctrl+m", "model_selector", "模型", show=True),
        Binding("ctrl+t", "theme_selector", "主题", show=True),
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
    ui_theme = reactive("default")

    def __init__(
        self,
        agent=None,
        session_mgr=None,
        plugin_mgr=None,
        commands=None,
        show_onboarding: bool = False,
        onboarding_required: bool = False,
        language: Optional[str] = None,
        **kwargs,
    ):
        self._theme_manager = ThemeManager.get_instance()
        super().__init__(**kwargs)
        self.agent = agent
        self.session_mgr = session_mgr
        self.plugin_mgr = plugin_mgr
        self.commands = commands
        self.show_onboarding = show_onboarding
        self.onboarding_required = onboarding_required
        self.onboarding_result: Optional[dict] = None
        self.language = language or (
            "zh" if os.environ.get("LANG", "").lower().startswith("zh") else "en"
        )
        self._thinking_widget = None
        self._risk_log_path = Path.home() / ".xiaotie" / "risk_actions.log"
        self._theme_preview_original: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()

        # Toast 容器
        yield Container(id="toast-container")

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
        set_language(self.language)
        self._theme_manager.subscribe(self._on_theme_changed)
        self._on_theme_changed(self._theme_manager.get_current_theme())
        self._sync_sessions()
        self._apply_responsive_layout(self.size.width)
        self._update_status()
        # 聚焦编辑器
        self.query_one("#editor-container", Editor).focus_input()
        if self.show_onboarding or should_show_onboarding():
            self.set_timer(0.05, self._open_onboarding)

    def on_unmount(self) -> None:
        self._theme_manager.unsubscribe(self._on_theme_changed)

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

    def on_resize(self, event) -> None:
        self._apply_responsive_layout(event.size.width)

    def watch_ui_theme(self, value: str) -> None:
        if self._theme_manager.get_current_theme() != value:
            if not self._theme_manager.set_theme(value):
                self.ui_theme = self._theme_manager.get_current_theme()
                return
        self._update_status()

    def _update_status(self) -> None:
        """更新状态行"""
        try:
            status_line = self.query_one("#status-line", StatusLine)
        except Exception:
            return
        status_line.model = self.model_name
        status_line.tokens = self.total_tokens
        status_line.session = self.session_name
        status_line.parallel = self.parallel_mode
        status_line.thinking = self.thinking_mode
        status_line.theme_name = self.ui_theme

    def _sync_sessions(self) -> None:
        if not self.session_mgr:
            return
        try:
            sessions = self.session_mgr.list_sessions()
            normalized = []
            current = getattr(self.session_mgr, "current_session", None)
            for item in sessions:
                if isinstance(item, str):
                    normalized.append(
                        {
                            "id": item,
                            "title": item,
                            "message_count": 0,
                            "is_current": item == current,
                        }
                    )
                elif isinstance(item, dict):
                    normalized.append(
                        {
                            "id": item.get("id", ""),
                            "title": item.get("title", "未命名"),
                            "message_count": item.get("message_count", 0),
                            "is_current": item.get("id") == current,
                        }
                    )
            self.update_sessions(normalized)
        except Exception:
            pass

    def _apply_responsive_layout(self, width: int) -> None:
        sidebar = self.query_one("#sidebar")
        if width < 110:
            self.sidebar_visible = False
            self.add_class("compact-mode")
            sidebar.add_class("compact")
            return
        self.remove_class("compact-mode")
        sidebar.remove_class("compact")
        if width >= 130:
            self.sidebar_visible = True

    def _on_theme_changed(self, name: str) -> None:
        """主题变更回调"""
        theme = get_theme(name)
        self.stylesheet.set_variables(
            {
                "primary": theme.primary,
                "secondary": theme.secondary,
                "accent": theme.accent,
                "success": theme.success,
                "warning": theme.warning,
                "error": theme.error,
                "info": theme.info,
                "background": theme.background,
                "background-panel": theme.background_panel,
                "background-element": theme.background_element,
                "surface": theme.surface,
                "text": theme.text,
                "text-muted": theme.text_muted,
                "border": theme.border,
                "border-active": theme.border_active,
                "border-subtle": theme.border_subtle,
                "diff-added": theme.diff_added,
                "diff-removed": theme.diff_removed,
                "diff-context": theme.diff_context,
                "markdown-heading": theme.markdown_heading,
                "markdown-link": theme.markdown_link,
                "markdown-code": theme.markdown_code,
                "markdown-quote": theme.markdown_quote,
                "syntax-keyword": theme.syntax_keyword,
                "syntax-function": theme.syntax_function,
                "syntax-string": theme.syntax_string,
                "syntax-number": theme.syntax_number,
                "syntax-comment": theme.syntax_comment,
            }
        )
        self.refresh_css()

        if self.ui_theme != name:
            self.ui_theme = name

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

    def show_toast(
        self,
        title: str,
        message: str,
        variant: str = "info",
        duration: float = 3.0,
    ) -> None:
        """显示 Toast 通知"""
        toast = Toast(title=title, message=message, variant=variant, duration=duration)
        container = self.query_one("#toast-container")
        container.mount(toast)

    def add_message(
        self,
        role: str,
        content: str,
        thinking: Optional[str] = None,
        tool_name: Optional[str] = None,
        is_error: bool = False,
    ) -> None:
        """添加消息"""
        messages = self.query_one("#messages-pane", MessageList)
        messages.add_message(role, content, thinking, tool_name, is_error)

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
        approved, intent = await self._confirm_risky_command(cmd_line)
        if not approved:
            self.show_toast(t("warning"), "已取消高风险操作", variant="warning")
            self._log_risky_action(cmd_line, intent, "cancelled")
            return
        # 特殊命令处理
        if cmd_line == "themes":
            self.action_theme_selector()
            return
        if cmd_line == "models":
            self.action_model_selector()
            return

        if self.commands:
            try:
                should_continue, message = await self.commands.execute(cmd_line)
                if message:
                    self.add_message("system", message)
                    if "开发中" in message or "用法" in message:
                        self.show_toast("操作提示", message, variant="warning")
                if not should_continue:
                    self.exit()
                self._sync_sessions()
                if intent:
                    self._log_risky_action(cmd_line, intent, "executed")
            except Exception:
                if intent:
                    self._log_risky_action(cmd_line, intent, "failed")
                raise
        else:
            self.add_message("system", "命令系统未初始化")

    async def _run_agent(self, user_input: str) -> None:
        """运行 Agent"""
        self.is_processing = True

        try:
            from .streaming import StreamingMessage, StreamingRenderer

            messages = self.query_one("#messages-pane", MessageList)

            # 移除欢迎消息
            if not messages._has_messages:
                welcome = messages.query("#welcome-msg")
                for w in welcome:
                    w.remove()
                messages._has_messages = True

            # 创建流式消息和渲染器
            streaming_msg = StreamingMessage()
            messages.mount(streaming_msg)
            messages.scroll_end(animate=False)

            renderer = StreamingRenderer(
                message_widget=streaming_msg,
                scroll_callback=lambda: messages.scroll_end(animate=False),
            )
            await renderer.start()

            # 设置回调
            self.agent.on_thinking = renderer.on_thinking
            self.agent.on_content = renderer.on_content

            # 运行
            await self.agent.run(user_input)

            await renderer.stop()

            # 更新 token 统计
            self.total_tokens = self.agent.api_total_tokens

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "quota" in error_str:
                guidance = "请稍后重试，或使用 Ctrl+M 切换到其他模型"
                variant = "warning"
            elif (
                "auth" in error_str
                or "401" in error_str
                or "api_key" in error_str
                or "invalid" in error_str
            ):
                guidance = "请检查 API Key 配置，使用 /config 查看当前设置"
                variant = "error"
            elif "timeout" in error_str or "timed out" in error_str:
                guidance = "请求超时，请检查网络或缩短提示词后重试"
                variant = "warning"
            elif "connect" in error_str or "network" in error_str or "resolve" in error_str:
                guidance = "网络连接失败，请检查网络环境或代理设置"
                variant = "error"
            else:
                guidance = f"{e} · 可用 /help 查看命令"
                variant = "error"
            self.add_message("system", f"错误: {e}", is_error=True)
            self.show_toast("错误", guidance, variant=variant)

        finally:
            self.is_processing = False

    def action_command_palette(self) -> None:
        """打开命令面板"""

        def on_command(cmd: str):
            asyncio.create_task(self._handle_command(cmd))

        self.push_screen(CommandPalette(callback=on_command))

    def action_toggle_sidebar(self) -> None:
        """切换侧边栏"""
        self.sidebar_visible = not self.sidebar_visible

    def action_model_selector(self) -> None:
        """打开模型选择器"""

        def on_model(provider: str, model: str):
            self.model_name = model
            self.show_toast("模型已切换", f"{provider} / {model}", variant="success")

        self.push_screen(QuickModelSelector(current_model=self.model_name, callback=on_model))

    def action_theme_selector(self) -> None:
        """打开主题选择器"""
        self._theme_preview_original = self.ui_theme

        def on_theme(theme: str):
            self.ui_theme = theme
            display_name = get_theme_display_name(theme)
            self.show_toast("主题已切换", f"当前主题: {display_name}", variant="success")

        def on_preview(theme: str):
            self.ui_theme = theme

        def on_restore(theme: str):
            if self._theme_preview_original and theme != self.ui_theme:
                self.ui_theme = theme

        self.push_screen(
            ThemeSelectorScreen(
                current_theme=self.ui_theme,
                callback=on_theme,
                preview_callback=on_preview,
                restore_callback=on_restore,
            )
        )

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

    def _open_onboarding(self) -> None:
        def on_complete(provider: str, model: str, api_key: str):
            self.model_name = model
            if api_key:
                os.environ[f"{provider.upper()}_API_KEY"] = api_key

        def on_result(result):
            if isinstance(result, dict):
                self.onboarding_result = result
                if result.get("completed"):
                    self.show_toast(t("success"), "引导配置已完成", variant="success")
                elif result.get("skipped"):
                    self.show_toast(
                        t("warning"), "已跳过引导，可通过 /help 查看操作", variant="warning"
                    )
                if self.onboarding_required:
                    self.exit()

        self.push_screen(OnboardingWizard(on_complete=on_complete), on_result)

    def _classify_risky_intent(self, cmd_line: str) -> Tuple[bool, str]:
        command = cmd_line.strip().lower()
        patterns: Dict[str, str] = {
            r"^(quit|exit)$": "退出会话（未保存的对话将丢失）",
            r"^(reset|clear)$": "清空上下文（当前对话历史将被清除）",
            r"^(delete|remove|rm)\b": "删除数据（该操作不可撤销）",
            r"^(danger|unsafe|safe off)\b": "降级安全策略（将允许高风险操作自动执行）",
            r"^(process-manager|kill)\b": "进程终止（可能影响正在运行的服务）",
            r"^compact\b": "压缩对话历史（早期消息细节将被摘要替代）",
            r"^undo\b": "撤销最后对话（将移除最后一组问答）",
        }
        for pattern, intent in patterns.items():
            if re.search(pattern, command):
                return True, intent
        return False, ""

    async def _confirm_risky_command(self, cmd_line: str) -> Tuple[bool, str]:
        risky, intent = self._classify_risky_intent(cmd_line)
        if not risky:
            return True, ""
        future: asyncio.Future = asyncio.get_running_loop().create_future()

        def on_result(confirmed):
            if not future.done():
                future.set_result(bool(confirmed))

        self.push_screen(RiskConfirmScreen(command=cmd_line, intent=intent), on_result)
        confirmed = await future
        return confirmed, intent

    def _log_risky_action(self, command: str, intent: str, status: str) -> None:
        self._risk_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "command": command,
            "intent": intent,
            "status": status,
        }
        with self._risk_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
