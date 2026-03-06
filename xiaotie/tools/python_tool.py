"""Python 代码执行工具"""

from __future__ import annotations

import ast
import math
import operator
import traceback
from typing import Any, Dict

from ..sandbox import Sandbox, SandboxConfig, ExecutionStatus
from .base import Tool, ToolResult


class PythonTool(Tool):
    """Python 代码执行工具（沙箱隔离）"""

    def __init__(self, sandbox_config: SandboxConfig | None = None):
        super().__init__()
        self._sandbox = Sandbox(sandbox_config or SandboxConfig(timeout=30, memory_limit_mb=256))

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
        """通过 Sandbox 执行 Python 代码"""
        try:
            result = await self._sandbox.execute(code)

            if result.status == ExecutionStatus.SUCCESS:
                output = result.stdout
                if result.stderr:
                    output += f"\n[stderr]\n{result.stderr}"
                return ToolResult(
                    success=True,
                    content=output if output.strip() else "代码执行成功（无输出）",
                )
            elif result.status == ExecutionStatus.TIMEOUT:
                return ToolResult(
                    success=False,
                    error=f"执行超时: {result.error_message}",
                )
            else:
                error_msg = result.error_message or result.stderr or "未知错误"
                return ToolResult(
                    success=False,
                    error=f"执行错误:\n{error_msg}",
                )

        except Exception:
            error_msg = traceback.format_exc()
            return ToolResult(
                success=False,
                error=f"执行错误:\n{error_msg}",
            )


class CalculatorTool(Tool):
    """计算器工具（安全 AST 求值）"""

    # 允许的 AST 节点类型（仅数学运算）
    _ALLOWED_NODES = (
        ast.Expression, ast.Module,
        ast.Constant, ast.Num,  # 数字字面量
        ast.UnaryOp, ast.UOp if hasattr(ast, 'UOp') else ast.unaryop,
        ast.USub, ast.UAdd,  # 一元运算符
        ast.BinOp,  # 二元运算
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
        ast.Mod, ast.Pow,  # 算术运算符
        ast.Call,  # 函数调用（受限）
        ast.Name, ast.Load,  # 变量引用
        ast.Attribute,  # 属性访问（如 math.sqrt）
        ast.List, ast.Tuple,  # 用于 min/max/sum
    )

    # 允许的函数名
    _SAFE_FUNCTIONS = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow, "int": int, "float": float,
    }

    # 允许的 math 函数
    _SAFE_MATH = {
        name: getattr(math, name) for name in [
            "sqrt", "ceil", "floor", "log", "log2", "log10",
            "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
            "exp", "factorial", "gcd", "pi", "e", "inf",
            "degrees", "radians", "hypot", "isfinite", "isinf", "isnan",
        ] if hasattr(math, name)
    }

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

    def _safe_eval_node(self, node: ast.AST) -> Any:
        """递归安全求值 AST 节点"""
        if isinstance(node, ast.Expression):
            return self._safe_eval_node(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, complex)):
                return node.value
            raise ValueError(f"不允许的常量类型: {type(node.value).__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._safe_eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            elif isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
        elif isinstance(node, ast.BinOp):
            left = self._safe_eval_node(node.left)
            right = self._safe_eval_node(node.right)
            ops = {
                ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                ast.Pow: operator.pow,
            }
            op_func = ops.get(type(node.op))
            if op_func is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and right > 1000:
                raise ValueError("指数过大，可能导致资源耗尽")
            return op_func(left, right)
        elif isinstance(node, ast.Call):
            return self._safe_eval_call(node)
        elif isinstance(node, ast.Name):
            if node.id == "math":
                return math
            if node.id in self._SAFE_FUNCTIONS:
                return self._SAFE_FUNCTIONS[node.id]
            if node.id in self._SAFE_MATH:
                return self._SAFE_MATH[node.id]
            raise ValueError(f"不允许的名称: {node.id}")
        elif isinstance(node, ast.Attribute):
            value = self._safe_eval_node(node.value)
            if value is math and node.attr in self._SAFE_MATH:
                return self._SAFE_MATH[node.attr]
            raise ValueError(f"不允许的属性访问: {node.attr}")
        elif isinstance(node, (ast.List, ast.Tuple)):
            return [self._safe_eval_node(elt) for elt in node.elts]
        else:
            raise ValueError(f"不允许的表达式类型: {type(node).__name__}")

    def _safe_eval_call(self, node: ast.Call) -> Any:
        """安全求值函数调用"""
        func = self._safe_eval_node(node.func)
        if not callable(func):
            raise ValueError(f"不可调用的对象: {func}")
        # 确保函数在白名单中
        allowed = set(self._SAFE_FUNCTIONS.values()) | set(self._SAFE_MATH.values())
        if func not in allowed:
            raise ValueError(f"不允许的函数调用")
        args = [self._safe_eval_node(arg) for arg in node.args]
        return func(*args)

    async def execute(self, expression: str) -> ToolResult:
        """执行计算（安全 AST 求值）"""
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._safe_eval_node(tree)
            return ToolResult(
                success=True,
                content=str(result),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"计算错误: {e}",
            )
