"""增强输入模块

参考 OpenCode 的交互设计：
- 命令自动补全
- 历史记录
- 多行输入支持
- 语法高亮
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .commands import Commands

# 尝试导入 prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    # 定义占位类
    Completer = object
    Completion = None


class CommandCompleter(Completer if HAS_PROMPT_TOOLKIT else object):
    """命令自动补全器"""

    def __init__(self, commands: "Commands"):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # 只在输入 / 开头时补全命令
        if text.startswith("/"):
            cmd_text = text[1:]  # 去掉 /
            parts = cmd_text.split(maxsplit=1)
            cmd_name = parts[0] if parts else ""

            # 补全命令名
            if len(parts) <= 1:
                for name, _ in self.commands.list_commands():
                    if name.startswith(cmd_name):
                        yield Completion(
                            name,
                            start_position=-len(cmd_name),
                            display=f"/{name}",
                            display_meta=self._get_cmd_desc(name),
                        )
            else:
                # 补全命令参数
                completions = self.commands.get_completions(cmd_name)
                arg_text = parts[1] if len(parts) > 1 else ""
                for comp in completions:
                    if comp.startswith(arg_text):
                        yield Completion(
                            comp,
                            start_position=-len(arg_text),
                        )

    def _get_cmd_desc(self, name: str) -> str:
        """获取命令描述"""
        for cmd_name, desc in self.commands.list_commands():
            if cmd_name == name:
                return desc[:30]
        return ""


class EnhancedInput:
    """增强输入处理器"""

    def __init__(
        self,
        commands: Optional["Commands"] = None,
        history_file: Optional[str] = None,
    ):
        self.commands = commands
        self.use_prompt_toolkit = HAS_PROMPT_TOOLKIT

        if self.use_prompt_toolkit:
            # 历史文件
            if history_file is None:
                history_dir = Path.home() / ".xiaotie"
                history_dir.mkdir(exist_ok=True)
                history_file = str(history_dir / "history")

            # 样式
            self.style = Style.from_dict({
                "prompt": "#00aa00 bold",
                "prompt.user": "#00aaff bold",
            })

            # 创建会话
            self.session: PromptSession = PromptSession(
                history=FileHistory(history_file),
                auto_suggest=AutoSuggestFromHistory(),
                completer=CommandCompleter(commands) if commands else None,
                style=self.style,
                multiline=False,
                enable_history_search=True,
            )

            # 快捷键
            self.bindings = KeyBindings()
            self._setup_keybindings()
        else:
            self.session = None

    def _setup_keybindings(self):
        """设置快捷键"""
        if not self.use_prompt_toolkit:
            return

        @self.bindings.add("c-l")
        def clear_screen(event):
            """Ctrl+L 清屏"""
            print("\033[2J\033[H", end="")
            event.app.renderer.reset()

    def prompt(self, message: str = "👤 你: ") -> str:
        """获取用户输入（同步版本，不能在 async 上下文中使用）"""
        if self.use_prompt_toolkit:
            try:
                return self.session.prompt(
                    HTML(f"<prompt.user>{message}</prompt.user>"),
                    key_bindings=self.bindings,
                )
            except (EOFError, KeyboardInterrupt):
                raise
        else:
            return input(message)

    async def prompt_async(self, message: str = "👤 你: ") -> str:
        """获取用户输入（异步版本，用于 async 上下文）"""
        if self.use_prompt_toolkit:
            try:
                return await self.session.prompt_async(
                    HTML(f"<prompt.user>{message}</prompt.user>"),
                    key_bindings=self.bindings,
                )
            except (EOFError, KeyboardInterrupt):
                raise
        else:
            # 在异步上下文中使用 run_in_executor 运行同步 input
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: input(message))

    def multiline_prompt(self, message: str = "👤 你: ") -> str:
        """多行输入（以空行结束）"""
        if self.use_prompt_toolkit:
            try:
                # 临时启用多行模式
                return self.session.prompt(
                    HTML(f"<prompt.user>{message}</prompt.user>"),
                    multiline=True,
                    key_bindings=self.bindings,
                )
            except (EOFError, KeyboardInterrupt):
                raise
        else:
            lines = []
            print(message, end="")
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                except EOFError:
                    break
            return "\n".join(lines)

    async def multiline_prompt_async(self, message: str = "👤 你: ") -> str:
        """多行输入（异步版本）"""
        if self.use_prompt_toolkit:
            try:
                return await self.session.prompt_async(
                    HTML(f"<prompt.user>{message}</prompt.user>"),
                    multiline=True,
                    key_bindings=self.bindings,
                )
            except (EOFError, KeyboardInterrupt):
                raise
        else:
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_multiline_input, message)

    def _sync_multiline_input(self, message: str) -> str:
        """同步多行输入辅助方法"""
        lines = []
        print(message, end="")
        while True:
            try:
                line = input()
                if not line:
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)


def create_input(commands: Optional["Commands"] = None) -> EnhancedInput:
    """创建输入处理器"""
    return EnhancedInput(commands=commands)
