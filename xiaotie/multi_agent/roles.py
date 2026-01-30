"""Agent 角色定义

定义不同类型的 Agent 角色，每个角色有特定的能力和工具集。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentRole(Enum):
    """Agent 角色类型"""

    # 主 Agent - 完整工具集
    MAIN = "main"

    # 任务 Agent - 只读工具集 (用于探索和搜索)
    TASK = "task"

    # 代码分析 Agent - 代码理解和分析
    ANALYZER = "analyzer"

    # 测试 Agent - 测试执行和验证
    TESTER = "tester"

    # 文档 Agent - 文档生成和更新
    DOCUMENTER = "documenter"


@dataclass
class RoleConfig:
    """角色配置"""

    role: AgentRole
    name: str
    description: str

    # 允许的工具列表 (None 表示所有工具)
    allowed_tools: Optional[list[str]] = None

    # 禁止的工具列表
    forbidden_tools: list[str] = field(default_factory=list)

    # 系统提示词前缀
    system_prompt_prefix: str = ""

    # 最大迭代次数
    max_iterations: int = 10

    # 是否可以生成子 Agent
    can_spawn_agents: bool = False

    def get_tool_filter(self) -> tuple[Optional[list[str]], list[str]]:
        """获取工具过滤器"""
        return self.allowed_tools, self.forbidden_tools


def create_default_roles() -> dict[AgentRole, RoleConfig]:
    """创建默认角色配置"""
    return {
        AgentRole.MAIN: RoleConfig(
            role=AgentRole.MAIN,
            name="主 Agent",
            description="完整功能的主 Agent，可以执行所有操作",
            allowed_tools=None,  # 所有工具
            forbidden_tools=[],
            system_prompt_prefix="你是一个强大的 AI 编程助手。",
            max_iterations=50,
            can_spawn_agents=True,
        ),
        AgentRole.TASK: RoleConfig(
            role=AgentRole.TASK,
            name="任务 Agent",
            description="用于探索和搜索的只读 Agent",
            allowed_tools=[
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "code_analysis",
            ],
            forbidden_tools=[
                "write_file",
                "edit_file",
                "bash",
                "python",
            ],
            system_prompt_prefix=(
                "你是一个专注于代码探索和搜索的 Agent。" "你只能读取和分析代码，不能修改任何文件。"
            ),
            max_iterations=10,
            can_spawn_agents=False,
        ),
        AgentRole.ANALYZER: RoleConfig(
            role=AgentRole.ANALYZER,
            name="分析 Agent",
            description="专注于代码分析和理解",
            allowed_tools=[
                "read_file",
                "glob",
                "grep",
                "list_dir",
                "code_analysis",
                "diagnostics",
            ],
            forbidden_tools=[
                "write_file",
                "edit_file",
                "bash",
            ],
            system_prompt_prefix=(
                "你是一个代码分析专家。" "你的任务是深入理解代码结构、依赖关系和潜在问题。"
            ),
            max_iterations=15,
            can_spawn_agents=False,
        ),
        AgentRole.TESTER: RoleConfig(
            role=AgentRole.TESTER,
            name="测试 Agent",
            description="专注于测试执行和验证",
            allowed_tools=[
                "read_file",
                "glob",
                "grep",
                "bash",
                "python",
            ],
            forbidden_tools=[
                "write_file",
                "edit_file",
            ],
            system_prompt_prefix=(
                "你是一个测试专家。"
                "你的任务是运行测试、分析测试结果并报告问题。"
                "你不能修改代码，只能运行测试命令。"
            ),
            max_iterations=10,
            can_spawn_agents=False,
        ),
        AgentRole.DOCUMENTER: RoleConfig(
            role=AgentRole.DOCUMENTER,
            name="文档 Agent",
            description="专注于文档生成和更新",
            allowed_tools=[
                "read_file",
                "write_file",
                "glob",
                "grep",
            ],
            forbidden_tools=[
                "bash",
                "python",
                "edit_file",
            ],
            system_prompt_prefix=(
                "你是一个文档专家。"
                "你的任务是生成和更新项目文档。"
                "你只能创建和修改文档文件 (*.md, *.rst, *.txt)。"
            ),
            max_iterations=10,
            can_spawn_agents=False,
        ),
    }
