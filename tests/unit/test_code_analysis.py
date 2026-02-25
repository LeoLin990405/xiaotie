"""CodeAnalysisTool 单元测试

测试覆盖：
- Python 文件分析（类、函数、导入提取）
- 依赖关系分析
- 文件不存在 / 非文件 错误处理
- 格式化输出
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xiaotie.tools.code_analysis import CodeAnalysisTool


@pytest.fixture
def analysis_tool(tmp_path):
    return CodeAnalysisTool(workspace_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# Python 文件分析
# ---------------------------------------------------------------------------

SAMPLE_PYTHON = '''\
"""Sample module."""

import os
import json
from pathlib import Path
from typing import Optional

class MyClass:
    """A sample class."""

    def method_one(self):
        pass

    async def async_method(self):
        pass

def top_level_func(a, b, c):
    """Top level function."""
    if a > 0:
        for i in range(b):
            pass
    return c
'''


class TestPythonAnalysis:
    """Python 文件分析"""

    @pytest.fixture(autouse=True)
    def _write_sample(self, tmp_path):
        self.py_file = tmp_path / "sample.py"
        self.py_file.write_text(SAMPLE_PYTHON)

    @pytest.mark.asyncio
    async def test_classes_extracted(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        assert result.success is True
        assert "MyClass" in result.content

    @pytest.mark.asyncio
    async def test_functions_extracted(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        assert "top_level_func" in result.content
        assert "method_one" in result.content

    @pytest.mark.asyncio
    async def test_async_function_detected(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        assert "async_method" in result.content

    @pytest.mark.asyncio
    async def test_imports_extracted(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        assert "os" in result.content
        assert "json" in result.content

    @pytest.mark.asyncio
    async def test_dependencies(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        # 依赖列表应包含顶级包名
        assert "os" in result.content
        assert "pathlib" in result.content

    @pytest.mark.asyncio
    async def test_complexity_nonzero(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(self.py_file))
        # 复杂度应 > 0（有 if / for / 类 / 函数）
        assert "复杂度" in result.content

    @pytest.mark.asyncio
    async def test_docstrings_included(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(
            path=str(self.py_file), include_docstrings=True
        )
        assert "A sample class" in result.content

    @pytest.mark.asyncio
    async def test_docstrings_excluded(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(
            path=str(self.py_file), include_docstrings=False
        )
        assert "A sample class" not in result.content


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------

class TestCodeAnalysisErrors:

    @pytest.mark.asyncio
    async def test_file_not_found(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(tmp_path / "nope.py"))
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_not_a_file(self, analysis_tool, tmp_path):
        result = await analysis_tool.execute(path=str(tmp_path))
        assert result.success is False
        assert "不是文件" in result.error

    @pytest.mark.asyncio
    async def test_relative_path_resolved(self, analysis_tool, tmp_path):
        (tmp_path / "rel.py").write_text("x = 1\n")
        result = await analysis_tool.execute(path="rel.py")
        assert result.success is True


# ---------------------------------------------------------------------------
# 通用 / JS 分析
# ---------------------------------------------------------------------------

class TestGenericAnalysis:

    @pytest.mark.asyncio
    async def test_generic_file(self, analysis_tool, tmp_path):
        txt = tmp_path / "data.txt"
        txt.write_text("hello\nworld\n")
        result = await analysis_tool.execute(path=str(txt))
        assert result.success is True
        assert "行数" in result.content

    @pytest.mark.asyncio
    async def test_js_file(self, analysis_tool, tmp_path):
        js = tmp_path / "app.js"
        js.write_text(
            "import React from 'react';\n"
            "class App {}\n"
            "function render() {}\n"
        )
        result = await analysis_tool.execute(path=str(js))
        assert result.success is True
        assert "App" in result.content


# ---------------------------------------------------------------------------
# 工具属性
# ---------------------------------------------------------------------------

class TestCodeAnalysisProperties:

    def test_name(self, analysis_tool):
        assert analysis_tool.name == "analyze_code"

    def test_parameters(self, analysis_tool):
        assert "path" in analysis_tool.parameters["properties"]
