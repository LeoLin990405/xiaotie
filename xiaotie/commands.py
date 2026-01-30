"""命令系统 - 约定优于配置

学习自 Aider 的命令设计模式：
- 以 cmd_ 前缀的方法自动注册为命令
- 支持命令补全
- 支持命令别名

学习自 OpenCode 的自定义命令：
- 用户命令: ~/.xiaotie/commands/
- 项目命令: .xiaotie/commands/
- 支持 Markdown 文件定义命令
- 支持命名参数 $ARG_NAME
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .agent import Agent
    from .plugins import PluginManager
    from .session import SessionManager

from .custom_commands import CustomCommandExecutor, CustomCommandManager


class Commands:
    """命令管理器"""

    # 命令别名
    ALIASES = {
        "q": "quit",
        "exit": "quit",
        "?": "help",
        "h": "help",
        "c": "clear",
        "r": "reset",
        "s": "save",
        "l": "load",
        "t": "tools",
        "tok": "tokens",
        "hist": "history",
        "cfg": "config",
        "cmds": "commands",
    }

    def __init__(
        self,
        agent: "Agent",
        session_mgr: "SessionManager",
        plugin_mgr: Optional["PluginManager"] = None,
        on_quit: Optional[Callable] = None,
        input_callback: Optional[Callable[[str], str]] = None,
    ):
        self.agent = agent
        self.session_mgr = session_mgr
        self.plugin_mgr = plugin_mgr
        self.on_quit = on_quit
        self._commands = self._discover_commands()

        # 自定义命令系统
        self.custom_cmd_mgr = CustomCommandManager(agent.workspace_dir)
        self.custom_cmd_executor = CustomCommandExecutor(
            self.custom_cmd_mgr,
            input_callback=input_callback,
        )

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

        # 显示自定义命令数量
        custom_cmds = self.custom_cmd_mgr.list_commands()
        if custom_cmds:
            lines.append(f"\n📜 自定义命令: {len(custom_cmds)} 个 (使用 /commands 查看)")

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

    def cmd_parallel(self, args: str) -> tuple[bool, str]:
        """切换工具并行执行模式"""
        self.agent.parallel_tools = not self.agent.parallel_tools
        status = "开启" if self.agent.parallel_tools else "关闭"
        return True, f"✅ 工具并行执行已{status}"

    def cmd_model(self, args: str) -> tuple[bool, str]:
        """显示或切换模型 (用法: /model [模型名])"""
        if not args:
            return True, f"📊 当前模型: {self.agent.llm._client.model}"

        # TODO: 实现模型切换
        return True, "⚠️ 模型切换功能开发中"

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
            lines.insert(1, "  ... (显示最近 10 条)")

        return True, "\n".join(lines)

    def cmd_tree(self, args: str) -> tuple[bool, str]:
        """显示项目目录结构"""
        from .repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        max_depth = 3
        if args:
            try:
                max_depth = int(args.strip())
            except ValueError:
                pass

        tree = repo_map.get_tree(max_depth=max_depth)
        return True, f"\n{tree}"

    def cmd_map(self, args: str) -> tuple[bool, str]:
        """显示代码库概览（类、函数定义）"""
        from .repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        max_tokens = 2000
        if args:
            try:
                max_tokens = int(args.strip())
            except ValueError:
                pass

        repo_overview = repo_map.get_repo_map(max_tokens=max_tokens)
        return True, f"\n{repo_overview}"

    def cmd_find(self, args: str) -> tuple[bool, str]:
        """搜索相关文件 (用法: /find <关键词>)"""
        if not args:
            return True, "用法: /find <关键词>"

        from .repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        files = repo_map.find_relevant_files(args.strip(), limit=10)

        if not files:
            return True, f"未找到与 '{args}' 相关的文件"

        lines = [f"\n🔍 搜索结果: {args}\n"]
        for f in files:
            defn_count = len(f.definitions)
            icon = "⭐" if f.is_important else "📄"
            lines.append(f"  {icon} {f.relative_path}")
            if defn_count > 0:
                lines.append(f"      └─ {defn_count} 个定义")

        return True, "\n".join(lines)

    def cmd_plugins(self, args: str) -> tuple[bool, str]:
        """显示已加载的插件"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        tools = self.plugin_mgr.get_loaded_tools()
        if not tools:
            lines = [
                "\n📦 插件系统",
                "",
                "  暂无已加载的插件",
                "",
                "  创建插件: /plugin-new <名称>",
                f"  插件目录: {self.plugin_mgr.DEFAULT_PLUGIN_DIRS[0]}",
            ]
            return True, "\n".join(lines)

        lines = [f"\n📦 已加载 {len(tools)} 个插件工具:\n"]
        for name, tool in tools.items():
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            lines.append(f"  • {name}: {desc}")

        return True, "\n".join(lines)

    def cmd_plugin_new(self, args: str) -> tuple[bool, str]:
        """创建新插件模板 (用法: /plugin-new <名称>)"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        if not args:
            return True, "用法: /plugin-new <插件名称>"

        name = args.strip().lower().replace("-", "_").replace(" ", "_")
        plugin_path = self.plugin_mgr.create_plugin_template(name)

        return True, f"✅ 插件模板已创建: {plugin_path}\n\n编辑后重启或使用 /plugin-reload {name} 加载"

    def cmd_plugin_reload(self, args: str) -> tuple[bool, str]:
        """重新加载插件 (用法: /plugin-reload <名称>)"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        if not args:
            return True, "用法: /plugin-reload <插件名称>"

        name = args.strip()
        if self.plugin_mgr.reload_plugin(name):
            # 更新 agent 的工具列表
            new_tools = self.plugin_mgr.get_loaded_tools()
            for tool_name, tool in new_tools.items():
                self.agent.tools[tool_name] = tool
            return True, f"✅ 插件 {name} 已重新加载"
        else:
            return True, f"❌ 插件 {name} 重新加载失败"

    def cmd_config(self, args: str) -> tuple[bool, str]:
        """显示当前配置"""
        lines = [
            "\n⚙️ 当前配置:\n",
            f"  模型: {self.agent.llm._client.model}",
            f"  流式输出: {'开启' if self.agent.stream else '关闭'}",
            f"  深度思考: {'开启' if self.agent.enable_thinking else '关闭'}",
            f"  并行工具: {'开启' if self.agent.parallel_tools else '关闭'}",
            f"  最大步数: {self.agent.max_steps}",
            f"  Token 限制: {self.agent.token_limit:,}",
            f"  工作目录: {self.agent.workspace_dir}",
            "",
            "  切换选项:",
            "    /stream   - 切换流式输出",
            "    /think    - 切换深度思考",
            "    /parallel - 切换并行工具",
        ]
        return True, "\n".join(lines)

    async def cmd_compact(self, args: str) -> tuple[bool, str]:
        """手动压缩对话历史"""
        before_tokens = self.agent._estimate_tokens()
        before_messages = len(self.agent.messages)

        # 强制触发摘要
        old_limit = self.agent.token_limit
        self.agent.token_limit = 0  # 临时设为 0 触发摘要
        await self.agent._summarize_messages()
        self.agent.token_limit = old_limit

        after_tokens = self.agent._estimate_tokens()
        after_messages = len(self.agent.messages)

        return True, (
            f"✅ 对话历史已压缩\n"
            f"   消息: {before_messages} → {after_messages}\n"
            f"   Token: {before_tokens:,} → {after_tokens:,}"
        )

    def cmd_status(self, args: str) -> tuple[bool, str]:
        """显示系统状态"""
        import platform

        lines = [
            "\n📊 系统状态:\n",
            f"  Python: {platform.python_version()}",
            f"  系统: {platform.system()} {platform.release()}",
            "",
            "  Agent 状态:",
            f"    消息数: {len(self.agent.messages)}",
            f"    工具数: {len(self.agent.tools)}",
            f"    Token 使用: {self.agent._estimate_tokens():,} / {self.agent.token_limit:,}",
            "",
            "  会话:",
            f"    当前会话: {self.session_mgr.current_session or '未保存'}",
            f"    保存会话数: {len(self.session_mgr.list_sessions())}",
        ]

        if self.plugin_mgr:
            plugin_count = len(self.plugin_mgr.get_loaded_tools())
            lines.append(f"    插件工具数: {plugin_count}")

        return True, "\n".join(lines)

    def cmd_copy(self, args: str) -> tuple[bool, str]:
        """复制最后一条回复到剪贴板"""
        # 找到最后一条 assistant 消息
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.content:
                try:
                    import subprocess
                    # macOS
                    process = subprocess.Popen(
                        ["pbcopy"],
                        stdin=subprocess.PIPE,
                    )
                    process.communicate(msg.content.encode("utf-8"))
                    return True, "✅ 已复制到剪贴板"
                except Exception:
                    try:
                        # Linux (xclip)
                        process = subprocess.Popen(
                            ["xclip", "-selection", "clipboard"],
                            stdin=subprocess.PIPE,
                        )
                        process.communicate(msg.content.encode("utf-8"))
                        return True, "✅ 已复制到剪贴板"
                    except Exception:
                        return True, "❌ 无法访问剪贴板"

        return True, "❌ 没有可复制的回复"

    def cmd_undo(self, args: str) -> tuple[bool, str]:
        """撤销最后一轮对话"""
        # 找到最后一条 user 消息的位置
        user_idx = -1
        for i in range(len(self.agent.messages) - 1, -1, -1):
            if self.agent.messages[i].role == "user":
                user_idx = i
                break

        if user_idx <= 0:  # 0 是 system 消息
            return True, "❌ 没有可撤销的对话"

        # 删除从 user 消息开始的所有消息
        removed = len(self.agent.messages) - user_idx
        self.agent.messages = self.agent.messages[:user_idx]

        return True, f"✅ 已撤销 {removed} 条消息"

    def cmd_retry(self, args: str) -> tuple[bool, str]:
        """重试最后一次请求"""
        # 找到最后一条 user 消息
        for i in range(len(self.agent.messages) - 1, -1, -1):
            if self.agent.messages[i].role == "user":
                user_msg = self.agent.messages[i].content
                # 删除这条消息之后的所有消息
                self.agent.messages = self.agent.messages[:i]
                return True, f"🔄 重试: {user_msg[:50]}..."

        return True, "❌ 没有可重试的请求"

    async def cmd_lint(self, args: str) -> tuple[bool, str]:
        """对文件运行 lint 检查 (用法: /lint <文件路径>)"""
        if not args:
            return True, "用法: /lint <文件路径>"

        from .feedback import FeedbackConfig, FeedbackLoop

        file_path = args.strip()
        feedback = FeedbackLoop(
            self.agent.workspace_dir,
            FeedbackConfig(auto_lint=True, auto_test=False)
        )

        result = await feedback.lint_file(file_path)

        if result.success:
            return True, f"✅ Lint 检查通过: {file_path}"
        else:
            lines = [f"❌ Lint 检查失败: {file_path}"]
            if result.errors:
                lines.append("\n错误:")
                for err in result.errors[:5]:
                    lines.append(f"  • {err}")
            return True, "\n".join(lines)

    async def cmd_test(self, args: str) -> tuple[bool, str]:
        """运行测试 (用法: /test [文件路径])"""
        from .feedback import FeedbackConfig, FeedbackLoop

        file_path = args.strip() if args else None
        feedback = FeedbackLoop(
            self.agent.workspace_dir,
            FeedbackConfig(auto_lint=False, auto_test=True)
        )

        result = await feedback.run_tests(file_path)

        if result.success:
            return True, f"✅ 测试通过: {result.passed} 个测试"
        else:
            lines = [f"❌ 测试失败: {result.failed} 个失败, {result.passed} 个通过"]
            if result.errors:
                lines.append("\n错误:")
                for err in result.errors[:5]:
                    lines.append(f"  • {err}")
            return True, "\n".join(lines)

    def cmd_profiles(self, args: str) -> tuple[bool, str]:
        """列出所有配置 profiles"""
        from .profiles import ProfileManager

        mgr = ProfileManager()
        profiles = mgr.list_profiles()

        if not profiles:
            return True, "📭 暂无保存的 profiles\n\n使用 /profile-new <名称> 创建"

        lines = ["\\n📋 可用 Profiles:\\n"]
        for name in profiles:
            try:
                config = mgr.load_profile(name)
                lines.append(f"  • {name}: {config.description or '无描述'}")
            except Exception:
                lines.append(f"  • {name}: (加载失败)")

        return True, "\n".join(lines)

    def cmd_profile(self, args: str) -> tuple[bool, str]:
        """切换或显示当前 profile (用法: /profile [名称])"""
        from .profiles import ProfileManager

        mgr = ProfileManager()

        if not args:
            current = mgr.get_current_profile()
            if current:
                return True, f"📋 当前 Profile: {current.name}"
            return True, "📋 未设置 Profile"

        name = args.strip()
        try:
            mgr.set_current_profile(name)
            return True, f"✅ 已切换到 Profile: {name}"
        except ValueError as e:
            return True, f"❌ {e}"

    def cmd_safe(self, args: str) -> tuple[bool, str]:
        """切换安全模式（需要确认所有操作）"""
        # 这里需要集成 PermissionManager
        return True, "⚠️ 安全模式功能开发中"

    def cmd_autolint(self, args: str) -> tuple[bool, str]:
        """切换自动 lint 检查"""
        # 需要在 agent 中添加 feedback_loop 属性
        return True, "⚠️ 自动 lint 功能开发中"

    # ==================== 自定义命令 ====================

    def cmd_commands(self, args: str) -> tuple[bool, str]:
        """列出所有自定义命令"""
        commands = self.custom_cmd_mgr.list_commands()

        if not commands:
            lines = [
                "\n📜 自定义命令",
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
            return True, "\n".join(lines)

        # 按来源分组
        user_cmds = [c for c in commands if c.source == "user"]
        project_cmds = [c for c in commands if c.source == "project"]

        lines = ["\n📜 自定义命令:\n"]

        if user_cmds:
            lines.append("  用户命令:")
            for cmd in user_cmds:
                desc = cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                args_hint = f" ({len(cmd.arguments)} 参数)" if cmd.arguments else ""
                lines.append(f"    • {cmd.id}{args_hint}")
                if desc:
                    lines.append(f"      {desc}")

        if project_cmds:
            if user_cmds:
                lines.append("")
            lines.append("  项目命令:")
            for cmd in project_cmds:
                desc = cmd.description[:40] + "..." if len(cmd.description) > 40 else cmd.description
                args_hint = f" ({len(cmd.arguments)} 参数)" if cmd.arguments else ""
                lines.append(f"    • {cmd.id}{args_hint}")
                if desc:
                    lines.append(f"      {desc}")

        lines.append("")
        lines.append("  执行命令: /run <命令ID>")

        return True, "\n".join(lines)

    async def cmd_run(self, args: str) -> tuple[bool, str]:
        """执行自定义命令 (用法: /run <命令ID>)"""
        if not args:
            return True, "用法: /run <命令ID>\n\n使用 /commands 查看可用命令"

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
            return True, f"❌ 未找到命令: {cmd_id}\n\n使用 /commands 查看可用命令"

        # 执行命令
        should_continue, content = await self.custom_cmd_executor.execute(cmd.id)

        # 返回内容作为要发送给 AI 的提示
        return should_continue, f"__CUSTOM_CMD__:{content}"

    def cmd_cmd_new(self, args: str) -> tuple[bool, str]:
        """创建用户自定义命令 (用法: /cmd-new <名称>)"""
        if not args:
            return True, "用法: /cmd-new <命令名称>\n\n示例: /cmd-new review-code"

        name = args.strip().lower().replace(" ", "-")
        file_path = self.custom_cmd_mgr.create_command_template(name, source="user")

        return True, (
            f"✅ 命令模板已创建: {file_path}\n\n"
            f"编辑文件后使用 /run user:{name} 执行\n"
            f"或使用 /cmd-reload 重新加载命令列表"
        )

    def cmd_cmd_new_project(self, args: str) -> tuple[bool, str]:
        """创建项目自定义命令 (用法: /cmd-new-project <名称>)"""
        if not args:
            return True, "用法: /cmd-new-project <命令名称>\n\n示例: /cmd-new-project deploy"

        name = args.strip().lower().replace(" ", "-")
        file_path = self.custom_cmd_mgr.create_command_template(name, source="project")

        return True, (
            f"✅ 项目命令模板已创建: {file_path}\n\n"
            f"编辑文件后使用 /run project:{name} 执行\n"
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
            f"\n📜 命令: {cmd.id}",
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

        return True, "\n".join(lines)

    def completions_run(self) -> list[str]:
        """run 命令的补全"""
        commands = self.custom_cmd_mgr.list_commands()
        return [cmd.id for cmd in commands]

    def completions_cmd_show(self) -> list[str]:
        """cmd-show 命令的补全"""
        return self.completions_run()


