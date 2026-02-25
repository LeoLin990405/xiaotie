"""PythonTool / CalculatorTool 单元测试

测试覆盖：
- PythonTool 沙箱执行（成功 / 错误 / 超时）
- CalculatorTool AST 安全求值
- 危险表达式拒绝
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from xiaotie.sandbox import ExecutionResult, ExecutionStatus, SandboxConfig
from xiaotie.tools.python_tool import CalculatorTool, PythonTool


# ---------------------------------------------------------------------------
# CalculatorTool — AST 安全求值
# ---------------------------------------------------------------------------

class TestCalculatorTool:

    @pytest.fixture
    def calc(self):
        return CalculatorTool()

    @pytest.mark.asyncio
    async def test_basic_arithmetic(self, calc):
        result = await calc.execute(expression="2 + 3 * 4")
        assert result.success is True
        assert result.content == "14"

    @pytest.mark.asyncio
    async def test_float_division(self, calc):
        result = await calc.execute(expression="7 / 2")
        assert result.success is True
        assert result.content == "3.5"

    @pytest.mark.asyncio
    async def test_floor_division(self, calc):
        result = await calc.execute(expression="7 // 2")
        assert result.success is True
        assert result.content == "3"

    @pytest.mark.asyncio
    async def test_modulo(self, calc):
        result = await calc.execute(expression="10 % 3")
        assert result.success is True
        assert result.content == "1"

    @pytest.mark.asyncio
    async def test_power(self, calc):
        result = await calc.execute(expression="2 ** 10")
        assert result.success is True
        assert result.content == "1024"

    @pytest.mark.asyncio
    async def test_unary_minus(self, calc):
        result = await calc.execute(expression="-5 + 3")
        assert result.success is True
        assert result.content == "-2"

    @pytest.mark.asyncio
    async def test_math_sqrt(self, calc):
        result = await calc.execute(expression="math.sqrt(16)")
        assert result.success is True
        assert result.content == "4.0"

    @pytest.mark.asyncio
    async def test_math_pi(self, calc):
        result = await calc.execute(expression="math.pi")
        assert result.success is True
        assert "3.14" in result.content

    @pytest.mark.asyncio
    async def test_builtin_abs(self, calc):
        result = await calc.execute(expression="abs(-42)")
        assert result.success is True
        assert result.content == "42"

    @pytest.mark.asyncio
    async def test_builtin_min_max(self, calc):
        r1 = await calc.execute(expression="min([3, 1, 2])")
        assert r1.success is True and r1.content == "1"
        r2 = await calc.execute(expression="max([3, 1, 2])")
        assert r2.success is True and r2.content == "3"

    @pytest.mark.asyncio
    async def test_reject_large_exponent(self, calc):
        result = await calc.execute(expression="2 ** 10000")
        assert result.success is False
        assert "指数过大" in result.error

    @pytest.mark.asyncio
    async def test_reject_string_constant(self, calc):
        result = await calc.execute(expression="'hello'")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_reject_import(self, calc):
        result = await calc.execute(expression="__import__('os')")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_reject_disallowed_name(self, calc):
        result = await calc.execute(expression="open")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_syntax_error(self, calc):
        result = await calc.execute(expression="2 +")
        assert result.success is False

    def test_properties(self, calc):
        assert calc.name == "calculator"
        assert "expression" in calc.parameters["properties"]


# ---------------------------------------------------------------------------
# PythonTool — 沙箱执行
# ---------------------------------------------------------------------------

class TestPythonTool:

    @pytest.fixture
    def python_tool(self):
        return PythonTool(sandbox_config=SandboxConfig(timeout=5, memory_limit_mb=64))

    @pytest.mark.asyncio
    async def test_success_execution(self, python_tool):
        """模拟沙箱返回成功结果"""
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="hello world\n",
            stderr="",
        )
        # NOTE: PythonTool.execute 调用 self._sandbox.execute(code) 时没有 await，
        # 所以这里用普通函数 mock（MagicMock）而非 AsyncMock。
        python_tool._sandbox.execute = MagicMock(return_value=mock_result)
        result = await python_tool.execute(code="print('hello world')")
        assert result.success is True
        assert "hello world" in result.content

    @pytest.mark.asyncio
    async def test_success_no_output(self, python_tool):
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="",
            stderr="",
        )
        python_tool._sandbox.execute = MagicMock(return_value=mock_result)
        result = await python_tool.execute(code="x = 1")
        assert result.success is True
        assert "无输出" in result.content

    @pytest.mark.asyncio
    async def test_success_with_stderr(self, python_tool):
        mock_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="ok\n",
            stderr="DeprecationWarning: ...\n",
        )
        python_tool._sandbox.execute = MagicMock(return_value=mock_result)
        result = await python_tool.execute(code="import warnings")
        assert result.success is True
        assert "[stderr]" in result.content

    @pytest.mark.asyncio
    async def test_timeout(self, python_tool):
        mock_result = ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_message="Execution timed out after 5s",
        )
        python_tool._sandbox.execute = MagicMock(return_value=mock_result)
        result = await python_tool.execute(code="while True: pass")
        assert result.success is False
        assert "超时" in result.error

    @pytest.mark.asyncio
    async def test_error(self, python_tool):
        mock_result = ExecutionResult(
            status=ExecutionStatus.ERROR,
            stderr="NameError: name 'x' is not defined",
            error_message="NameError: name 'x' is not defined",
        )
        python_tool._sandbox.execute = MagicMock(return_value=mock_result)
        result = await python_tool.execute(code="print(x)")
        assert result.success is False
        assert "执行错误" in result.error

    @pytest.mark.asyncio
    async def test_sandbox_exception(self, python_tool):
        python_tool._sandbox.execute = MagicMock(side_effect=RuntimeError("sandbox crash"))
        result = await python_tool.execute(code="1+1")
        assert result.success is False
        assert "执行错误" in result.error

    def test_properties(self, python_tool):
        assert python_tool.name == "python"
        assert "code" in python_tool.parameters["properties"]
