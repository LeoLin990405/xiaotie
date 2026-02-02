"""流式渲染组件

优化 LLM 响应的实时显示：
- StreamingMessage: 支持增量更新的消息组件
- StreamingRenderer: 流式渲染管理器
- 防抖动更新机制
- 平滑滚动
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


@dataclass
class StreamingState:
    """流式渲染状态"""

    thinking: str = ""
    content: str = ""
    is_thinking: bool = False
    is_streaming: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tokens_per_second: float = 0.0
    total_tokens: int = 0

    def reset(self) -> None:
        """重置状态"""
        self.thinking = ""
        self.content = ""
        self.is_thinking = False
        self.is_streaming = False
        self.start_time = None
        self.end_time = None
        self.tokens_per_second = 0.0
        self.total_tokens = 0


class StreamingMessage(Widget):
    """流式消息组件 - 支持增量更新"""

    DEFAULT_CSS = """
    StreamingMessage {
        width: 100%;
        height: auto;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
        border-left: thick $success;
    }

    StreamingMessage .msg-header {
        height: 1;
        margin-bottom: 1;
    }

    StreamingMessage .msg-role {
        text-style: bold;
        color: $success;
    }

    StreamingMessage .msg-time {
        color: $text-muted;
        text-style: dim;
    }

    StreamingMessage .msg-stats {
        color: $text-muted;
        text-style: dim;
        margin-left: 2;
    }

    StreamingMessage .msg-content {
        width: 100%;
    }

    StreamingMessage .msg-thinking {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
        padding: 0 1;
        border-left: solid $secondary;
    }

    StreamingMessage .msg-cursor {
        color: $primary;
    }

    StreamingMessage.streaming {
        border-left: thick $warning;
    }

    StreamingMessage.streaming .msg-role {
        color: $warning;
    }
    """

    # 响应式属性
    content = reactive("", layout=True)
    thinking = reactive("", layout=True)
    is_streaming = reactive(False)
    tokens_per_second = reactive(0.0)

    class Completed(Message):
        """流式完成消息"""

        def __init__(self, content: str, thinking: str) -> None:
            self.content = content
            self.thinking = thinking
            super().__init__()

    def __init__(
        self,
        timestamp: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.timestamp = timestamp or datetime.now()
        self._content_widget: Optional[Static] = None
        self._thinking_widget: Optional[Static] = None
        self._stats_widget: Optional[Static] = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="msg-header"):
            yield Static("󰚩 小铁", classes="msg-role")
            yield Static(f"  {self.timestamp.strftime('%H:%M:%S')}", classes="msg-time")
            yield Static("", classes="msg-stats", id="stream-stats")

        yield Static("", classes="msg-content", id="stream-content")
        yield Static("", classes="msg-thinking", id="stream-thinking")

    def on_mount(self) -> None:
        self._content_widget = self.query_one("#stream-content", Static)
        self._thinking_widget = self.query_one("#stream-thinking", Static)
        self._stats_widget = self.query_one("#stream-stats", Static)
        self._thinking_widget.display = False

    def watch_content(self, value: str) -> None:
        """内容变化时更新显示"""
        if self._content_widget is None:
            return

        if value:
            if self.is_streaming:
                # 流式模式：显示原始文本 + 光标
                display_text = Text()
                display_text.append(value)
                display_text.append("▌", style="bold blink")
                self._content_widget.update(display_text)
            else:
                # 完成模式：渲染 Markdown
                self._content_widget.update(Markdown(value))
        else:
            self._content_widget.update("")

    def watch_thinking(self, value: str) -> None:
        """思考内容变化时更新显示"""
        if self._thinking_widget is None:
            return

        if value:
            # 只显示前 300 字符
            preview = value[:300]
            if len(value) > 300:
                preview += "..."
            self._thinking_widget.update(f"󰔚 {preview}")
            self._thinking_widget.display = True
        else:
            self._thinking_widget.display = False

    def watch_is_streaming(self, value: bool) -> None:
        """流式状态变化"""
        if value:
            self.add_class("streaming")
        else:
            self.remove_class("streaming")
            # 重新渲染为 Markdown
            if self._content_widget and self.content:
                self._content_widget.update(Markdown(self.content))

    def watch_tokens_per_second(self, value: float) -> None:
        """更新速度统计"""
        if self._stats_widget is None:
            return

        if value > 0 and self.is_streaming:
            self._stats_widget.update(f"  {value:.1f} tok/s")
        else:
            self._stats_widget.update("")

    def append_content(self, text: str) -> None:
        """追加内容"""
        self.content += text

    def append_thinking(self, text: str) -> None:
        """追加思考内容"""
        self.thinking += text

    def finish(self) -> None:
        """完成流式输出"""
        self.is_streaming = False
        self.tokens_per_second = 0.0
        self.post_message(self.Completed(self.content, self.thinking))


class StreamingRenderer:
    """流式渲染管理器

    功能：
    - 管理流式消息的生命周期
    - 防抖动更新（避免过于频繁的 UI 更新）
    - 速度统计
    - 平滑滚动
    """

    def __init__(
        self,
        message_widget: StreamingMessage,
        scroll_callback: Optional[Callable[[], None]] = None,
        update_interval: float = 0.05,  # 50ms 更新间隔
    ):
        self.widget = message_widget
        self.scroll_callback = scroll_callback
        self.update_interval = update_interval

        self._state = StreamingState()
        self._pending_content = ""
        self._pending_thinking = ""
        self._update_task: Optional[asyncio.Task] = None
        self._token_count = 0
        self._last_token_time: Optional[float] = None

    async def start(self) -> None:
        """开始流式渲染"""
        self._state.reset()
        self._state.is_streaming = True
        self._state.start_time = datetime.now()
        self._pending_content = ""
        self._pending_thinking = ""
        self._token_count = 0
        self._last_token_time = None

        self.widget.content = ""
        self.widget.thinking = ""
        self.widget.is_streaming = True

        # 启动更新任务
        self._update_task = asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        """停止流式渲染"""
        self._state.is_streaming = False
        self._state.end_time = datetime.now()

        # 停止更新任务
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

        # 刷新剩余内容
        await self._flush()

        # 完成
        self.widget.finish()

    def on_thinking(self, text: str) -> None:
        """接收思考内容"""
        self._pending_thinking += text
        self._state.thinking += text
        self._state.is_thinking = True

    def on_content(self, text: str) -> None:
        """接收内容"""
        self._pending_content += text
        self._state.content += text
        self._state.is_thinking = False

        # 更新 token 统计
        self._token_count += len(text.split())
        current_time = asyncio.get_event_loop().time()
        if self._last_token_time is not None:
            elapsed = current_time - self._last_token_time
            if elapsed > 0:
                # 简单估算：每个词约 1.3 个 token
                tokens = len(text.split()) * 1.3
                self._state.tokens_per_second = tokens / elapsed
        self._last_token_time = current_time

    async def _update_loop(self) -> None:
        """定期更新 UI"""
        while self._state.is_streaming:
            await self._flush()
            await asyncio.sleep(self.update_interval)

    async def _flush(self) -> None:
        """刷新待更新内容到 UI"""
        if self._pending_content:
            self.widget.content = self._state.content
            self._pending_content = ""

        if self._pending_thinking:
            self.widget.thinking = self._state.thinking
            self._pending_thinking = ""

        # 更新速度
        self.widget.tokens_per_second = self._state.tokens_per_second

        # 滚动
        if self.scroll_callback:
            self.scroll_callback()


class ThinkingProgress(Static):
    """思考进度指示器 - 增强版"""

    DEFAULT_CSS = """
    ThinkingProgress {
        width: 100%;
        height: auto;
        min-height: 2;
        padding: 0 2;
        background: $surface-darken-1;
        border-left: thick $secondary;
        color: $text-muted;
    }

    ThinkingProgress .progress-header {
        height: 1;
    }

    ThinkingProgress .progress-spinner {
        color: $secondary;
    }

    ThinkingProgress .progress-text {
        color: $text-muted;
    }

    ThinkingProgress .progress-preview {
        color: $text-muted;
        text-style: italic dim;
        height: auto;
        max-height: 3;
        overflow: hidden;
    }
    """

    thinking_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._frame_idx = 0

    def compose(self) -> ComposeResult:
        with Horizontal(classes="progress-header"):
            yield Static("⠋", classes="progress-spinner", id="spinner")
            yield Static(" 思考中...", classes="progress-text")
        yield Static("", classes="progress-preview", id="preview")

    def on_mount(self) -> None:
        self.set_interval(0.1, self._animate)

    def _animate(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        spinner = self.query_one("#spinner", Static)
        spinner.update(self._frames[self._frame_idx])

    def watch_thinking_text(self, value: str) -> None:
        """更新思考预览"""
        preview = self.query_one("#preview", Static)
        if value:
            # 显示最后 100 字符
            text = value[-100:] if len(value) > 100 else value
            if len(value) > 100:
                text = "..." + text
            preview.update(text)
        else:
            preview.update("")

    def append(self, text: str) -> None:
        """追加思考内容"""
        self.thinking_text += text
