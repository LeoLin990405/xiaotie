"""GitTool 单元测试

测试覆盖：
- status / diff / log / commit / branch / add / show 命令
- _sanitize_git_args 参数安全解析
- 错误处理（非 git 仓库、未知命令、运行时错误）
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.tools.git_tool import GitTool, _sanitize_git_args


# ---------------------------------------------------------------------------
# _sanitize_git_args 安全解析
# ---------------------------------------------------------------------------

class TestSanitizeGitArgs:
    """参数安全解析测试"""

    def test_empty_string(self):
        assert _sanitize_git_args("") == []

    def test_normal_args(self):
        assert _sanitize_git_args("main") == ["main"]
        assert _sanitize_git_args("-a -v") == ["-a", "-v"]

    def test_file_path(self):
        assert _sanitize_git_args("src/main.py") == ["src/main.py"]

    @pytest.mark.parametrize("dangerous_arg", [
        "--exec=evil",
        "--upload-pack=evil",
        "--receive-pack=evil",
        "--config key=val",
        "--work-tree=/tmp",
        "--git-dir=/tmp",
        "--exec-path=/tmp",
        "-c",
        "--no-verify",
        "--force",
    ])
    def test_dangerous_args_rejected(self, dangerous_arg):
        with pytest.raises(ValueError, match="不允许的 git 参数"):
            _sanitize_git_args(dangerous_arg)

    def test_quoted_args(self):
        result = _sanitize_git_args('"file with spaces.py"')
        assert result == ["file with spaces.py"]


# ---------------------------------------------------------------------------
# GitTool 辅助 fixture
# ---------------------------------------------------------------------------

def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    """构造一个模拟的 asyncio.subprocess.Process"""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout_text = stdout
    proc.stderr_text = stderr
    return proc


@pytest.fixture
def git_tool(tmp_path):
    return GitTool(workspace_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# 非 git 仓库
# ---------------------------------------------------------------------------

class TestGitToolNotRepo:
    """非 git 仓库场景"""

    @pytest.mark.asyncio
    async def test_not_git_repo(self, git_tool):
        with patch.object(git_tool, "_is_git_repo", return_value=False):
            result = await git_tool.execute("status")
            assert result.success is False
            assert "不是 Git 仓库" in result.error


# ---------------------------------------------------------------------------
# status 命令
# ---------------------------------------------------------------------------

class TestGitStatus:

    @pytest.mark.asyncio
    async def test_status_clean(self, git_tool):
        proc = _make_proc(stdout="## main\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("status")
            assert result.success is True
            assert "分支" in result.content

    @pytest.mark.asyncio
    async def test_status_modified(self, git_tool):
        proc = _make_proc(stdout="## main\n M src/app.py\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("status")
            assert result.success is True
            assert "app.py" in result.content

    @pytest.mark.asyncio
    async def test_status_untracked(self, git_tool):
        proc = _make_proc(stdout="## main\n?? new_file.py\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("status")
            assert result.success is True
            assert "new_file.py" in result.content


# ---------------------------------------------------------------------------
# diff 命令
# ---------------------------------------------------------------------------

class TestGitDiff:

    @pytest.mark.asyncio
    async def test_diff_no_changes(self, git_tool):
        proc_stat = _make_proc(stdout="")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc_stat):
            result = await git_tool.execute("diff")
            assert result.success is True
            assert "没有差异" in result.content

    @pytest.mark.asyncio
    async def test_diff_with_changes(self, git_tool):
        proc_stat = _make_proc(stdout=" file.py | 2 +-\n")
        proc_full = _make_proc(stdout="+added line\n-removed line\n")
        call_count = 0

        async def mock_run_git(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return proc_stat if call_count == 1 else proc_full

        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", side_effect=mock_run_git):
            result = await git_tool.execute("diff")
            assert result.success is True
            assert "差异" in result.content

    @pytest.mark.asyncio
    async def test_diff_dangerous_args(self, git_tool):
        with patch.object(git_tool, "_is_git_repo", return_value=True):
            result = await git_tool.execute("diff", "--exec=evil")
            assert result.success is False


# ---------------------------------------------------------------------------
# log 命令
# ---------------------------------------------------------------------------

class TestGitLog:

    @pytest.mark.asyncio
    async def test_log(self, git_tool):
        proc = _make_proc(stdout="* abc1234 Initial commit\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("log")
            assert result.success is True
            assert "提交历史" in result.content


# ---------------------------------------------------------------------------
# branch 命令
# ---------------------------------------------------------------------------

class TestGitBranch:

    @pytest.mark.asyncio
    async def test_branch_list(self, git_tool):
        proc = _make_proc(stdout="* main  abc1234 Initial\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("branch")
            assert result.success is True
            assert "分支列表" in result.content

    @pytest.mark.asyncio
    async def test_branch_create(self, git_tool):
        proc = _make_proc(stdout="")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("branch", "feature-x")
            assert result.success is True
            assert "已创建分支" in result.content

    @pytest.mark.asyncio
    async def test_branch_delete(self, git_tool):
        proc = _make_proc(stdout="")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("branch", "-d feature-x")
            assert result.success is True
            assert "已删除分支" in result.content


# ---------------------------------------------------------------------------
# commit 命令
# ---------------------------------------------------------------------------

class TestGitCommit:

    @pytest.mark.asyncio
    async def test_commit_no_message(self, git_tool):
        with patch.object(git_tool, "_is_git_repo", return_value=True):
            result = await git_tool.execute("commit")
            assert result.success is False
            assert "提交信息" in result.error

    @pytest.mark.asyncio
    async def test_commit_no_staged(self, git_tool):
        proc = _make_proc(stdout="")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("commit", "fix bug")
            assert result.success is False
            assert "暂存" in result.error

    @pytest.mark.asyncio
    async def test_commit_success(self, git_tool):
        proc_staged = _make_proc(stdout=" file.py | 1 +\n")
        proc_commit = _make_proc(stdout="[main abc1234] fix bug\n")
        call_count = 0

        async def mock_run_git(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return proc_staged if call_count == 1 else proc_commit

        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", side_effect=mock_run_git):
            result = await git_tool.execute("commit", "fix bug")
            assert result.success is True
            assert "提交成功" in result.content


# ---------------------------------------------------------------------------
# add 命令
# ---------------------------------------------------------------------------

class TestGitAdd:

    @pytest.mark.asyncio
    async def test_add_no_args(self, git_tool):
        with patch.object(git_tool, "_is_git_repo", return_value=True):
            result = await git_tool.execute("add")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_add_file(self, git_tool):
        proc = _make_proc(stdout="")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("add", "file.py")
            assert result.success is True
            assert "已暂存" in result.content


# ---------------------------------------------------------------------------
# show 命令
# ---------------------------------------------------------------------------

class TestGitShow:

    @pytest.mark.asyncio
    async def test_show_head(self, git_tool):
        proc = _make_proc(stdout="commit abc1234\nAuthor: test\n")
        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", return_value=proc):
            result = await git_tool.execute("show")
            assert result.success is True
            assert "提交详情" in result.content


# ---------------------------------------------------------------------------
# 未知命令 & RuntimeError
# ---------------------------------------------------------------------------

class TestGitToolErrors:

    @pytest.mark.asyncio
    async def test_unknown_command(self, git_tool):
        with patch.object(git_tool, "_is_git_repo", return_value=True):
            result = await git_tool.execute("rebase")
            assert result.success is False
            assert "未知命令" in result.error

    @pytest.mark.asyncio
    async def test_runtime_error(self, git_tool):
        async def raise_runtime(*a, **kw):
            raise RuntimeError("fatal: bad revision")

        with patch.object(git_tool, "_is_git_repo", return_value=True), \
             patch.object(git_tool, "_run_git", side_effect=raise_runtime):
            result = await git_tool.execute("log")
            assert result.success is False
            assert "Git 错误" in result.error

    @pytest.mark.asyncio
    async def test_tool_properties(self, git_tool):
        assert git_tool.name == "git"
        assert "command" in git_tool.parameters["properties"]
