"""
Session management commands Mixin.
"""

from .base import CommandsBase


class SessionCommandsMixin(CommandsBase):
    """Session related commands like save, load, sessions, new, reset, history, compact"""

    ALIASES = {
        "s": "save",
        "l": "load",
        "r": "reset",
        "hist": "history",
    }

    def cmd_reset(self, args: str) -> tuple[bool, str]:
        """重置对话历史"""
        self.agent.reset()
        return True, "✅ 对话已重置"

    def cmd_save(self, args: str) -> tuple[bool, str]:
        """保存当前会话"""
        if not self.session_mgr.current_session:
            self.session_mgr.create_session()
        self.session_mgr.save_session(self.session_mgr.current_session, self.agent.messages)
        return True, f"✅ 会话已保存: {self.session_mgr.current_session}"

    def cmd_sessions(self, args: str) -> tuple[bool, str]:
        """列出所有会话"""
        sessions = self.session_mgr.list_sessions()
        if not sessions:
            return True, "📭 暂无保存的会话"

        lines = ["\\n📚 保存的会话:\\n"]
        for s in sessions[:10]:
            marker = "→" if s["id"] == self.session_mgr.current_session else " "
            lines.append(f"  {marker} {s['id']}: {s['title']} ({s['message_count']} 条消息)")
        return True, "\\n".join(lines)

    def cmd_load(self, args: str) -> tuple[bool, str]:
        """加载会话 (用法: /load <session_id>)"""
        if not args:
            sessions = self.session_mgr.list_sessions()
            if sessions:
                lines = ["用法: /load <session_id>\\n可用会话:"]
                for s in sessions[:5]:
                    lines.append(f"  - {s['id']}: {s['title']}")
                return True, "\\n".join(lines)
            return True, "📭 暂无可加载的会话"

        session_id = args.strip()
        messages = self.session_mgr.load_session(session_id)
        if messages:
            self.agent.messages = messages
            return True, f"✅ 已加载会话: {session_id}"
        return True, f"❌ 会话不存在: {session_id}"

    def completions_load(self) -> list[str]:
        """load 命令的补全"""
        sessions = self.session_mgr.list_sessions()
        return [s["id"] for s in sessions[:10]]

    def cmd_new(self, args: str) -> tuple[bool, str]:
        """创建新会话 (用法: /new [标题])"""
        title = args.strip() if args else None
        session_id = self.session_mgr.create_session(title)
        self.agent.reset()
        return True, f"✅ 新会话已创建: {session_id}"

    def cmd_history(self, args: str) -> tuple[bool, str]:
        """显示对话历史摘要"""
        messages = self.agent.messages
        lines = [f"\\n📜 对话历史 ({len(messages)} 条消息):\\n"]

        for i, msg in enumerate(messages[-10:], 1):
            role_icon = {
                "system": "⚙️",
                "user": "👤",
                "assistant": "🤖",
                "tool": "🔧",
            }.get(msg.role, "❓")

            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            content = content.replace("\\n", " ")
            lines.append(f"  {role_icon} {content}")

        if len(messages) > 10:
            lines.insert(1, "  ... (显示最近 10 条)")

        return True, "\\n".join(lines)

    async def cmd_compact(self, args: str) -> tuple[bool, str]:
        """手动压缩对话历史"""
        before_tokens = self.agent._estimate_tokens()
        before_messages = len(self.agent.messages)

        old_limit = self.agent.token_limit
        self.agent.token_limit = 0
        await self.agent._summarize_messages()
        self.agent.token_limit = old_limit

        after_tokens = self.agent._estimate_tokens()
        after_messages = len(self.agent.messages)

        return True, (
            f"✅ 对话历史已压缩\\n"
            f"   消息: {before_messages} → {after_messages}\\n"
            f"   Token: {before_tokens:,} → {after_tokens:,}"
        )
