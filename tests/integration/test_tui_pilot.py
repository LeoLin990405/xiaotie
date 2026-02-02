"""TUI 交互测试 - 使用 Textual Pilot

测试 TUI 组件的交互行为：
- 命令面板打开/关闭
- 模糊搜索
- 键盘导航
- 主题切换
"""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from xiaotie.tui.command_palette import (
    Command,
    CommandCategory,
    CommandPalette,
    DEFAULT_COMMANDS,
    QuickModelSelector,
    fuzzy_match,
    search_commands,
)


class DummyApp(App):
    """测试用 App"""

    def compose(self) -> ComposeResult:
        yield Static("Test App")


class TestCommandPaletteTUI:
    """Command Palette TUI 测试"""

    @pytest.mark.asyncio
    async def test_palette_opens_in_app(self):
        """测试命令面板在 App 中打开"""
        app = DummyApp()
        async with app.run_test() as pilot:
            # 推送命令面板
            palette = CommandPalette()
            app.push_screen(palette)
            await pilot.pause()

            # 验证面板在屏幕栈中
            assert len(app.screen_stack) > 1
            assert isinstance(app.screen_stack[-1], CommandPalette)

    @pytest.mark.asyncio
    async def test_palette_closes_on_escape(self):
        """测试 ESC 关闭面板"""
        app = DummyApp()
        async with app.run_test() as pilot:
            palette = CommandPalette()
            app.push_screen(palette)
            await pilot.pause()

            initial_stack_size = len(app.screen_stack)

            # 按 ESC
            await pilot.press("escape")
            await pilot.pause()

            # 面板应该被关闭
            assert len(app.screen_stack) < initial_stack_size

    @pytest.mark.asyncio
    async def test_arrow_navigation(self):
        """测试方向键导航"""
        app = DummyApp()
        async with app.run_test() as pilot:
            palette = CommandPalette()
            app.push_screen(palette)
            await pilot.pause()

            initial_index = palette.selected_index

            # 按下键
            await pilot.press("down")
            await pilot.pause()
            assert palette.selected_index == initial_index + 1

            # 按上键
            await pilot.press("up")
            await pilot.pause()
            assert palette.selected_index == initial_index

    @pytest.mark.asyncio
    async def test_enter_executes_command(self):
        """测试 Enter 执行命令"""
        executed_command = None

        def callback(cmd):
            nonlocal executed_command
            executed_command = cmd

        app = DummyApp()
        async with app.run_test() as pilot:
            palette = CommandPalette(callback=callback)
            app.push_screen(palette)
            await pilot.pause()

            # 直接按 Enter 执行第一个命令
            await pilot.press("enter")
            await pilot.pause()

            # 验证回调被调用
            assert executed_command is not None


class TestQuickModelSelectorTUI:
    """Quick Model Selector TUI 测试"""

    @pytest.mark.asyncio
    async def test_selector_opens(self):
        """测试模型选择器打开"""
        app = DummyApp()
        async with app.run_test() as pilot:
            selector = QuickModelSelector()
            app.push_screen(selector)
            await pilot.pause()

            # 验证选择器在屏幕栈中
            assert len(app.screen_stack) > 1
            assert isinstance(app.screen_stack[-1], QuickModelSelector)

    @pytest.mark.asyncio
    async def test_selector_shows_models(self):
        """测试显示模型列表"""
        app = DummyApp()
        async with app.run_test() as pilot:
            selector = QuickModelSelector()
            app.push_screen(selector)
            await pilot.pause()

            # 验证有模型加载
            assert len(selector.models) > 0

    @pytest.mark.asyncio
    async def test_selector_highlights_current(self):
        """测试高亮当前模型"""
        current = "gpt-4o"
        app = DummyApp()
        async with app.run_test() as pilot:
            selector = QuickModelSelector(current_model=current)
            app.push_screen(selector)
            await pilot.pause()

            assert selector.current_model == current


class TestCommandPaletteIntegration:
    """Command Palette 集成测试"""

    @pytest.mark.asyncio
    async def test_custom_commands(self):
        """测试自定义命令列表"""
        custom_commands = [
            Command("custom1", "自定义命令1", category=CommandCategory.GENERAL),
            Command("custom2", "自定义命令2", category=CommandCategory.TOOLS),
        ]

        app = DummyApp()
        async with app.run_test() as pilot:
            palette = CommandPalette(commands=custom_commands)
            app.push_screen(palette)
            await pilot.pause()

            assert len(palette.commands) == 2
            assert palette.commands[0].name == "custom1"

    @pytest.mark.asyncio
    async def test_filtered_results_initialized(self):
        """测试过滤结果初始化"""
        app = DummyApp()
        async with app.run_test() as pilot:
            palette = CommandPalette()
            app.push_screen(palette)
            await pilot.pause()

            # 初始时应该有所有命令
            assert len(palette.filtered_results) > 0


class TestFuzzyMatchAlgorithm:
    """模糊匹配算法测试 (非 TUI)"""

    def test_exact_match_highest_score(self):
        """精确匹配应该有最高分"""
        _, exact_score = fuzzy_match("help", "help")
        _, prefix_score = fuzzy_match("hel", "help")
        _, contains_score = fuzzy_match("elp", "help")

        assert exact_score > prefix_score > contains_score

    def test_search_returns_sorted_results(self):
        """搜索结果应该按分数排序"""
        results = search_commands("h", DEFAULT_COMMANDS)
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_by_name(self):
        """测试按名称搜索"""
        results = search_commands("help", DEFAULT_COMMANDS)
        assert len(results) > 0
        assert results[0][0].name == "help"

    def test_search_by_alias(self):
        """测试按别名搜索"""
        results = search_commands("q", DEFAULT_COMMANDS)
        names = [r[0].name for r in results]
        assert "quit" in names

    def test_search_empty_query(self):
        """测试空查询返回所有命令"""
        results = search_commands("", DEFAULT_COMMANDS)
        assert len(results) == min(20, len(DEFAULT_COMMANDS))

    def test_search_no_match(self):
        """测试无匹配"""
        results = search_commands("xyzabc123", DEFAULT_COMMANDS)
        assert len(results) == 0
