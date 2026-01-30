"""自定义命令系统

学习自 OpenCode 的自定义命令设计：
- 用户命令: ~/.xiaotie/commands/ 或 ~/.config/xiaotie/commands/
- 项目命令: <PROJECT>/.xiaotie/commands/
- 支持 Markdown 文件定义命令
- 支持命名参数 $ARG_NAME
- 支持子目录组织命令
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class CustomCommand:
    """自定义命令"""
    id: str                          # 命令 ID (如 user:git:commit)
    name: str                        # 命令名称 (如 commit)
    source: str                      # 来源 (user/project)
    file_path: Path                  # 文件路径
    content: str                     # 命令内容
    description: str = ""            # 描述 (从文件第一行提取)
    arguments: list[str] = field(default_factory=list)  # 参数列表

    @property
    def display_name(self) -> str:
        """显示名称"""
        return f"{self.source}:{self.name}"


class CustomCommandManager:
    """自定义命令管理器"""

    # 参数模式: $NAME (大写字母、数字、下划线，必须以字母开头)
    ARG_PATTERN = re.compile(r'\$([A-Z][A-Z0-9_]*)')

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self._commands: dict[str, CustomCommand] = {}
        self._loaded = False

    @property
    def user_command_dirs(self) -> list[Path]:
        """用户命令目录列表"""
        dirs = []

        # XDG_CONFIG_HOME/xiaotie/commands/
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            dirs.append(Path(xdg_config) / "xiaotie" / "commands")

        # ~/.config/xiaotie/commands/
        home = Path.home()
        dirs.append(home / ".config" / "xiaotie" / "commands")

        # ~/.xiaotie/commands/
        dirs.append(home / ".xiaotie" / "commands")

        return dirs

    @property
    def project_command_dir(self) -> Path:
        """项目命令目录"""
        return self.workspace_dir / ".xiaotie" / "commands"

    def discover_commands(self) -> dict[str, CustomCommand]:
        """发现所有自定义命令"""
        if self._loaded:
            return self._commands

        self._commands = {}

        # 加载用户命令
        for cmd_dir in self.user_command_dirs:
            if cmd_dir.exists():
                self._load_commands_from_dir(cmd_dir, "user")
                break  # 只使用第一个存在的目录

        # 加载项目命令
        if self.project_command_dir.exists():
            self._load_commands_from_dir(self.project_command_dir, "project")

        self._loaded = True
        return self._commands

    def _load_commands_from_dir(self, cmd_dir: Path, source: str) -> None:
        """从目录加载命令"""
        for md_file in cmd_dir.rglob("*.md"):
            try:
                cmd = self._load_command_file(md_file, cmd_dir, source)
                if cmd:
                    self._commands[cmd.id] = cmd
            except Exception as e:
                print(f"警告: 加载命令失败 {md_file}: {e}")

    def _load_command_file(
        self, file_path: Path, base_dir: Path, source: str
    ) -> Optional[CustomCommand]:
        """加载单个命令文件"""
        content = file_path.read_text(encoding="utf-8")

        # 计算命令名称 (相对路径，去掉 .md 后缀)
        rel_path = file_path.relative_to(base_dir)
        name_parts = list(rel_path.parts)
        name_parts[-1] = name_parts[-1][:-3]  # 去掉 .md
        name = ":".join(name_parts)

        # 命令 ID
        cmd_id = f"{source}:{name}"

        # 提取描述 (第一行非空内容)
        description = ""
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                description = line[:80]
                break
            elif line.startswith("# "):
                description = line[2:80]
                break

        # 提取参数
        arguments = list(set(self.ARG_PATTERN.findall(content)))

        return CustomCommand(
            id=cmd_id,
            name=name,
            source=source,
            file_path=file_path,
            content=content,
            description=description,
            arguments=arguments,
        )

    def get_command(self, cmd_id: str) -> Optional[CustomCommand]:
        """获取命令"""
        self.discover_commands()
        return self._commands.get(cmd_id)

    def list_commands(self) -> list[CustomCommand]:
        """列出所有命令"""
        self.discover_commands()
        return list(self._commands.values())

    def execute_command(
        self,
        cmd: CustomCommand,
        arg_values: Optional[dict[str, str]] = None,
    ) -> str:
        """执行命令，返回替换参数后的内容"""
        content = cmd.content
        arg_values = arg_values or {}

        # 替换参数
        for arg_name in cmd.arguments:
            value = arg_values.get(arg_name, "")
            content = content.replace(f"${arg_name}", value)

        return content

    def reload(self) -> None:
        """重新加载命令"""
        self._loaded = False
        self._commands = {}
        self.discover_commands()

    def create_command_template(
        self,
        name: str,
        source: str = "user",
        content: Optional[str] = None,
    ) -> Path:
        """创建命令模板"""
        if source == "user":
            # 使用第一个用户命令目录
            cmd_dir = self.user_command_dirs[0]
        else:
            cmd_dir = self.project_command_dir

        cmd_dir.mkdir(parents=True, exist_ok=True)

        # 处理子目录
        parts = name.split(":")
        if len(parts) > 1:
            sub_dir = cmd_dir / "/".join(parts[:-1])
            sub_dir.mkdir(parents=True, exist_ok=True)
            file_path = sub_dir / f"{parts[-1]}.md"
        else:
            file_path = cmd_dir / f"{name}.md"

        # 默认模板
        if content is None:
            content = f"""# {name.replace(":", " ").title()} 命令

这是一个自定义命令模板。

## 使用方法

编辑此文件，添加你想要发送给 AI 的提示内容。

## 参数示例

你可以使用命名参数，如 $FILE_PATH 或 $ISSUE_NUMBER。
当执行命令时，系统会提示你输入这些参数的值。

## 示例内容

请分析以下文件: $FILE_PATH

RUN git status
READ README.md
"""

        file_path.write_text(content, encoding="utf-8")
        return file_path


class CustomCommandExecutor:
    """自定义命令执行器 - 集成到 Commands 类"""

    def __init__(
        self,
        manager: CustomCommandManager,
        input_callback: Optional[Callable[[str], str]] = None,
    ):
        self.manager = manager
        self.input_callback = input_callback or self._default_input

    def _default_input(self, prompt: str) -> str:
        """默认输入回调"""
        return input(prompt)

    def collect_arguments(self, cmd: CustomCommand) -> dict[str, str]:
        """收集命令参数"""
        if not cmd.arguments:
            return {}

        print(f"\n📝 命令 '{cmd.display_name}' 需要以下参数:\n")

        arg_values = {}
        for arg_name in cmd.arguments:
            prompt = f"  {arg_name}: "
            value = self.input_callback(prompt)
            arg_values[arg_name] = value

        return arg_values

    async def execute(self, cmd_id: str) -> tuple[bool, str]:
        """执行自定义命令

        Returns:
            (should_continue, prompt_content): 是否继续，要发送的提示内容
        """
        cmd = self.manager.get_command(cmd_id)
        if not cmd:
            return True, f"❌ 未找到命令: {cmd_id}"

        # 收集参数
        arg_values = self.collect_arguments(cmd)

        # 执行命令
        content = self.manager.execute_command(cmd, arg_values)

        return True, content
