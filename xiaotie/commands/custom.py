"""
Custom commands management Mixin.
"""

from .base import CommandsBase


class CustomCommandsMixin(CommandsBase):
    """Custom user & project commands like commands, run, cmd-*"""

    def cmd_commands(self, args: str) -> tuple[bool, str]:
        """列出所有自定义命令"""
        commands = self.custom_cmd_mgr.list_commands()

        if not commands:
            lines = [
                "\\n📜 自定义命令",
                "",
                "  暂无自定义命令",
                "",
                "  创建命令:",
                "    /cmd-new <名称>         - 创建用户命令",
                "    /cmd-new-project <名称> - 创建项目命令",
                "",
                "  命令目录:",
            ]
            for d in self.custom_cmd_mgr.user_command_dirs[:2]:
                lines.append(f"    用户: {d}")
            lines.append(f"    项目: {self.custom_cmd_mgr.project_command_dir}")
            return True, "\\n".join(lines)

        # 按来源分组
        user_cmds = [c for c in commands if c.source == "user"]
        project_cmds = [c for c in commands if c.source == "project"]

        lines = ["\\n📜 自定义命令:\\n"]

        if user_cmds:
            lines.append("  用户命令:")
            for cmd in user_cmds:
                desc = (
                    cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                )
                args_hint = f" ({len(cmd.arguments)} 参数)" if cmd.arguments else ""
                lines.append(f"    • {cmd.id}{args_hint}")
                if desc:
                    lines.append(f"      {desc}")

        if project_cmds:
            if user_cmds:
                lines.append("")
            lines.append("  项目命令:")
            for cmd in project_cmds:
                desc = (
                    cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                )
                args_hint = f" ({len(cmd.arguments)} 参数)" if cmd.arguments else ""
                lines.append(f"    • {cmd.id}{args_hint}")
                if desc:
                    lines.append(f"      {desc}")

        lines.append("")
        lines.append("  执行命令: /run <命令ID>")

        return True, "\\n".join(lines)

    async def cmd_run(self, args: str) -> tuple[bool, str]:
        """执行自定义命令 (用法: /run <命令ID>)"""
        if not args:
            return True, "用法: /run <命令ID>\\n\\n使用 /commands 查看可用命令"

        cmd_id = args.strip()

        # 尝试匹配命令
        cmd = self.custom_cmd_mgr.get_command(cmd_id)

        # 如果没找到，尝试添加前缀
        if not cmd:
            for prefix in ["user:", "project:"]:
                cmd = self.custom_cmd_mgr.get_command(f"{prefix}{cmd_id}")
                if cmd:
                    break

        if not cmd:
            return True, f"❌ 未找到命令: {cmd_id}\\n\\n使用 /commands 查看可用命令"

        # 执行命令
        should_continue, content = await self.custom_cmd_executor.execute(cmd.id)

        # 返回内容作为要发送给 AI 的提示
        return should_continue, f"__CUSTOM_CMD__:{content}"

    def cmd_cmd_new(self, args: str) -> tuple[bool, str]:
        """创建用户自定义命令 (用法: /cmd-new <名称>)"""
        if not args:
            return True, "用法: /cmd-new <命令名称>\\n\\n示例: /cmd-new review-code"

        name = args.strip().lower().replace(" ", "-")
        file_path = self.custom_cmd_mgr.create_command_template(name, source="user")

        return True, (
            f"✅ 命令模板已创建: {file_path}\\n\\n"
            f"编辑文件后使用 /run user:{name} 执行\\n"
            f"或使用 /cmd-reload 重新加载命令列表"
        )

    def cmd_cmd_new_project(self, args: str) -> tuple[bool, str]:
        """创建项目自定义命令 (用法: /cmd-new-project <名称>)"""
        if not args:
            return True, "用法: /cmd-new-project <命令名称>\\n\\n示例: /cmd-new-project deploy"

        name = args.strip().lower().replace(" ", "-")
        file_path = self.custom_cmd_mgr.create_command_template(name, source="project")

        return True, (
            f"✅ 项目命令模板已创建: {file_path}\\n\\n"
            f"编辑文件后使用 /run project:{name} 执行\\n"
            f"或使用 /cmd-reload 重新加载命令列表"
        )

    def cmd_cmd_reload(self, args: str) -> tuple[bool, str]:
        """重新加载自定义命令"""
        self.custom_cmd_mgr.reload()
        count = len(self.custom_cmd_mgr.list_commands())
        return True, f"✅ 已重新加载 {count} 个自定义命令"

    def cmd_cmd_show(self, args: str) -> tuple[bool, str]:
        """显示自定义命令内容 (用法: /cmd-show <命令ID>)"""
        if not args:
            return True, "用法: /cmd-show <命令ID>"

        cmd_id = args.strip()
        cmd = self.custom_cmd_mgr.get_command(cmd_id)

        # 尝试添加前缀
        if not cmd:
            for prefix in ["user:", "project:"]:
                cmd = self.custom_cmd_mgr.get_command(f"{prefix}{cmd_id}")
                if cmd:
                    break

        if not cmd:
            return True, f"❌ 未找到命令: {cmd_id}"

        lines = [
            f"\\n📜 命令: {cmd.id}",
            f"   文件: {cmd.file_path}",
        ]

        if cmd.arguments:
            lines.append(f"   参数: {', '.join(cmd.arguments)}")

        lines.append("")
        lines.append("内容:")
        lines.append("-" * 40)
        lines.append(cmd.content[:500])
        if len(cmd.content) > 500:
            lines.append("... (内容已截断)")

        return True, "\\n".join(lines)

    def completions_run(self) -> list[str]:
        """run 命令的补全"""
        commands = self.custom_cmd_mgr.list_commands()
        return [c.id for c in commands]

    def cmd_safe(self, args: str) -> tuple[bool, str]:
        """安全模式管理 (用法: /safe [strict|relaxed|status])"""
        pm = getattr(self.agent, "permission_manager", None)
        if pm is None:
            return True, "⚠️ 权限管理器未初始化"

        sub = args.strip().lower() if args else "status"

        if sub == "strict":
            pm.auto_approve_low_risk = True
            pm.auto_approve_medium_risk = False
            pm.require_double_confirm_high_risk = True
            return True, (
                "🔒 已切换到严格模式\n"
                "  • 低风险: 自动批准\n"
                "  • 中风险: 需要确认\n"
                "  • 高风险: 需要二次确认"
            )
        elif sub == "relaxed":
            pm.auto_approve_low_risk = True
            pm.auto_approve_medium_risk = True
            pm.require_double_confirm_high_risk = False
            return True, ("🔓 已切换到宽松模式\n  • 低/中风险: 自动批准\n  • 高风险: 单次确认")
        else:
            # status
            stats = pm.get_stats()
            history = pm.get_decision_history()
            recent = history[-5:] if history else []

            lines = [
                "\n🛡️ 安全模式状态",
                f"  自动批准低风险: {'✅' if stats['auto_approve_low_risk'] else '❌'}",
                f"  自动批准中风险: {'✅' if stats['auto_approve_medium_risk'] else '❌'}",
                f"  高风险二次确认: {'✅' if pm.require_double_confirm_high_risk else '❌'}",
                f"  会话白名单: {stats['session_whitelist']} 条",
                f"  永久白名单: {stats['permanent_whitelist']} 条",
                f"  决策总数: {stats['total_decisions']}",
            ]
            if recent:
                lines.append("\n  📋 最近决策:")
                for d in recent:
                    icon = "✅" if d["approved"] else "❌"
                    lines.append(f"    {icon} [{d['risk_level']}] {d['tool_name']}: {d['reason']}")

            lines.append("\n  用法: /safe strict | /safe relaxed")
            return True, "\n".join(lines)
