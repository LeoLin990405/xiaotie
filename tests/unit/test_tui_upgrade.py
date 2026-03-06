import json
from pathlib import Path

import pytest

from xiaotie.tui.app import XiaoTieApp
from xiaotie.tui.command_palette import CommandPalette
from xiaotie.tui.onboarding import OnboardingWizard
from xiaotie.tui.themes import ThemeManager
from xiaotie.tui.widgets import ChatMessage, MessageList


class TestTUIUpgrade:
    @pytest.mark.asyncio
    async def test_command_palette_switched_to_enhanced(self):
        app = XiaoTieApp()
        async with app.run_test() as pilot:
            app.action_command_palette()
            await pilot.pause()
            assert isinstance(app.screen_stack[-1], CommandPalette)

    @pytest.mark.asyncio
    async def test_message_list_has_history_cap(self):
        app = XiaoTieApp()
        async with app.run_test() as pilot:
            message_list = app.query_one("#messages-pane", MessageList)
            for i in range(220):
                message_list.add_message("assistant", f"msg-{i}")
            await pilot.pause()
            assert len(list(message_list.query(ChatMessage))) <= 200

    def test_theme_persistence(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ThemeManager._instance = None
        manager = ThemeManager.get_instance()
        assert manager.set_theme("nord")
        ThemeManager._instance = None
        manager2 = ThemeManager.get_instance()
        assert manager2.get_current_theme() == "nord"

    def test_risky_intent_classification(self):
        app = XiaoTieApp()
        assert app._classify_risky_intent("reset")[0] is True
        assert app._classify_risky_intent("quit")[0] is True
        assert app._classify_risky_intent("help")[0] is False

    def test_risky_action_logging(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        app = XiaoTieApp()
        app._log_risky_action("reset", "清空上下文", "executed")
        lines = app._risk_log_path.read_text(encoding="utf-8").strip().splitlines()
        data = json.loads(lines[-1])
        assert data["command"] == "reset"
        assert data["intent"] == "清空上下文"
        assert data["status"] == "executed"

    @pytest.mark.asyncio
    async def test_onboarding_required_opens_wizard(self):
        app = XiaoTieApp(show_onboarding=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert any(isinstance(screen, OnboardingWizard) for screen in app.screen_stack)
