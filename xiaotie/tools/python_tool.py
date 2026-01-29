"""Python 代码执行工具"""

from __future__ import annotations

import sys
import io
import traceback
from typing import Any, Dict

from .base import Tool, ToolResult


class PythonTool(Tool):
    """Python 代码执行工具"""

    @property
    def name(self) -> str:
        return "python"

    @property
    def description(self) -> str:
        return "执行 Python 代码并返回结果。可用于数据处理、计算、文件操作等。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str) -> ToolResult:
        """执行 Python 代码"""
        # 捕获输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        result_value = None
        error = None

        try:
            # 创建执行环境
            exec_globals = {
                "__builtins__": __builtins__,
                "print": print,
            }

            # 执行代码
            exec(code, exec_globals)

            # 获取输出
            stdout_output = sys.stdout.getvalue()
            stderr_output = sys.stderr.getvalue()

            output = ""
            if stdout_output:
                output += stdout_output
            if stderr_output:
                output += f"\n[stderr]\n{stderr_output}"

            return ToolResult(
                success=True,
                content=output if output else "代码执行成功（无输出）",
            )

        except Exception as e:
            error_msg = traceback.format_exc()
            return ToolResult(
                success=False,
                error=f"执行错误:\n{error_msg}",
            )

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


class CalculatorTool(Tool):
    """计算器工具"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "执行数学计算。支持基本运算、数学函数等。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '2 + 3 * 4' 或 'math.sqrt(16)'",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, expression: str) -> ToolResult:
        """执行计算"""
        import math

        try:
            # 安全的计算环境
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "math": math,
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)
            return ToolResult(
                success=True,
                content=str(result),
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"计算错误: {e}",
            )
