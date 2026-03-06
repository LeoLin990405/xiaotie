"""workflows/ 单元测试

Tests for dataclasses and workflow logic that can be tested without
external dependencies (proxy, automation engines).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.workflows.miniapp_capture import (
    AutomationEngine,
    ExportFormat,
    PageAction,
    MiniAppTarget,
    CaptureConfig,
    CaptureResult,
    MiniAppCaptureWorkflow,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestAutomationEngine:
    def test_values(self):
        assert AutomationEngine.MACOS.value == "macos"
        assert AutomationEngine.APPIUM.value == "appium"
        assert AutomationEngine.NONE.value == "none"


class TestExportFormat:
    def test_values(self):
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.HAR.value == "har"


class TestPageAction:
    def test_defaults(self):
        action = PageAction(action="scroll_down")
        assert action.params == {}
        assert action.delay == 1.0

    def test_custom(self):
        action = PageAction(action="click", params={"x": 100, "y": 200}, delay=0.5)
        assert action.params["x"] == 100
        assert action.delay == 0.5


class TestMiniAppTarget:
    def test_defaults(self):
        target = MiniAppTarget(name="Test App")
        assert target.app_id is None
        assert target.deeplink is None
        assert target.actions == []
        assert target.capture_duration == 30.0
        assert target.export_format == ExportFormat.JSON

    def test_custom(self):
        target = MiniAppTarget(
            name="Custom",
            app_id="wx123",
            capture_duration=60.0,
            export_format=ExportFormat.HAR,
        )
        assert target.app_id == "wx123"
        assert target.export_format == ExportFormat.HAR


class TestCaptureConfig:
    def test_defaults(self):
        cfg = CaptureConfig()
        assert cfg.proxy_port == 8080
        assert cfg.enable_https is True
        assert cfg.engine == AutomationEngine.NONE
        assert cfg.scroll_count == 5
        assert cfg.default_capture_duration == 30.0

    def test_custom(self):
        cfg = CaptureConfig(proxy_port=9090, engine=AutomationEngine.MACOS)
        assert cfg.proxy_port == 9090
        assert cfg.engine == AutomationEngine.MACOS


class TestCaptureResult:
    def test_success(self):
        r = CaptureResult(
            miniapp_name="Test",
            success=True,
            total_requests=100,
            miniapp_requests=42,
            duration_seconds=15.0,
        )
        assert r.success
        assert r.miniapp_requests == 42

    def test_failure(self):
        r = CaptureResult(
            miniapp_name="Fail",
            success=False,
            error="Connection refused",
        )
        assert not r.success
        assert r.error == "Connection refused"
        assert r.stats == {}


# ---------------------------------------------------------------------------
# MiniAppCaptureWorkflow
# ---------------------------------------------------------------------------


class TestMiniAppCaptureWorkflow:
    @pytest.fixture
    def workflow(self):
        config = CaptureConfig(proxy_port=18080, engine=AutomationEngine.NONE)
        logs = []
        wf = MiniAppCaptureWorkflow(config=config, on_progress=logs.append)
        wf._logs = logs
        return wf

    def test_init_defaults(self):
        wf = MiniAppCaptureWorkflow()
        assert wf.config.proxy_port == 8080
        assert wf._proxy is None
        assert wf._automation is None

    def test_init_custom_config(self, workflow):
        assert workflow.config.proxy_port == 18080

    def test_on_progress_callback(self, workflow):
        workflow._log("test message")
        assert "test message" in workflow._logs

    @pytest.mark.asyncio
    async def test_cleanup_when_nothing_running(self, workflow):
        await workflow.cleanup()
        assert workflow._proxy is None
        assert workflow._automation is None

    @pytest.mark.asyncio
    async def test_cleanup_stops_proxy(self, workflow):
        mock_proxy = MagicMock()
        mock_proxy.stop = AsyncMock()
        workflow._proxy = mock_proxy
        await workflow.cleanup()
        mock_proxy.stop.assert_awaited_once()
        assert workflow._proxy is None

    @pytest.mark.asyncio
    async def test_cleanup_stops_automation(self, workflow):
        workflow.config = CaptureConfig(engine=AutomationEngine.APPIUM)
        mock_auto = MagicMock()
        mock_auto.stop = AsyncMock()
        workflow._automation = mock_auto
        await workflow.cleanup()
        mock_auto.stop.assert_awaited_once()
        assert workflow._automation is None

    @pytest.mark.asyncio
    async def test_context_manager(self, workflow):
        async with workflow as wf:
            assert wf is workflow
        assert workflow._proxy is None

    @pytest.mark.asyncio
    async def test_capture_one_handles_error(self, workflow):
        """When proxy start fails, capture_one returns failure result."""
        with patch.object(workflow, "_start_proxy", side_effect=RuntimeError("no proxy")):
            target = MiniAppTarget(name="ErrorApp", capture_duration=0.1)
            result = await workflow.capture_one(target)
            assert not result.success
            assert "no proxy" in result.error

    @pytest.mark.asyncio
    async def test_log_summary(self, workflow):
        results = [
            CaptureResult(miniapp_name="App1", success=True, miniapp_requests=10, duration_seconds=5.0),
            CaptureResult(miniapp_name="App2", success=False, error="timeout", miniapp_requests=0, duration_seconds=3.0),
        ]
        workflow._log_summary(results)
        summary = workflow._logs[-1]
        assert "App1" in summary
        assert "App2" in summary
        assert "1/2" in summary

    @pytest.mark.asyncio
    async def test_wait_capture(self, workflow):
        """_wait_capture should not fail with a short duration."""
        mock_proxy = MagicMock()
        mock_proxy.storage = MagicMock()
        mock_proxy.storage.count = 5
        workflow._proxy = mock_proxy
        await workflow._wait_capture(0.1)

    @pytest.mark.asyncio
    async def test_execute_actions_default(self, workflow):
        """With no actions defined, uses default scroll actions."""
        workflow.config.scroll_count = 2
        workflow.config.action_delay = 0.01
        mock_auto = MagicMock()
        mock_auto.scroll_down = AsyncMock()
        workflow._automation = mock_auto

        target = MiniAppTarget(name="Test", actions=[])
        await workflow._execute_actions(target)

    @pytest.mark.asyncio
    async def test_do_action_wait(self, workflow):
        action = PageAction(action="wait", delay=0.01)
        await workflow._do_action(action)

    @pytest.mark.asyncio
    async def test_do_action_scroll(self, workflow):
        mock_auto = MagicMock()
        mock_auto.scroll_down = AsyncMock()
        workflow._automation = mock_auto
        action = PageAction(action="scroll_down", delay=0.01)
        await workflow._do_action(action)
        mock_auto.scroll_down.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_do_action_screenshot(self, workflow):
        mock_auto = MagicMock()
        mock_auto.screenshot = AsyncMock()
        workflow._automation = mock_auto
        action = PageAction(action="screenshot", params={"filename": "test.png"})
        await workflow._do_action(action)
        mock_auto.screenshot.assert_awaited_once()
