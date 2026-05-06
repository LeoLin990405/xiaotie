"""
Commands Main Entry point.
Dynamically constructs the Commands class using multiple inheritance (Mixins).
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from xiaotie.agent import Agent
    from xiaotie.plugins import PluginManager
    from xiaotie.session import SessionManager

from xiaotie.custom_commands import CustomCommandExecutor, CustomCommandManager

from .base import CommandsBase
from .custom import CustomCommandsMixin
from .metrics import MetricsCommandsMixin
from .plugins import PluginsCommandsMixin
from .profiles import ProfilesCommandsMixin
from .quality import QualityCommandsMixin
from .secret_cmd import SecretCommands
from .session import SessionCommandsMixin
from .system import AgentOpsMixin, SystemCommandsMixin
from .workspace import WorkspaceCommandsMixin

__all__ = ["Commands", "CommandsBase"]


class Commands(
    SystemCommandsMixin,
    AgentOpsMixin,
    SessionCommandsMixin,
    WorkspaceCommandsMixin,
    PluginsCommandsMixin,
    MetricsCommandsMixin,
    QualityCommandsMixin,
    ProfilesCommandsMixin,
    CustomCommandsMixin,
    SecretCommands,
):
    """
    命令管理器

    This class combines all the specific command domain mixins.
    """

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

        # Merge aliases from all base classes
        self.ALIASES = {}
        for base in reversed(self.__class__.__mro__):
            if hasattr(base, "ALIASES") and isinstance(base.ALIASES, dict):
                self.ALIASES.update(base.ALIASES)

        self._commands = self._discover_commands()

        # 自定义命令系统
        self.custom_cmd_mgr = CustomCommandManager(agent.workspace_dir)
        self.custom_cmd_executor = CustomCommandExecutor(
            self.custom_cmd_mgr,
            input_callback=input_callback,
        )

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


__all__ = ["Commands"]
