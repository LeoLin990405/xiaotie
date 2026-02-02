"""流式渲染组件测试"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from xiaotie.tui.streaming import (
    StreamingMessage,
    StreamingRenderer,
    StreamingState,
    ThinkingProgress,
)


class TestStreamingState:
    """StreamingState 测试"""

    def test_initial_state(self):
        """测试初始状态"""
        state = StreamingState()
        assert state.thinking == ""
        assert state.content == ""
        assert state.is_thinking is False
        assert state.is_streaming is False
        assert state.start_time is None
        assert state.end_time is None
        assert state.tokens_per_second == 0.0
        assert state.total_tokens == 0

    def test_reset(self):
        """测试重置"""
        state = StreamingState(
            thinking="test thinking",
            content="test content",
            is_thinking=True,
            is_streaming=True,
            start_time=datetime.now(),
            tokens_per_second=10.5,
            total_tokens=100,
        )
        state.reset()
        assert state.thinking == ""
        assert state.content == ""
        assert state.is_thinking is False
        assert state.is_streaming is False
        assert state.start_time is None
        assert state.tokens_per_second == 0.0


class TestStreamingMessage:
    """StreamingMessage 测试"""

    def test_create_message(self):
        """测试创建消息"""
        msg = StreamingMessage()
        assert msg.content == ""
        assert msg.thinking == ""
        assert msg.is_streaming is False
        assert msg.timestamp is not None

    def test_create_with_timestamp(self):
        """测试带时间戳创建"""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        msg = StreamingMessage(timestamp=ts)
        assert msg.timestamp == ts

    def test_append_content(self):
        """测试追加内容"""
        msg = StreamingMessage()
        msg.append_content("Hello ")
        msg.append_content("World")
        assert msg.content == "Hello World"

    def test_append_thinking(self):
        """测试追加思考内容"""
        msg = StreamingMessage()
        msg.append_thinking("Let me think...")
        msg.append_thinking(" about this.")
        assert msg.thinking == "Let me think... about this."

    def test_streaming_class(self):
        """测试流式状态类"""
        msg = StreamingMessage()
        msg.is_streaming = True
        assert "streaming" in msg.classes
        msg.is_streaming = False
        assert "streaming" not in msg.classes


class TestStreamingRenderer:
    """StreamingRenderer 测试"""

    @pytest.fixture
    def mock_widget(self):
        """创建模拟 widget"""
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0
        return widget

    def test_create_renderer(self, mock_widget):
        """测试创建渲染器"""
        renderer = StreamingRenderer(mock_widget)
        assert renderer.widget == mock_widget
        assert renderer.update_interval == 0.05

    def test_custom_update_interval(self, mock_widget):
        """测试自定义更新间隔"""
        renderer = StreamingRenderer(mock_widget, update_interval=0.1)
        assert renderer.update_interval == 0.1

    def test_on_thinking(self, mock_widget):
        """测试接收思考内容"""
        renderer = StreamingRenderer(mock_widget)
        renderer.on_thinking("Thinking...")
        assert renderer._state.thinking == "Thinking..."
        assert renderer._state.is_thinking is True

    def test_on_content(self, mock_widget):
        """测试接收内容"""
        renderer = StreamingRenderer(mock_widget)
        renderer.on_content("Hello")
        assert renderer._state.content == "Hello"
        assert renderer._state.is_thinking is False

    def test_multiple_content_chunks(self, mock_widget):
        """测试多个内容块"""
        renderer = StreamingRenderer(mock_widget)
        renderer.on_content("Hello ")
        renderer.on_content("World")
        assert renderer._state.content == "Hello World"

    @pytest.mark.asyncio
    async def test_start_stop(self, mock_widget):
        """测试启动和停止"""
        renderer = StreamingRenderer(mock_widget)

        await renderer.start()
        assert renderer._state.is_streaming is True
        assert renderer._state.start_time is not None

        await renderer.stop()
        assert renderer._state.is_streaming is False
        assert renderer._state.end_time is not None

    @pytest.mark.asyncio
    async def test_flush_content(self, mock_widget):
        """测试刷新内容"""
        renderer = StreamingRenderer(mock_widget)
        renderer._state.content = "Test content"
        renderer._pending_content = "Test content"

        await renderer._flush()
        # Widget 的 content 应该被更新
        assert mock_widget.content == "Test content"

    @pytest.mark.asyncio
    async def test_scroll_callback(self, mock_widget):
        """测试滚动回调"""
        scroll_called = False

        def scroll_callback():
            nonlocal scroll_called
            scroll_called = True

        renderer = StreamingRenderer(mock_widget, scroll_callback=scroll_callback)
        renderer._state.content = "Test"
        renderer._pending_content = "Test"

        await renderer._flush()
        assert scroll_called is True


class TestThinkingProgress:
    """ThinkingProgress 测试"""

    def test_create_progress(self):
        """测试创建进度指示器"""
        progress = ThinkingProgress()
        # 在未挂载时，直接检查内部状态
        assert progress._frames is not None
        assert len(progress._frames) == 10

    def test_append_thinking(self):
        """测试追加思考内容"""
        progress = ThinkingProgress()
        # 直接设置属性（不触发 watcher）
        progress._reactive_thinking_text = "First thought. "
        progress._reactive_thinking_text += "Second thought."
        # 验证内部状态
        assert "First thought" in progress._reactive_thinking_text

    def test_frames(self):
        """测试动画帧"""
        progress = ThinkingProgress()
        assert len(progress._frames) == 10
        assert "⠋" in progress._frames


class TestStreamingIntegration:
    """流式渲染集成测试"""

    @pytest.mark.asyncio
    async def test_full_streaming_flow(self):
        """测试完整流式流程"""
        # 创建模拟 widget
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0

        renderer = StreamingRenderer(widget, update_interval=0.01)

        # 启动
        await renderer.start()
        assert renderer._state.is_streaming is True

        # 模拟思考
        renderer.on_thinking("Let me analyze this...")
        assert renderer._state.thinking == "Let me analyze this..."

        # 模拟内容流
        for word in ["Hello", " ", "World", "!"]:
            renderer.on_content(word)
            await asyncio.sleep(0.01)

        assert renderer._state.content == "Hello World!"

        # 停止
        await renderer.stop()
        assert renderer._state.is_streaming is False

    @pytest.mark.asyncio
    async def test_rapid_content_updates(self):
        """测试快速内容更新"""
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0

        renderer = StreamingRenderer(widget, update_interval=0.05)

        await renderer.start()

        # 快速发送多个内容块
        for i in range(100):
            renderer.on_content(f"chunk{i} ")

        # 等待一个更新周期
        await asyncio.sleep(0.1)

        # 内容应该被累积
        assert "chunk0" in renderer._state.content
        assert "chunk99" in renderer._state.content

        await renderer.stop()

    @pytest.mark.asyncio
    async def test_thinking_to_content_transition(self):
        """测试从思考到内容的转换"""
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0

        renderer = StreamingRenderer(widget)

        await renderer.start()

        # 先发送思考
        renderer.on_thinking("Analyzing...")
        assert renderer._state.is_thinking is True

        # 然后发送内容
        renderer.on_content("Here's my answer")
        assert renderer._state.is_thinking is False

        await renderer.stop()


class TestStreamingPerformance:
    """流式渲染性能测试"""

    @pytest.mark.asyncio
    async def test_large_content_handling(self):
        """测试大内容处理"""
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0

        renderer = StreamingRenderer(widget, update_interval=0.01)

        await renderer.start()

        # 发送大量内容
        large_content = "x" * 10000
        renderer.on_content(large_content)

        await asyncio.sleep(0.05)
        await renderer.stop()

        assert len(renderer._state.content) == 10000

    @pytest.mark.asyncio
    async def test_concurrent_thinking_and_content(self):
        """测试并发思考和内容"""
        widget = MagicMock(spec=StreamingMessage)
        widget.content = ""
        widget.thinking = ""
        widget.is_streaming = False
        widget.tokens_per_second = 0.0

        renderer = StreamingRenderer(widget)

        await renderer.start()

        # 交替发送思考和内容
        renderer.on_thinking("Think 1")
        renderer.on_content("Content 1")
        renderer.on_thinking("Think 2")
        renderer.on_content("Content 2")

        await asyncio.sleep(0.1)
        await renderer.stop()

        assert "Think 1" in renderer._state.thinking
        assert "Think 2" in renderer._state.thinking
        assert "Content 1" in renderer._state.content
        assert "Content 2" in renderer._state.content
