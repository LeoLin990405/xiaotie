"""Git 工具

提供 Git 操作能力：
- 状态查看
- 差异对比
- 提交历史
- 分支管理
"""

from __future__ import annotations

import subprocess
from typing import Any, Dict, Optional
from pathlib import Path

from .base import Tool, ToolResult


class GitTool(Tool):
    """Git 操作工具"""

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return """执行 Git 操作。支持的命令：
- status: 查看仓库状态
- diff: 查看文件差异
- log: 查看提交历史
- branch: 查看/创建分支
- add: 暂存文件
- commit: 提交更改
- show: 查看提交详情"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git 命令 (status/diff/log/branch/add/commit/show)",
                    "enum": ["status", "diff", "log", "branch", "add", "commit", "show"],
                },
                "args": {
                    "type": "string",
                    "description": "命令参数，如文件路径、分支名、提交信息等",
                    "default": "",
                },
            },
            "required": ["command"],
        }

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """执行 git 命令"""
        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            check=check,
        )

    def _is_git_repo(self) -> bool:
        """检查是否是 Git 仓库"""
        try:
            result = self._run_git("rev-parse", "--git-dir", check=False)
            return result.returncode == 0
        except Exception:
            return False

    async def execute(self, command: str, args: str = "") -> ToolResult:
        """执行 Git 命令"""
        if not self._is_git_repo():
            return ToolResult(
                success=False,
                error="当前目录不是 Git 仓库",
            )

        try:
            if command == "status":
                return await self._status(args)
            elif command == "diff":
                return await self._diff(args)
            elif command == "log":
                return await self._log(args)
            elif command == "branch":
                return await self._branch(args)
            elif command == "add":
                return await self._add(args)
            elif command == "commit":
                return await self._commit(args)
            elif command == "show":
                return await self._show(args)
            else:
                return ToolResult(
                    success=False,
                    error=f"未知命令: {command}",
                )
        except subprocess.CalledProcessError as e:
            return ToolResult(
                success=False,
                error=f"Git 错误: {e.stderr or e.stdout}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"执行错误: {e}",
            )

    async def _status(self, args: str) -> ToolResult:
        """查看仓库状态"""
        result = self._run_git("status", "--short", "--branch")

        # 解析状态
        lines = result.stdout.strip().split("\n")
        output_lines = ["📊 Git 状态:\n"]

        for line in lines:
            if line.startswith("##"):
                # 分支信息
                branch_info = line[3:]
                output_lines.append(f"🌿 分支: {branch_info}\n")
            elif line:
                status = line[:2]
                filename = line[3:]

                # 状态图标
                if status[0] == "M" or status[1] == "M":
                    icon = "📝"  # 修改
                elif status[0] == "A":
                    icon = "➕"  # 新增
                elif status[0] == "D" or status[1] == "D":
                    icon = "➖"  # 删除
                elif status == "??":
                    icon = "❓"  # 未跟踪
                elif status[0] == "R":
                    icon = "🔄"  # 重命名
                else:
                    icon = "📄"

                output_lines.append(f"  {icon} [{status.strip() or '  '}] {filename}")

        if len(output_lines) == 2:
            output_lines.append("  ✨ 工作区干净")

        return ToolResult(success=True, content="\n".join(output_lines))

    async def _diff(self, args: str) -> ToolResult:
        """查看差异"""
        git_args = ["diff", "--stat"]
        if args:
            git_args.extend(args.split())

        result = self._run_git(*git_args)

        if not result.stdout.strip():
            return ToolResult(success=True, content="没有差异")

        # 获取详细差异（限制行数）
        git_args_full = ["diff"]
        if args:
            git_args_full.extend(args.split())

        result_full = self._run_git(*git_args_full)
        diff_content = result_full.stdout

        # 限制输出长度
        lines = diff_content.split("\n")
        if len(lines) > 100:
            diff_content = "\n".join(lines[:100]) + f"\n\n... (省略 {len(lines) - 100} 行)"

        return ToolResult(
            success=True,
            content=f"📊 差异统计:\n{result.stdout}\n\n📝 详细差异:\n{diff_content}",
        )

    async def _log(self, args: str) -> ToolResult:
        """查看提交历史"""
        git_args = [
            "log",
            "--oneline",
            "--graph",
            "--decorate",
            "-n", "15",  # 最近 15 条
        ]
        if args:
            git_args.extend(args.split())

        result = self._run_git(*git_args)

        return ToolResult(
            success=True,
            content=f"📜 提交历史:\n\n{result.stdout}",
        )

    async def _branch(self, args: str) -> ToolResult:
        """分支操作"""
        if not args:
            # 列出分支
            result = self._run_git("branch", "-a", "-v")
            return ToolResult(
                success=True,
                content=f"🌿 分支列表:\n\n{result.stdout}",
            )
        else:
            # 创建或切换分支
            parts = args.split()
            if parts[0] == "-d":
                # 删除分支
                result = self._run_git("branch", "-d", parts[1])
                return ToolResult(success=True, content=f"已删除分支: {parts[1]}")
            else:
                # 创建分支
                result = self._run_git("branch", parts[0])
                return ToolResult(success=True, content=f"已创建分支: {parts[0]}")

    async def _add(self, args: str) -> ToolResult:
        """暂存文件"""
        if not args:
            return ToolResult(
                success=False,
                error="请指定要暂存的文件，如 'git add .' 或 'git add file.py'",
            )

        files = args.split()
        result = self._run_git("add", *files)

        return ToolResult(
            success=True,
            content=f"✅ 已暂存: {', '.join(files)}",
        )

    async def _commit(self, args: str) -> ToolResult:
        """提交更改"""
        if not args:
            return ToolResult(
                success=False,
                error="请提供提交信息，如 'git commit 修复了一个bug'",
            )

        # 检查是否有暂存的更改
        status_result = self._run_git("diff", "--cached", "--stat")
        if not status_result.stdout.strip():
            return ToolResult(
                success=False,
                error="没有暂存的更改，请先使用 'git add' 暂存文件",
            )

        result = self._run_git("commit", "-m", args)

        return ToolResult(
            success=True,
            content=f"✅ 提交成功:\n{result.stdout}",
        )

    async def _show(self, args: str) -> ToolResult:
        """查看提交详情"""
        commit_ref = args.strip() if args else "HEAD"

        result = self._run_git("show", "--stat", commit_ref)

        # 限制输出
        lines = result.stdout.split("\n")
        if len(lines) > 50:
            content = "\n".join(lines[:50]) + f"\n\n... (省略 {len(lines) - 50} 行)"
        else:
            content = result.stdout

        return ToolResult(
            success=True,
            content=f"📝 提交详情 ({commit_ref}):\n\n{content}",
        )
