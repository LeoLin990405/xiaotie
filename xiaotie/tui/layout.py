"""布局组件

参考 OpenCode 的布局设计：
- SplitPane: 可调整大小的分割面板
- Container: 带边框的容器
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class SplitPane(Horizontal):
    """分割面板 - 左右布局"""

    DEFAULT_CSS = """
    SplitPane {
        width: 100%;
        height: 100%;
    }

    SplitPane > .split-left {
        width: 1fr;
        height: 100%;
    }

    SplitPane > .split-right {
        width: auto;
        min-width: 0;
        height: 100%;
    }

    SplitPane > .split-right.collapsed {
        width: 0;
        display: none;
    }

    SplitPane > .split-divider {
        width: 1;
        height: 100%;
        background: $surface-darken-1;
    }
    """

    sidebar_visible = reactive(True)

    def __init__(
        self,
        left_content: ComposeResult = None,
        right_content: ComposeResult = None,
        right_width: int = 30,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._left_content = left_content
        self._right_content = right_content
        self._right_width = right_width

    def compose(self) -> ComposeResult:
        with Container(classes="split-left"):
            if self._left_content:
                yield from self._left_content
        yield Static("", classes="split-divider")
        with Container(classes="split-right"):
            if self._right_content:
                yield from self._right_content

    def watch_sidebar_visible(self, visible: bool) -> None:
        right = self.query_one(".split-right")
        divider = self.query_one(".split-divider")
        if visible:
            right.remove_class("collapsed")
            right.styles.width = self._right_width
            divider.styles.display = "block"
        else:
            right.add_class("collapsed")
            divider.styles.display = "none"

    def toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible


class BorderedContainer(Container):
    """带边框的容器"""

    DEFAULT_CSS = """
    BorderedContainer {
        border: round $surface-lighten-1;
        padding: 0;
    }

    BorderedContainer > .container-title {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
        text-style: bold;
        color: $text-muted;
    }

    BorderedContainer > .container-content {
        width: 100%;
        height: 1fr;
    }
    """

    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        if self._title:
            yield Static(self._title, classes="container-title")
        yield Container(classes="container-content")


class Panel(Container):
    """面板组件 - 带标题和边框"""

    DEFAULT_CSS = """
    Panel {
        width: 100%;
        height: auto;
        border: solid $surface-lighten-1;
        background: $surface;
    }

    Panel > .panel-header {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface-darken-1;
        padding: 0 1;
    }

    Panel > .panel-header .panel-title {
        text-style: bold;
    }

    Panel > .panel-header .panel-actions {
        dock: right;
    }

    Panel > .panel-body {
        width: 100%;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        with Horizontal(classes="panel-header"):
            yield Static(self._title, classes="panel-title")
            yield Static("", classes="panel-actions")
        yield Container(classes="panel-body")
