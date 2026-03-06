"""
System and Agent operations commands Mixin.
"""

from .base import CommandsBase

class SystemCommandsMixin(CommandsBase):
    """System related commands like help, quit, list, config"""
    
    ALIASES = {
        "?": "help",
        "h": "help",
        "q": "quit",
        "exit": "quit",
        "c": "clear",
        "cfg": "config",
        "t": "tools",
        "tok": "tokens",
    }
    
    def cmd_help(self, args: str) -> tuple[bool, str]:
        """显示帮助信息"""
        lines = ["\\n📖 可用命令:\\n"]
        for name, desc in self.list_commands():
            lines.append(f"  /{name:12} - {desc}")

        # 显示自定义命令数量
        if hasattr(self, "custom_cmd_mgr"):
            custom_cmds = self.custom_cmd_mgr.list_commands()
            if custom_cmds:
                lines.append(f"\\n📜 自定义命令: {len(custom_cmds)} 个 (使用 /commands 查看)")

        lines.append("\\n💡 提示: 命令支持前缀匹配，如 /h 等同于 /help")
        return True, "\\n".join(lines)

    def cmd_quit(self, args: str) -> tuple[bool, str]:
        """退出程序"""
        # 自动保存会话
        if hasattr(self, "session_mgr") and self.session_mgr.current_session:
            self.session_mgr.save_session(self.session_mgr.current_session, self.agent.messages)
        if hasattr(self, "on_quit") and self.on_quit:
            self.on_quit()
        return False, "\\n👋 再见！"
        
    def cmd_clear(self, args: str) -> tuple[bool, str]:
        """清屏"""
        print("\\033[2J\\033[H", end="")
        return True, ""
        
    def cmd_tools(self, args: str) -> tuple[bool, str]:
        """显示可用工具"""
        lines = ["\\n🔧 可用工具:\\n"]
        for name, tool in self.agent.tools.items():
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            lines.append(f"  • {name}: {desc}")
        return True, "\\n".join(lines)
        
    def cmd_tokens(self, args: str) -> tuple[bool, str]:
        """显示 Token 使用情况"""
        estimated = self.agent._estimate_tokens()
        api_total = self.agent.api_total_tokens
        limit = self.agent.token_limit

        lines = [
            "\\n📊 Token 使用情况:\\n",
            f"  估算消息 Token: {estimated:,}",
            f"  API 累计 Token: {api_total:,}",
            f"  Token 限制: {limit:,}",
            f"  使用率: {max(estimated, api_total) / limit * 100:.1f}%",
        ]
        return True, "\\n".join(lines)
        
    def cmd_model(self, args: str) -> tuple[bool, str]:
        """显示或切换模型 (用法: /model [模型名])"""
        if not args:
            return True, f"📊 当前模型: {self.agent.llm._client.model}"

        new_model = args.strip()
        self.agent.llm.model = new_model
        if hasattr(self.agent.llm, "_client"):
            self.agent.llm._client.model = new_model
        if hasattr(self.agent, "config") and hasattr(self.agent.config, "llm"):
            self.agent.config.llm.model = new_model
            
        return True, f"✅ 已切换到模型: {new_model}"
        
    def cmd_config(self, args: str) -> tuple[bool, str]:
        """显示当前配置"""
        lines = [
            "\\n⚙️ 当前配置:\\n",
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
        return True, "\\n".join(lines)
        
    def cmd_status(self, args: str) -> tuple[bool, str]:
        """显示系统状态"""
        import platform

        lines = [
            "\\n📊 系统状态:\\n",
            f"  Python: {platform.python_version()}",
            f"  系统: {platform.system()} {platform.release()}",
            "",
            "  Agent 状态:",
            f"    消息数: {len(self.agent.messages)}",
            f"    工具数: {len(self.agent.tools)}",
            f"    Token 使用: {self.agent._estimate_tokens():,} / {self.agent.token_limit:,}",
            "",
            "  会话:",
            f"    当前会话: {self.session_mgr.current_session if hasattr(self, 'session_mgr') and self.session_mgr.current_session else '未保存'}",
        ]
        
        if hasattr(self, "session_mgr"):
            lines.append(f"    保存会话数: {len(self.session_mgr.list_sessions())}")

        if hasattr(self, "plugin_mgr") and self.plugin_mgr:
            plugin_count = len(self.plugin_mgr.get_loaded_tools())
            lines.append(f"    插件工具数: {plugin_count}")

        return True, "\\n".join(lines)


class AgentOpsMixin(CommandsBase):
    """Commands related to agent manipulation like undo, retry, stream, parallel, etc"""
    
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
        self.agent.config.parallel_tools = self.agent.parallel_tools
        status = "开启" if self.agent.parallel_tools else "关闭"
        return True, f"✅ 工具并行执行已{status}"
        
    def cmd_copy(self, args: str) -> tuple[bool, str]:
        """复制最后一条回复到剪贴板"""
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
        user_idx = -1
        for i in range(len(self.agent.messages) - 1, -1, -1):
            if self.agent.messages[i].role == "user":
                user_idx = i
                break

        if user_idx <= 0:  # 0 是 system 消息
            return True, "❌ 没有可撤销的对话"

        removed = len(self.agent.messages) - user_idx
        self.agent.messages = self.agent.messages[:user_idx]

        return True, f"✅ 已撤销 {removed} 条消息"
        
    def cmd_retry(self, args: str) -> tuple[bool, str]:
        """重试最后一次请求"""
        for i in range(len(self.agent.messages) - 1, -1, -1):
            if self.agent.messages[i].role == "user":
                user_msg = self.agent.messages[i].content
                self.agent.messages = self.agent.messages[:i]
                return True, f"🔄 重试: {user_msg[:50]}..."

        return True, "❌ 没有可重试的请求"
