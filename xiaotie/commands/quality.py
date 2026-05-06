"""
Quality and feedback loop commands Mixin.
"""

from .base import CommandsBase


class QualityCommandsMixin(CommandsBase):
    """Quality related commands like lint, test, autolint"""

    async def cmd_lint(self, args: str) -> tuple[bool, str]:
        """对文件运行 lint 检查 (用法: /lint <文件路径>)"""
        if not args:
            return True, "用法: /lint <文件路径>"

        from xiaotie.feedback import FeedbackConfig, FeedbackLoop

        file_path = args.strip()
        feedback = FeedbackLoop(
            self.agent.workspace_dir, FeedbackConfig(auto_lint=True, auto_test=False)
        )

        result = await feedback.lint_file(file_path)

        if result.success:
            return True, f"✅ Lint 检查通过: {file_path}"
        else:
            lines = [f"❌ Lint 检查失败: {file_path}"]
            if result.errors:
                lines.append("\\n错误:")
                for err in result.errors[:5]:
                    lines.append(f"  • {err}")
            return True, "\\n".join(lines)

    async def cmd_test(self, args: str) -> tuple[bool, str]:
        """运行测试 (用法: /test [文件路径])"""
        from xiaotie.feedback import FeedbackConfig, FeedbackLoop

        file_path = args.strip() if args else None
        feedback = FeedbackLoop(
            self.agent.workspace_dir, FeedbackConfig(auto_lint=False, auto_test=True)
        )

        result = await feedback.run_tests(file_path)

        if result.success:
            return True, f"✅ 测试通过: {result.passed} 个测试"
        else:
            lines = [f"❌ 测试失败: {result.failed} 个失败, {result.passed} 个通过"]
            if result.errors:
                lines.append("\\n错误:")
                for err in result.errors[:5]:
                    lines.append(f"  • {err}")
            return True, "\\n".join(lines)

    def cmd_autolint(self, args: str) -> tuple[bool, str]:
        """切换自动 lint 检查"""
        # 需要在 agent 中添加 feedback_loop 属性
        return True, "⚠️ 自动 lint 功能开发中"
