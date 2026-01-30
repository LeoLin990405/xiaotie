"""Lint/Test 反馈循环

参考 Aider 的设计：
- 自动运行 lint/test 命令
- 检测错误并反馈给 LLM
- 自动修复循环
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LintResult:
    """Lint 结果"""

    success: bool
    output: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_path: Optional[str] = None


@dataclass
class TestResult:
    """测试结果"""

    success: bool
    output: str
    passed: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class FeedbackConfig:
    """反馈配置"""

    # Lint 配置
    auto_lint: bool = True
    lint_cmd: Optional[str] = None  # 自定义 lint 命令
    lint_on_save: bool = True

    # Test 配置
    auto_test: bool = False  # 默认不自动测试（可能耗时）
    test_cmd: Optional[str] = None  # 自定义测试命令
    test_on_save: bool = False

    # 自动修复
    auto_fix: bool = True
    max_fix_attempts: int = 3


# 语言对应的默认 lint 命令
DEFAULT_LINT_COMMANDS: Dict[str, str] = {
    ".py": "python -m py_compile {file}",
    ".js": "node --check {file}",
    ".ts": "npx tsc --noEmit {file}",
    ".jsx": "npx eslint {file}",
    ".tsx": "npx eslint {file}",
    ".go": "go vet {file}",
    ".rs": "rustfmt --check {file}",
    ".rb": "ruby -c {file}",
    ".sh": "bash -n {file}",
}

# 语言对应的默认测试命令
DEFAULT_TEST_COMMANDS: Dict[str, str] = {
    ".py": "python -m pytest {dir} -x --tb=short",
    ".js": "npm test",
    ".ts": "npm test",
    ".go": "go test {dir}/...",
    ".rs": "cargo test",
}

# 错误模式匹配
ERROR_PATTERNS = {
    "python": [
        r"File \"([^\"]+)\", line (\d+)",
        r"SyntaxError: (.+)",
        r"IndentationError: (.+)",
        r"NameError: (.+)",
        r"TypeError: (.+)",
    ],
    "javascript": [
        r"at ([^:]+):(\d+):(\d+)",
        r"SyntaxError: (.+)",
        r"ReferenceError: (.+)",
        r"TypeError: (.+)",
    ],
    "typescript": [
        r"([^:]+)\((\d+),(\d+)\): error TS\d+: (.+)",
    ],
    "go": [
        r"([^:]+):(\d+):(\d+): (.+)",
    ],
}


class FeedbackLoop:
    """Lint/Test 反馈循环"""

    def __init__(
        self,
        workspace_dir: str,
        config: Optional[FeedbackConfig] = None,
    ):
        self.workspace = Path(workspace_dir).absolute()
        self.config = config or FeedbackConfig()
        self._fix_attempts: Dict[str, int] = {}

    def _get_lint_command(self, file_path: str) -> Optional[str]:
        """获取 lint 命令"""
        if self.config.lint_cmd:
            return self.config.lint_cmd.format(file=file_path)

        suffix = Path(file_path).suffix.lower()
        if suffix in DEFAULT_LINT_COMMANDS:
            return DEFAULT_LINT_COMMANDS[suffix].format(file=file_path)

        return None

    def _get_test_command(self, file_path: str) -> Optional[str]:
        """获取测试命令"""
        if self.config.test_cmd:
            return self.config.test_cmd.format(file=file_path, dir=str(Path(file_path).parent))

        suffix = Path(file_path).suffix.lower()
        if suffix in DEFAULT_TEST_COMMANDS:
            return DEFAULT_TEST_COMMANDS[suffix].format(
                file=file_path, dir=str(Path(file_path).parent)
            )

        return None

    def _detect_language(self, file_path: str) -> str:
        """检测文件语言"""
        suffix = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
        }
        return language_map.get(suffix, "unknown")

    def _parse_errors(self, output: str, language: str) -> List[str]:
        """解析错误信息"""
        errors = []
        patterns = ERROR_PATTERNS.get(language, [])

        for pattern in patterns:
            for match in re.finditer(pattern, output, re.MULTILINE):
                errors.append(match.group(0))

        # 如果没有匹配到特定模式，提取包含 error/Error 的行
        if not errors:
            for line in output.split("\n"):
                if "error" in line.lower() or "Error" in line:
                    errors.append(line.strip())

        return errors[:10]  # 限制错误数量

    async def _run_command(self, command: str, timeout: int = 60) -> Tuple[bool, str]:
        """运行命令"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")

            return process.returncode == 0, output

        except asyncio.TimeoutError:
            return False, f"命令超时（{timeout}秒）"
        except Exception as e:
            return False, f"执行失败: {e}"

    async def lint_file(self, file_path: str) -> LintResult:
        """对文件运行 lint"""
        command = self._get_lint_command(file_path)
        if not command:
            return LintResult(
                success=True,
                output="无可用的 lint 命令",
                file_path=file_path,
            )

        success, output = await self._run_command(command)
        language = self._detect_language(file_path)
        errors = self._parse_errors(output, language) if not success else []

        return LintResult(
            success=success,
            output=output,
            errors=errors,
            file_path=file_path,
        )

    async def run_tests(self, file_path: Optional[str] = None) -> TestResult:
        """运行测试"""
        command = self._get_test_command(file_path or ".")
        if not command:
            return TestResult(
                success=True,
                output="无可用的测试命令",
            )

        success, output = await self._run_command(command, timeout=120)

        # 解析测试结果
        passed = 0
        failed = 0

        # pytest 格式
        pytest_match = re.search(r"(\d+) passed", output)
        if pytest_match:
            passed = int(pytest_match.group(1))
        pytest_fail = re.search(r"(\d+) failed", output)
        if pytest_fail:
            failed = int(pytest_fail.group(1))

        # 通用格式
        if not passed and not failed:
            pass_match = re.search(r"(\d+)\s+(?:tests?\s+)?pass", output, re.IGNORECASE)
            if pass_match:
                passed = int(pass_match.group(1))
            fail_match = re.search(r"(\d+)\s+(?:tests?\s+)?fail", output, re.IGNORECASE)
            if fail_match:
                failed = int(fail_match.group(1))

        errors = self._parse_errors(output, "python") if not success else []

        return TestResult(
            success=success,
            output=output,
            passed=passed,
            failed=failed,
            errors=errors,
        )

    async def check_file(self, file_path: str) -> Dict[str, Any]:
        """检查文件（lint + 可选测试）

        Returns:
            {
                "lint": LintResult,
                "test": TestResult | None,
                "needs_fix": bool,
                "feedback": str,
            }
        """
        result = {
            "lint": None,
            "test": None,
            "needs_fix": False,
            "feedback": "",
        }

        # 运行 lint
        if self.config.auto_lint:
            lint_result = await self.lint_file(file_path)
            result["lint"] = lint_result

            if not lint_result.success:
                result["needs_fix"] = True
                result["feedback"] = self._format_lint_feedback(lint_result)

        # 运行测试
        if self.config.auto_test and not result["needs_fix"]:
            test_result = await self.run_tests(file_path)
            result["test"] = test_result

            if not test_result.success:
                result["needs_fix"] = True
                result["feedback"] = self._format_test_feedback(test_result)

        return result

    def _format_lint_feedback(self, result: LintResult) -> str:
        """格式化 lint 反馈"""
        lines = [f"❌ Lint 检查失败: {result.file_path}"]

        if result.errors:
            lines.append("\n错误信息:")
            for error in result.errors[:5]:
                lines.append(f"  • {error}")

        lines.append("\n请修复以上错误后重试。")
        return "\n".join(lines)

    def _format_test_feedback(self, result: TestResult) -> str:
        """格式化测试反馈"""
        lines = [f"❌ 测试失败: {result.failed} 个测试未通过"]

        if result.errors:
            lines.append("\n错误信息:")
            for error in result.errors[:5]:
                lines.append(f"  • {error}")

        lines.append("\n请修复测试错误后重试。")
        return "\n".join(lines)

    def should_auto_fix(self, file_path: str) -> bool:
        """检查是否应该自动修复"""
        if not self.config.auto_fix:
            return False

        attempts = self._fix_attempts.get(file_path, 0)
        return attempts < self.config.max_fix_attempts

    def record_fix_attempt(self, file_path: str):
        """记录修复尝试"""
        self._fix_attempts[file_path] = self._fix_attempts.get(file_path, 0) + 1

    def reset_fix_attempts(self, file_path: str):
        """重置修复尝试计数"""
        self._fix_attempts.pop(file_path, None)

    def get_fix_prompt(self, feedback: str) -> str:
        """生成修复提示"""
        return f"""
检测到代码错误，请修复：

{feedback}

请分析错误原因并修复代码。修复后我会自动重新检查。
"""
