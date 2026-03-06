import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from xiaotie.tui.app import RiskConfirmScreen, ThemeSelectorScreen, XiaoTieApp
from xiaotie.tui.onboarding import OnboardingWizard


class DummyApp(App):
    def compose(self) -> ComposeResult:
        yield Static("dummy")


class TestGuidedFlowIntegration:
    @pytest.mark.asyncio
    async def test_onboarding_skip_flow(self):
        app = XiaoTieApp(show_onboarding=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert any(isinstance(screen, OnboardingWizard) for screen in app.screen_stack)
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert app.onboarding_result is not None
            assert app.onboarding_result.get("skipped") is True

    @pytest.mark.asyncio
    async def test_theme_preview_updates_selection(self):
        app = DummyApp()
        selected = {"theme": None}

        def on_preview(theme: str):
            selected["theme"] = theme

        async with app.run_test() as pilot:
            screen = ThemeSelectorScreen(current_theme="default", preview_callback=on_preview)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert selected["theme"] is not None

    @pytest.mark.asyncio
    async def test_risk_confirm_requires_confirm_input(self):
        app = DummyApp()
        result = {"ok": False}

        def on_result(confirmed):
            result["ok"] = bool(confirmed)

        async with app.run_test() as pilot:
            app.push_screen(RiskConfirmScreen(command="reset", intent="清空上下文", cooldown_seconds=0), on_result)
            await pilot.pause()
            await pilot.press("C", "O", "N", "F", "I", "R", "M")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert result["ok"] is True
