"""多 Agent 协作测试"""

import pytest
from xiaotie.multi_agent import (
    AgentCoordinator,
    TaskResult,
    AgentRole,
    RoleConfig,
    create_default_roles,
    TaskAgent,
    TaskAgentConfig,
    AgentTool,
)


class TestAgentRole:
    """AgentRole 测试"""

    def test_role_values(self):
        """测试角色值"""
        assert AgentRole.MAIN.value == "main"
        assert AgentRole.TASK.value == "task"
        assert AgentRole.ANALYZER.value == "analyzer"
        assert AgentRole.TESTER.value == "tester"
        assert AgentRole.DOCUMENTER.value == "documenter"


class TestRoleConfig:
    """RoleConfig 测试"""

    def test_create_role_config(self):
        """测试创建角色配置"""
        config = RoleConfig(
            role=AgentRole.TASK,
            name="测试角色",
            description="测试描述",
            allowed_tools=["read_file", "glob"],
            max_iterations=5,
        )
        assert config.role == AgentRole.TASK
        assert config.name == "测试角色"
        assert "read_file" in config.allowed_tools
        assert config.max_iterations == 5

    def test_default_roles(self):
        """测试默认角色"""
        roles = create_default_roles()
        assert AgentRole.MAIN in roles
        assert AgentRole.TASK in roles
        assert AgentRole.ANALYZER in roles

        # 主 Agent 可以生成子 Agent
        assert roles[AgentRole.MAIN].can_spawn_agents is True

        # 任务 Agent 不能生成子 Agent
        assert roles[AgentRole.TASK].can_spawn_agents is False


class TestTaskAgentConfig:
    """TaskAgentConfig 测试"""

    def test_create_config(self):
        """测试创建配置"""
        config = TaskAgentConfig(
            parent_id="parent-123",
            prompt="搜索所有 Python 文件",
        )
        assert config.parent_id == "parent-123"
        assert config.prompt == "搜索所有 Python 文件"
        assert "read_file" in config.allowed_tools

    def test_config_defaults(self):
        """测试配置默认值"""
        config = TaskAgentConfig(
            parent_id="parent",
            prompt="test",
        )
        assert config.max_iterations == 10
        assert config.timeout == 300.0


class TestTaskResult:
    """TaskResult 测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = TaskResult(
            task_id="task-123",
            success=True,
            content="找到 10 个文件",
        )
        assert result.success is True
        assert result.task_id == "task-123"
        assert "10 个文件" in result.content

    def test_failure_result(self):
        """测试失败结果"""
        result = TaskResult(
            task_id="task-456",
            success=False,
            content="",
            error="任务超时",
        )
        assert result.success is False
        assert result.error == "任务超时"


class TestAgentTool:
    """AgentTool 测试"""

    def test_tool_properties(self):
        """测试工具属性"""
        tool = AgentTool()
        assert tool.name == "agent"
        assert "探索" in tool.description or "Agent" in tool.description
        assert "prompt" in tool.parameters["properties"]

    @pytest.mark.asyncio
    async def test_execute_without_coordinator(self):
        """测试无协调器时执行"""
        tool = AgentTool()
        result = await tool.execute(prompt="测试任务")
        assert result.success is False
        assert "未初始化" in result.error


class TestAgentCoordinator:
    """AgentCoordinator 测试"""

    def test_create_coordinator(self):
        """测试创建协调器"""
        coordinator = AgentCoordinator(
            llm_client=None,
            tools=[],
        )
        assert coordinator is not None
        assert coordinator.max_concurrent_agents == 5

    def test_get_total_tokens(self):
        """测试获取 token 统计"""
        coordinator = AgentCoordinator(
            llm_client=None,
            tools=[],
        )
        tokens = coordinator.get_total_tokens()
        assert "prompt" in tokens
        assert "completion" in tokens

    def test_list_tasks(self):
        """测试列出任务"""
        coordinator = AgentCoordinator(
            llm_client=None,
            tools=[],
        )
        tasks = coordinator.list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) == 0

    def test_list_active_agents(self):
        """测试列出活跃 Agent"""
        coordinator = AgentCoordinator(
            llm_client=None,
            tools=[],
        )
        agents = coordinator.list_active_agents()
        assert isinstance(agents, list)
        assert len(agents) == 0
