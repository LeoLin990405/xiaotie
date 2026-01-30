"""工具单元测试"""

import os
import pytest
from pathlib import Path

from xiaotie.tools import ReadTool, WriteTool, BashTool
from xiaotie.schema import ToolResult


class TestReadTool:
    """ReadTool 测试"""

    @pytest.fixture
    def read_tool(self, workspace_dir):
        return ReadTool(workspace_dir=workspace_dir)

    @pytest.mark.asyncio
    async def test_read_existing_file(self, read_tool, sample_python_file):
        """测试读取存在的文件"""
        result = await read_tool.execute(path=sample_python_file)
        assert result.success is True
        assert "def hello" in result.content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, read_tool, workspace_dir):
        """测试读取不存在的文件"""
        result = await read_tool.execute(path=os.path.join(workspace_dir, "nonexistent.txt"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_read_with_max_tokens(self, read_tool, sample_python_file):
        """测试读取指定最大 token 数"""
        result = await read_tool.execute(
            path=sample_python_file,
            max_tokens=1000,
        )
        assert result.success is True

    def test_tool_properties(self, read_tool):
        """测试工具属性"""
        assert read_tool.name == "read_file"
        assert "读取" in read_tool.description or "read" in read_tool.description.lower()
        assert "path" in read_tool.parameters["properties"]


class TestWriteTool:
    """WriteTool 测试"""

    @pytest.fixture
    def write_tool(self, workspace_dir):
        return WriteTool(workspace_dir=workspace_dir)

    @pytest.mark.asyncio
    async def test_write_new_file(self, write_tool, workspace_dir):
        """测试写入新文件"""
        file_path = os.path.join(workspace_dir, "new_file.txt")
        result = await write_tool.execute(
            path=file_path,
            content="Hello, World!",
        )
        assert result.success is True
        assert os.path.exists(file_path)
        with open(file_path) as f:
            assert f.read() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_creates_directories(self, write_tool, workspace_dir):
        """测试写入时创建目录"""
        file_path = os.path.join(workspace_dir, "subdir", "nested", "file.txt")
        result = await write_tool.execute(
            path=file_path,
            content="Nested content",
        )
        assert result.success is True
        assert os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, write_tool, sample_python_file):
        """测试覆盖现有文件"""
        result = await write_tool.execute(
            path=sample_python_file,
            content="# New content",
        )
        assert result.success is True
        with open(sample_python_file) as f:
            assert f.read() == "# New content"

    def test_tool_properties(self, write_tool):
        """测试工具属性"""
        assert write_tool.name == "write_file"
        assert "path" in write_tool.parameters["properties"]
        assert "content" in write_tool.parameters["properties"]


class TestBashTool:
    """BashTool 测试"""

    @pytest.fixture
    def bash_tool(self):
        return BashTool()

    @pytest.mark.asyncio
    async def test_simple_command(self, bash_tool):
        """测试简单命令"""
        result = await bash_tool.execute(command="echo 'Hello'")
        assert result.success is True
        assert "Hello" in result.content

    @pytest.mark.asyncio
    async def test_command_with_output(self, bash_tool, workspace_dir):
        """测试有输出的命令"""
        # 创建测试文件
        test_file = os.path.join(workspace_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        result = await bash_tool.execute(command=f"cat {test_file}")
        assert result.success is True
        assert "test content" in result.content

    @pytest.mark.asyncio
    async def test_failed_command(self, bash_tool):
        """测试失败的命令"""
        result = await bash_tool.execute(command="nonexistent_command_xyz")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_command_timeout(self, bash_tool):
        """测试命令超时"""
        result = await bash_tool.execute(
            command="sleep 10",
            timeout=1,
        )
        # 应该超时或被终止
        assert result.success is False

    def test_tool_properties(self, bash_tool):
        """测试工具属性"""
        assert bash_tool.name == "bash"
        assert "command" in bash_tool.parameters["properties"]
