"""ToolExecutor 单元测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent.executor import ToolExecutor, ToolResult, _filter_sensitive_output, _summarize_arguments
from xiaotie.schema import FunctionCall, ToolCall
from xiaotie.schema import ToolResult as SchemaToolResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_tool(name="dummy", success=True, content="ok", error=None):
    tool = MagicMock()
    tool.name = name
    tool.__class__.__module__ = "xiaotie.tools"
    tool.to_schema.return_value = {
        "type": "function",
        "function": {"name": name, "description": "test", "parameters": {}},
    }
    tool.execute = AsyncMock(
        return_value=SchemaToolResult(success=success, content=content, error=error)
    )
    return tool


def _make_tool_call(tc_id="tc1", name="dummy", arguments=None):
    return ToolCall(
        id=tc_id,
        function=FunctionCall(name=name, arguments=arguments or {}),
    )


@pytest.fixture
def permission_manager():
    pm = MagicMock()
    pm.check_permission = AsyncMock(return_value=(True, ""))
    risk = MagicMock()
    risk.value = "low"
    pm.get_risk_level = MagicMock(return_value=risk)
    return pm


@pytest.fixture
def telemetry():
    t = MagicMock()
    t.record_tool_call = MagicMock()
    return t


@pytest.fixture
def executor(permission_manager, telemetry):
    tool = _make_tool()
    return ToolExecutor(
        tools={"dummy": tool},
        permission_manager=permission_manager,
        telemetry=telemetry,
        session_id="test-exec",
        quiet=True,
    )


# ---------------------------------------------------------------------------
# Sequential execution
# ---------------------------------------------------------------------------

class TestSequentialExecution:
    async def test_sequential_single(self, executor):
        tc = _make_tool_call()
        results = await executor.execute([tc], parallel=False)
        assert len(results) == 1
        assert results[0].success
        assert results[0].content == "ok"
        assert results[0].function_name == "dummy"

    async def test_sequential_multiple(self, executor):
        tc1 = _make_tool_call("tc1")
        tc2 = _make_tool_call("tc2")
        results = await executor.execute([tc1, tc2], parallel=False)
        assert len(results) == 2
        assert results[0].tool_call_id == "tc1"
        assert results[1].tool_call_id == "tc2"

    async def test_empty_tool_calls(self, executor):
        results = await executor.execute([], parallel=False)
        assert results == []


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

class TestParallelExecution:
    async def test_parallel_multiple(self, executor):
        tc1 = _make_tool_call("tc1")
        tc2 = _make_tool_call("tc2")
        results = await executor.execute([tc1, tc2], parallel=True)
        assert len(results) == 2

    async def test_parallel_single_falls_back_to_sequential(self, executor):
        tc = _make_tool_call()
        results = await executor.execute([tc], parallel=True)
        assert len(results) == 1
        assert results[0].success


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

class TestUnknownTool:
    async def test_unknown_tool_returns_error(self, executor):
        tc = _make_tool_call(name="nonexistent")
        results = await executor.execute([tc], parallel=False)
        assert len(results) == 1
        assert not results[0].success
        assert "未知工具" in results[0].content


# ---------------------------------------------------------------------------
# Permission denied
# ---------------------------------------------------------------------------

class TestPermissionDenied:
    async def test_permission_denied(self, executor, permission_manager):
        permission_manager.check_permission = AsyncMock(
            return_value=(False, "操作被拒绝")
        )
        tc = _make_tool_call()
        results = await executor.execute([tc], parallel=False)
        assert len(results) == 1
        assert not results[0].success
        assert "权限拒绝" in results[0].content


# ---------------------------------------------------------------------------
# Tool exception
# ---------------------------------------------------------------------------

class TestToolException:
    async def test_tool_raises_exception(self, permission_manager, telemetry):
        tool = _make_tool()
        tool.execute = AsyncMock(side_effect=RuntimeError("boom"))
        executor = ToolExecutor(
            tools={"dummy": tool},
            permission_manager=permission_manager,
            telemetry=telemetry,
            session_id="test-exc",
            quiet=True,
        )
        tc = _make_tool_call()
        results = await executor.execute([tc], parallel=False)
        assert len(results) == 1
        assert not results[0].success
        assert "执行异常" in results[0].content
        assert "boom" in results[0].content

    async def test_parallel_exception_handled(self, permission_manager, telemetry):
        good_tool = _make_tool("good")
        bad_tool = _make_tool("bad")
        bad_tool.execute = AsyncMock(side_effect=ValueError("fail"))
        executor = ToolExecutor(
            tools={"good": good_tool, "bad": bad_tool},
            permission_manager=permission_manager,
            telemetry=telemetry,
            session_id="test-par-exc",
            quiet=True,
        )
        tc1 = _make_tool_call("tc1", name="good")
        tc2 = _make_tool_call("tc2", name="bad")
        results = await executor.execute([tc1, tc2], parallel=True)
        assert len(results) == 2
        successes = [r.success for r in results]
        assert True in successes
        assert False in successes


# ---------------------------------------------------------------------------
# _filter_sensitive_output
# ---------------------------------------------------------------------------

class TestFilterSensitiveOutput:
    def test_aws_key_redacted(self):
        output, blocked, reason = _filter_sensitive_output(
            "key is AKIAIOSFODNN7EXAMPLE"
        )
        assert blocked
        assert "REDACTED" in output
        assert "AWS" in reason

    def test_github_token_redacted(self):
        output, blocked, reason = _filter_sensitive_output(
            "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh1234"
        )
        assert blocked
        assert "REDACTED" in output
        assert "GitHub" in reason

    def test_pem_key_redacted(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        output, blocked, reason = _filter_sensitive_output(pem)
        assert blocked
        assert "REDACTED" in output

    def test_api_key_assignment_redacted(self):
        output, blocked, reason = _filter_sensitive_output(
            "api_key=sk-abc123def456ghi789jkl012mno345"
        )
        assert blocked
        assert "REDACTED" in output

    def test_clean_content_passes(self):
        clean = "def hello():\n    return 'world'"
        output, blocked, reason = _filter_sensitive_output(clean)
        assert not blocked
        assert output == clean
        assert reason == ""

    def test_empty_string(self):
        output, blocked, reason = _filter_sensitive_output("")
        assert not blocked

    def test_none_input(self):
        output, blocked, reason = _filter_sensitive_output(None)
        assert not blocked

    def test_word_token_no_false_positive(self):
        text = "def get_token(self):\n    return self.token"
        output, blocked, _ = _filter_sensitive_output(text)
        assert not blocked
        assert output == text


# ---------------------------------------------------------------------------
# _summarize_arguments
# ---------------------------------------------------------------------------

class TestSummarizeArguments:
    def test_short_values_unchanged(self):
        args = {"key": "value", "num": "42"}
        result = _summarize_arguments(args)
        assert result["key"] == "value"
        assert result["num"] == "42"

    def test_long_values_truncated(self):
        args = {"code": "x" * 200}
        result = _summarize_arguments(args)
        assert len(result["code"]) == 123  # 120 + "..."
        assert result["code"].endswith("...")

    def test_empty_args(self):
        result = _summarize_arguments({})
        assert result == {}
