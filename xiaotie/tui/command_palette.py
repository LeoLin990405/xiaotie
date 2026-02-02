"""命令面板模块 - 增强版

功能:
- 模糊搜索命令
- 动态模型列表
- 命令分类
- 历史记录搜索
- 快捷键提示
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class CommandCategory(str, Enum):
    """命令分类"""

    GENERAL = "general"  # 通用
    SESSION = "session"  # 会话
    MODEL = "model"  # 模型
    DISPLAY = "display"  # 显示
    TOOLS = "tools"  # 工具
    DEBUG = "debug"  # 调试


@dataclass
class Command:
    """命令定义"""

    name: str
    description: str
    shortcut: str = ""
    category: CommandCategory = CommandCategory.GENERAL
    icon: str = ""
    aliases: List[str] = field(default_factory=list)

    @property
    def search_text(self) -> str:
        """用于搜索的文本"""
        return f"{self.name} {self.description} {' '.join(self.aliases)}".lower()


# 默认命令列表
DEFAULT_COMMANDS: List[Command] = [
    # 通用
    Command("help", "显示帮助信息", "F1", CommandCategory.GENERAL, "󰋽", ["h", "?"]),
    Command("quit", "退出程序", "Ctrl+Q", CommandCategory.GENERAL, "󰗼", ["q", "exit"]),
    Command("clear", "清空屏幕", "Ctrl+L", CommandCategory.GENERAL, "󰃢", ["cls"]),
    # 会话
    Command("new", "创建新会话", "Ctrl+N", CommandCategory.SESSION, "󰝒", ["n"]),
    Command("save", "保存当前会话", "Ctrl+S", CommandCategory.SESSION, "󰆓", ["s"]),
    Command("sessions", "列出所有会话", "", CommandCategory.SESSION, "󰪶", ["ls"]),
    Command("reset", "重置对话", "", CommandCategory.SESSION, "󰑓", ["r"]),
    Command("undo", "撤销最后对话", "", CommandCategory.SESSION, "󰕌", ["u"]),
    Command("retry", "重试最后请求", "", CommandCategory.SESSION, "󰑐", ["re"]),
    # 模型
    Command("models", "模型列表", "Ctrl+M", CommandCategory.MODEL, "󰚩", ["m"]),
    Command("stream", "切换流式输出", "", CommandCategory.MODEL, "󰦕", []),
    Command("think", "切换深度思考", "", CommandCategory.MODEL, "󰠮", []),
    Command("parallel", "切换并行执行", "", CommandCategory.MODEL, "󰕇", []),
    # 显示
    Command("themes", "主题列表", "Ctrl+T", CommandCategory.DISPLAY, "󰏘", ["t"]),
    Command("sidebar", "切换侧边栏", "Ctrl+B", CommandCategory.DISPLAY, "󰕰", ["sb"]),
    # 工具
    Command("tools", "显示可用工具", "", CommandCategory.TOOLS, "󰦛", []),
    Command("tree", "显示目录结构", "", CommandCategory.TOOLS, "󰙅", []),
    Command("map", "显示代码库概览", "", CommandCategory.TOOLS, "󰆧", []),
    Command("find", "搜索相关文件", "", CommandCategory.TOOLS, "󰍉", ["search"]),
    # 调试
    Command("config", "显示当前配置", "", CommandCategory.DEBUG, "󰒓", ["cfg"]),
    Command("status", "显示系统状态", "", CommandCategory.DEBUG, "󰋼", ["st"]),
    Command("tokens", "显示 Token 使用", "", CommandCategory.DEBUG, "󰆼", []),
    Command("plugins", "显示已加载插件", "", CommandCategory.DEBUG, "󰐱", []),
    Command("compact", "压缩对话历史", "", CommandCategory.DEBUG, "󰗜", []),
    Command("copy", "复制最后回复", "", CommandCategory.DEBUG, "󰆏", ["cp"]),
]


def fuzzy_match(query: str, text: str) -> Tuple[bool, int]:
    """模糊匹配算法

    返回: (是否匹配, 匹配分数)
    分数越高越好
    """
    if not query:
        return True, 0

    query = query.lower()
    text = text.lower()

    # 完全匹配
    if query == text:
        return True, 1000

    # 前缀匹配
    if text.startswith(query):
        return True, 900 + (len(query) / len(text)) * 100

    # 包含匹配
    if query in text:
        # 位置越靠前分数越高
        pos = text.find(query)
        return True, 800 - pos * 10 + (len(query) / len(text)) * 50

    # 子序列匹配
    query_idx = 0
    score = 0
    consecutive = 0
    last_match_idx = -2

    for i, char in enumerate(text):
        if query_idx < len(query) and char == query[query_idx]:
            # 连续匹配加分
            if i == last_match_idx + 1:
                consecutive += 1
                score += consecutive * 10
            else:
                consecutive = 0
                score += 5

            # 单词开头匹配加分
            if i == 0 or text[i - 1] in " -_":
                score += 20

            last_match_idx = i
            query_idx += 1

    if query_idx == len(query):
        # 匹配完成，根据匹配比例调整分数
        return True, score + (len(query) / len(text)) * 50

    return False, 0


def search_commands(
    query: str,
    commands: List[Command],
    limit: int = 20,
) -> List[Tuple[Command, int]]:
    """搜索命令

    返回: [(命令, 分数), ...]
    """
    if not query:
        return [(cmd, 0) for cmd in commands[:limit]]

    results = []
    for cmd in commands:
        # 搜索命令名
        matched, score = fuzzy_match(query, cmd.name)
        if matched and score > 0:
            results.append((cmd, score + 100))  # 命令名匹配加权
            continue

        # 搜索别名
        for alias in cmd.aliases:
            matched, score = fuzzy_match(query, alias)
            if matched and score > 0:
                results.append((cmd, score + 80))  # 别名匹配加权
                break
        else:
            # 搜索描述
            matched, score = fuzzy_match(query, cmd.description)
            if matched and score > 0:
                results.append((cmd, score))

    # 按分数排序
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


class CommandPalette(ModalScreen):
    """增强版命令面板"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    CommandPalette {
        align: center top;
        padding-top: 3;
    }

    CommandPalette > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 0;
    }

    CommandPalette .palette-header {
        width: 100%;
        height: 1;
        background: $primary 20%;
        padding: 0 1;
        color: $text;
    }

    CommandPalette Input {
        width: 100%;
        border: none;
        background: $surface;
        padding: 0 1;
    }

    CommandPalette Input:focus {
        border: none;
    }

    CommandPalette .command-list {
        width: 100%;
        height: auto;
        max-height: 25;
        padding: 0;
    }

    CommandPalette .category-header {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-style: bold;
    }

    CommandPalette .cmd-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    CommandPalette .cmd-item:hover {
        background: $primary 30%;
    }

    CommandPalette .cmd-item.selected {
        background: $primary 40%;
    }

    CommandPalette .no-results {
        width: 100%;
        padding: 1;
        text-align: center;
        color: $text-muted;
    }

    CommandPalette .hint {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-align: center;
    }
    """

    def __init__(
        self,
        commands: Optional[List[Command]] = None,
        callback: Optional[Callable[[str], None]] = None,
        show_categories: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.commands = commands or DEFAULT_COMMANDS
        self.callback = callback
        self.show_categories = show_categories
        self.filtered_results: List[Tuple[Command, int]] = []
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰌌 命令面板", classes="palette-header")
            yield Input(placeholder="输入命令或搜索...", id="cmd-input")
            with ScrollableContainer(classes="command-list"):
                pass  # 动态填充
            yield Static("↑↓ 导航  Enter 执行  Esc 关闭", classes="hint")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()
        self._update_list("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "cmd-input":
            return
        self._update_list(event.value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd-input":
            return
        self._execute_selected()

    def on_key(self, event) -> None:
        if event.key == "down":
            self._move_selection(1)
            event.prevent_default()
        elif event.key == "up":
            self._move_selection(-1)
            event.prevent_default()
        elif event.key == "enter":
            self._execute_selected()
            event.prevent_default()

    def _update_list(self, query: str) -> None:
        """更新命令列表"""
        self.filtered_results = search_commands(query, self.commands)
        self.selected_index = 0

        command_list = self.query_one(".command-list")
        # 清空
        for child in list(command_list.children):
            child.remove()

        if not self.filtered_results:
            command_list.mount(Static("无匹配命令", classes="no-results"))
            return

        # 按分类分组（仅在无搜索时）
        if not query and self.show_categories:
            self._render_grouped(command_list)
        else:
            self._render_flat(command_list)

    def _render_flat(self, container) -> None:
        """平铺渲染"""
        for i, (cmd, score) in enumerate(self.filtered_results):
            classes = "cmd-item selected" if i == 0 else "cmd-item"
            container.mount(
                Static(
                    self._format_cmd(cmd),
                    classes=classes,
                    id=f"cmd-{cmd.name}",
                )
            )

    def _render_grouped(self, container) -> None:
        """分组渲染"""
        current_category = None
        item_index = 0

        for cmd, score in self.filtered_results:
            if cmd.category != current_category:
                current_category = cmd.category
                category_name = self._get_category_name(current_category)
                container.mount(
                    Static(category_name, classes="category-header")
                )

            classes = "cmd-item selected" if item_index == 0 else "cmd-item"
            container.mount(
                Static(
                    self._format_cmd(cmd),
                    classes=classes,
                    id=f"cmd-{cmd.name}",
                )
            )
            item_index += 1

    def _format_cmd(self, cmd: Command) -> Text:
        """格式化命令显示"""
        text = Text()
        if cmd.icon:
            text.append(f"{cmd.icon} ", style="cyan")
        text.append(f"/{cmd.name}", style="bold cyan")
        text.append(f"  {cmd.description}", style="dim")
        if cmd.shortcut:
            text.append(f"  [{cmd.shortcut}]", style="yellow dim")
        return text

    def _get_category_name(self, category: CommandCategory) -> str:
        """获取分类显示名"""
        names = {
            CommandCategory.GENERAL: "── 通用 ──",
            CommandCategory.SESSION: "── 会话 ──",
            CommandCategory.MODEL: "── 模型 ──",
            CommandCategory.DISPLAY: "── 显示 ──",
            CommandCategory.TOOLS: "── 工具 ──",
            CommandCategory.DEBUG: "── 调试 ──",
        }
        return names.get(category, "── 其他 ──")

    def _move_selection(self, delta: int) -> None:
        """移动选择"""
        if not self.filtered_results:
            return

        new_index = self.selected_index + delta
        new_index = max(0, min(new_index, len(self.filtered_results) - 1))

        if new_index != self.selected_index:
            self.selected_index = new_index
            self._update_selection()

    def _update_selection(self) -> None:
        """更新选中状态"""
        items = list(self.query(".cmd-item"))
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
            else:
                item.remove_class("selected")

    def _execute_selected(self) -> None:
        """执行选中的命令"""
        if not self.filtered_results:
            return

        cmd, _ = self.filtered_results[self.selected_index]
        if self.callback:
            self.callback(cmd.name)
        self.dismiss(cmd.name)


class QuickModelSelector(ModalScreen):
    """快速模型选择器 - 集成 Provider 系统"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]

    DEFAULT_CSS = """
    QuickModelSelector {
        align: center top;
        padding-top: 5;
    }

    QuickModelSelector > Vertical {
        width: 60;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: solid $primary;
        padding: 0;
    }

    QuickModelSelector .selector-header {
        width: 100%;
        height: 1;
        background: $primary 20%;
        padding: 0 1;
        color: $text;
    }

    QuickModelSelector Input {
        width: 100%;
        border: none;
        background: $surface;
        padding: 0 1;
    }

    QuickModelSelector .model-list {
        width: 100%;
        height: auto;
        max-height: 20;
        padding: 0;
    }

    QuickModelSelector .provider-header {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-style: bold;
    }

    QuickModelSelector .model-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    QuickModelSelector .model-item:hover {
        background: $primary 30%;
    }

    QuickModelSelector .model-item.selected {
        background: $primary 40%;
    }

    QuickModelSelector .model-item.current {
        color: $success;
    }
    """

    # Provider 图标映射
    PROVIDER_ICONS = {
        "anthropic": "󰚩",
        "openai": "󰧑",
        "gemini": "󰊭",
        "deepseek": "󰊤",
        "qwen": "󰮯",
        "zhipu": "󰮯",
        "minimax": "󰮯",
        "ollama": "󰆧",
    }

    def __init__(
        self,
        current_model: str = "",
        callback: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.current_model = current_model
        self.callback = callback
        self.models: List[Tuple[str, str, str]] = []  # (provider, model, display)
        self.filtered_models: List[Tuple[str, str, str]] = []
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("󰚩 选择模型", classes="selector-header")
            yield Input(placeholder="搜索模型...", id="model-input")
            with ScrollableContainer(classes="model-list"):
                pass

    def on_mount(self) -> None:
        self._load_models()
        self.query_one("#model-input", Input).focus()
        self._update_list("")

    def _load_models(self) -> None:
        """从 Provider 系统加载模型"""
        try:
            from ..llm.providers import PROVIDER_CONFIGS
        except ImportError:
            # 回退到默认列表
            self.models = [
                ("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4"),
                ("anthropic", "claude-opus-4-20250514", "Claude Opus 4"),
                ("openai", "gpt-4o", "GPT-4o"),
                ("openai", "gpt-4o-mini", "GPT-4o Mini"),
                ("deepseek", "deepseek-chat", "DeepSeek Chat"),
            ]
            return

        self.models = []
        for provider_name, config in PROVIDER_CONFIGS.items():
            for model in config.models:
                display = f"{model}"
                self.models.append((provider_name, model, display))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "model-input":
            return
        self._update_list(event.value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "model-input":
            return
        self._execute_selected()

    def on_key(self, event) -> None:
        if event.key == "down":
            self._move_selection(1)
            event.prevent_default()
        elif event.key == "up":
            self._move_selection(-1)
            event.prevent_default()

    def _update_list(self, query: str) -> None:
        """更新模型列表"""
        if query:
            query_lower = query.lower()
            self.filtered_models = [
                m for m in self.models
                if query_lower in m[1].lower() or query_lower in m[0].lower()
            ]
        else:
            self.filtered_models = self.models.copy()

        self.selected_index = 0

        model_list = self.query_one(".model-list")
        for child in list(model_list.children):
            child.remove()

        if not self.filtered_models:
            model_list.mount(Static("无匹配模型", classes="no-results"))
            return

        # 按 provider 分组
        current_provider = None
        for i, (provider, model, display) in enumerate(self.filtered_models):
            if provider != current_provider:
                current_provider = provider
                icon = self.PROVIDER_ICONS.get(provider, "󰮯")
                model_list.mount(
                    Static(f"{icon} {provider.upper()}", classes="provider-header")
                )

            is_current = model == self.current_model
            classes = "model-item"
            if i == 0:
                classes += " selected"
            if is_current:
                classes += " current"

            text = Text()
            text.append(f"  {display}", style="bold" if is_current else "")
            if is_current:
                text.append(" ✓", style="green")

            model_list.mount(
                Static(text, classes=classes, id=f"model-{i}")
            )

    def _move_selection(self, delta: int) -> None:
        if not self.filtered_models:
            return

        new_index = self.selected_index + delta
        new_index = max(0, min(new_index, len(self.filtered_models) - 1))

        if new_index != self.selected_index:
            self.selected_index = new_index
            self._update_selection()

    def _update_selection(self) -> None:
        items = list(self.query(".model-item"))
        for i, item in enumerate(items):
            if i == self.selected_index:
                item.add_class("selected")
            else:
                item.remove_class("selected")

    def _execute_selected(self) -> None:
        if not self.filtered_models:
            return

        provider, model, _ = self.filtered_models[self.selected_index]
        if self.callback:
            self.callback(provider, model)
        self.dismiss((provider, model))
