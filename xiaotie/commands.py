"""命令系统 - 约定优于配置

学习自 Aider 的命令设计模式：
- 以 cmd_ 前缀的方法自动注册为命令
- 支持命令补全
- 支持命令别名
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Optional, Callable, Any

if TYPE_CHECKING:
    from .agent import Agent
    from .session import SessionManager


class Commands:
    """命令管理器"""

    # 命令别名
    ALIASES = {
        "q": "quit",
        "exit": "quit",
        "?": "help",
        "h": "help",
    }

    def __init__(
        self,
        agent: "Agent",
        session_mgr: "SessionManager",
        on_quit: Optional[Callable] = None,
    ):
        self.agent = agent
        self.session_mgr = session_mgr
        self.on_quit = on_quit
        self._commands = self._discover_commands()

    def _discover_commands(self) -> dict[str, Callable]:
        """发现所有 cmd_ 前缀的方法"""
        commands = {}
        for name in dir(self):
            if name.startswith("cmd_"):
                cmd_name = name[4:]  # 去掉 cmd_ 前缀
                commands[cmd_name] = getattr(self, name)
        return commands

    def get_command(self, name: str) -> Optional[Callable]:
        """获取命令（支持别名和前缀匹配）"""
        # 处理别名
        name = self.ALIASES.get(name, name)

        # 精确匹配
        if name in self._commands:
            return self._commands[name]

        # 前缀匹配
        matches = [cmd for cmd in self._commands if cmd.startswith(name)]
        if len(matches) == 1:
            return self._commands[matches[0]]

        return None

    def get_completions(self, cmd_name: str) -> list[str]:
        """获取命令补全"""
        completion_method = getattr(self, f"completions_{cmd_name}", None)
        if completion_method:
            return completion_method()
        return []

    def list_commands(self) -> list[tuple[str, str]]:
        """列出所有命令及其描述"""
        result = []
        for name, func in sorted(self._commands.items()):
            doc = func.__doc__ or "无描述"
            # 取第一行作为简短描述
            short_doc = doc.strip().split("\n")[0]
            result.append((name, short_doc))
        return result

    async def execute(self, command_line: str) -> tuple[bool, str]:
        """执行命令

        Returns:
            (should_continue, message): 是否继续循环，返回消息
        """
        parts = command_line.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd_func = self.get_command(cmd_name)
        if not cmd_func:
            # 检查是否有相似命令
            similar = [c for c in self._commands if cmd_name in c or c in cmd_name]
            if similar:
                return True, f"❓ 未知命令: {cmd_name}，你是否想要: /{', /'.join(similar)}"
            return True, f"❓ 未知命令: {cmd_name}，输入 /help 查看帮助"

        # 执行命令
        result = cmd_func(args)
        if inspect.iscoroutine(result):
            result = await result

        return result

    # ==================== 命令实现 ====================

    def cmd_help(self, args: str) -> tuple[bool, str]:
        """显示帮助信息"""
        lines = ["\n📖 可用命令:\n"]
        for name, desc in self.list_commands():
            lines.append(f"  /{name:12} - {desc}")
        lines.append("\n💡 提示: 命令支持前缀匹配，如 /h 等同于 /help")
        return True, "\n".join(lines)

    def cmd_quit(self, args: str) -> tuple[bool, str]:
        """退出程序"""
        # 自动保存会话
        if self.session_mgr.current_session:
            self.session_mgr.save_session(
                self.session_mgr.current_session,
                self.agent.messages
            )
        if self.on_quit:
            self.on_quit()
        return False, "\n👋 再见！"

    def cmd_reset(self, args: str) -> tuple[bool, str]:
        """重置对话历史"""
        self.agent.reset()
        return True, "✅ 对话已重置"

    def cmd_tools(self, args: str) -> tuple[bool, str]:
        """显示可用工具"""
        lines = ["\n🔧 可用工具:\n"]
        for name, tool in self.agent.tools.items():
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            lines.append(f"  • {name}: {desc}")
        return True, "\n".join(lines)

    def cmd_save(self, args: str) -> tuple[bool, str]:
        """保存当前会话"""
        if not self.session_mgr.current_session:
            self.session_mgr.create_session()
        self.session_mgr.save_session(
            self.session_mgr.current_session,
            self.agent.messages
        )
        return True, f"✅ 会话已保存: {self.session_mgr.current_session}"

    def cmd_sessions(self, args: str) -> tuple[bool, str]:
        """列出所有会话"""
        sessions = self.session_mgr.list_sessions()
        if not sessions:
            return True, "📭 暂无保存的会话"

        lines = ["\n📚 保存的会话:\n"]
        for s in sessions[:10]:
            marker = "→" if s["id"] == self.session_mgr.current_session else " "
            lines.append(f"  {marker} {s['id']}: {s['title']} ({s['message_count']} 条消息)")
        return True, "\n".join(lines)

    def cmd_load(self, args: str) -> tuple[bool, str]:
        """加载会话 (用法: /load <session_id>)"""
        if not args:
            sessions = self.session_mgr.list_sessions()
            if sessions:
                lines = ["用法: /load <session_id>\n可用会话:"]
                for s in sessions[:5]:
                    lines.append(f"  - {s['id']}: {s['title']}")
                return True, "\n".join(lines)
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

    def cmd_stream(self, args: str) -> tuple[bool, str]:
        """切换流式输出"""
        self.agent.stream = not self.agent.stream
        status = "开启" if self.agent.stream else "关闭"
        return True, f"✅ 流式输出已{status}"

    def cmd_think(self, args: str) -> tuple[bool, str]:
        """切换深度思考模式"""
        self.agent.enable_thinking = not self.agent.enable_thinking
        status = "开启" if self.agent.enable_thinking else "关闭"
        return True, f"✅ 深度思考已{status}"

    def cmd_model(self, args: str) -> tuple[bool, str]:
        """显示或切换模型 (用法: /model [模型名])"""
        if not args:
            return True, f"📊 当前模型: {self.agent.llm._client.model}"

        # TODO: 实现模型切换
        return True, f"⚠️ 模型切换功能开发中"

    def cmd_tokens(self, args: str) -> tuple[bool, str]:
        """显示 Token 使用情况"""
        estimated = self.agent._estimate_tokens()
        api_total = self.agent.api_total_tokens
        limit = self.agent.token_limit

        lines = [
            "\n📊 Token 使用情况:\n",
            f"  估算消息 Token: {estimated:,}",
            f"  API 累计 Token: {api_total:,}",
            f"  Token 限制: {limit:,}",
            f"  使用率: {max(estimated, api_total) / limit * 100:.1f}%",
        ]
        return True, "\n".join(lines)

    def cmd_clear(self, args: str) -> tuple[bool, str]:
        """清屏"""
        print("\033[2J\033[H", end="")
        return True, ""

    def cmd_history(self, args: str) -> tuple[bool, str]:
        """显示对话历史摘要"""
        messages = self.agent.messages
        lines = [f"\n📜 对话历史 ({len(messages)} 条消息):\n"]

        for i, msg in enumerate(messages[-10:], 1):
            role_icon = {
                "system": "⚙️",
                "user": "👤",
                "assistant": "🤖",
                "tool": "🔧",
            }.get(msg.role, "❓")

            content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            content = content.replace("\n", " ")
            lines.append(f"  {role_icon} {content}")

        if len(messages) > 10:
            lines.insert(1, f"  ... (显示最近 10 条)")

        return True, "\n".join(lines)
