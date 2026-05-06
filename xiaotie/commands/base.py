"""
Base classes and generic handlers for the Commands module.
"""

from typing import Callable, Optional


class CommandsBase:
    """
    Base mixin for command definitions.
    Defines the shape expected by the dynamic `Commands` class.
    """

    # Aliases should be merged by the main class, subclasses can define their own ALIASES
    ALIASES = {}

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
        main_aliases = getattr(self, "ALIASES", {})
        name = main_aliases.get(name, name)

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
