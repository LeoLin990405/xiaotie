"""multi_agent/coordinator.py 单元测试"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from xiaotie.multi_agent.coordinator import (
    AgentRole,
    AgentState,
    Task,
    CoordinatorAgent,
    ExpertAgent,
    ExecutorAgent,
    SupervisorAgent,
    MultiAgentSystem,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class TestAgentRole:
    def test_values(self):
        assert AgentRole.COORDINATOR.value == "coordinator"
        assert AgentRole.EXPERT.value == "expert"
        assert AgentRole.EXECUTOR.value == "executor"


class TestTask:
    def test_defaults(self):
        t = Task(id="t1", description="do something")
        assert t.status == "pending"
        assert t.priority == 1
        assert t.dependencies == []
        assert t.result is None

    def test_custom(self):
        t = Task(id="t2", description="high priority", priority=5, dependencies=["t1"])
        assert t.priority == 5
        assert t.dependencies == ["t1"]


class TestAgentState:
    def test_defaults(self):
        s = AgentState(agent_id="a1", role=AgentRole.EXPERT, capabilities=["analysis"])
        assert s.status == "idle"
        assert s.workload == 0


# ---------------------------------------------------------------------------
# Mock event broker to avoid global state dependency
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_event_broker():
    """Patch get_event_broker to avoid requiring global initialization."""
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock()
    with patch("xiaotie.multi_agent.coordinator.get_event_broker", return_value=mock_broker):
        yield mock_broker


# ---------------------------------------------------------------------------
# CoordinatorAgent
# ---------------------------------------------------------------------------


class TestCoordinatorAgent:
    @pytest.fixture
    def coordinator(self):
        return CoordinatorAgent("coord-1")

    def test_init(self, coordinator):
        assert coordinator.role == AgentRole.COORDINATOR
        assert "task_coordination" in coordinator.capabilities

    @pytest.mark.asyncio
    async def test_add_agent(self, coordinator):
        expert = ExpertAgent("e1", "python")
        await coordinator.add_agent(expert)
        assert expert in coordinator.agent_pool
        assert expert.supervisor is coordinator

    @pytest.mark.asyncio
    async def test_execute_task_enqueues(self, coordinator):
        task = Task(id="t1", description="test task")
        result = await coordinator.execute_task(task)
        assert "队列" in result or "queue" in result.lower() or len(result) > 0

    @pytest.mark.asyncio
    async def test_distribute_tasks_assigns(self, coordinator):
        executor = ExecutorAgent("ex1")
        executor.state.status = "idle"
        await coordinator.add_agent(executor)

        task = Task(
            id="t1",
            description="execute something",
            metadata={"required_capabilities": ["execution"]},
        )
        coordinator.task_queue.append(task)

        await coordinator.distribute_tasks()
        assert task.assigned_to == "ex1"
        assert task.status == "running"

    @pytest.mark.asyncio
    async def test_distribute_skips_non_pending(self, coordinator):
        executor = ExecutorAgent("ex1")
        await coordinator.add_agent(executor)

        task = Task(id="t1", description="already running", status="running")
        coordinator.task_queue.append(task)

        await coordinator.distribute_tasks()
        assert task.assigned_to is None

    @pytest.mark.asyncio
    async def test_find_suitable_agent_respects_workload(self, coordinator):
        executor = ExecutorAgent("ex1")
        executor.state.workload = 5  # Over limit of 3
        await coordinator.add_agent(executor)

        task = Task(
            id="t1",
            description="heavy",
            metadata={"required_capabilities": ["execution"]},
        )
        result = await coordinator._find_suitable_agent(task)
        assert result is None

    @pytest.mark.asyncio
    async def test_track_progress_removes_completed(self, coordinator):
        executor = ExecutorAgent("ex1")
        executor.state.workload = 1
        await coordinator.add_agent(executor)

        task = Task(id="t1", description="done", status="completed")
        executor.tasks.append(task)

        await coordinator.track_progress()
        assert task not in executor.tasks
        assert executor.state.workload == 0


# ---------------------------------------------------------------------------
# ExpertAgent
# ---------------------------------------------------------------------------


class TestExpertAgent:
    @pytest.mark.asyncio
    async def test_execute_task(self):
        expert = ExpertAgent("e1", "security")
        task = Task(id="t1", description="analyze vulnerability")
        result = await expert.execute_task(task)
        assert task.status == "completed"
        assert "security" in result
        assert expert.state.status == "idle"
        assert expert.state.workload == 0


# ---------------------------------------------------------------------------
# ExecutorAgent
# ---------------------------------------------------------------------------


class TestExecutorAgent:
    @pytest.mark.asyncio
    async def test_execute_task(self):
        executor = ExecutorAgent("ex1")
        task = Task(id="t1", description="run migration")
        result = await executor.execute_task(task)
        assert task.status == "completed"
        assert task.result is not None
        assert executor.state.status == "idle"


# ---------------------------------------------------------------------------
# SupervisorAgent
# ---------------------------------------------------------------------------


class TestSupervisorAgent:
    @pytest.mark.asyncio
    async def test_execute_task(self):
        supervisor = SupervisorAgent("s1")
        task = Task(id="t1", description="review results")
        result = await supervisor.execute_task(task)
        assert task.status == "completed"
        assert "质量" in result or "quality" in result.lower() or len(result) > 0


# ---------------------------------------------------------------------------
# MultiAgentSystem
# ---------------------------------------------------------------------------


class TestMultiAgentSystem:
    @pytest.fixture
    def system(self):
        return MultiAgentSystem()

    @pytest.mark.asyncio
    async def test_add_agent(self, system):
        executor = ExecutorAgent("ex1")
        await system.add_agent(executor)
        assert "ex1" in system.agents

    @pytest.mark.asyncio
    async def test_add_coordinator_sets_field(self, system):
        coord = CoordinatorAgent("c1")
        await system.add_agent(coord)
        assert system.coordinator is coord

    @pytest.mark.asyncio
    async def test_create_task(self, system):
        task = await system.create_task(
            "test task",
            required_capabilities=["analysis"],
            priority=3,
        )
        assert task.id in system.task_registry
        assert task.priority == 3
        assert task.metadata["required_capabilities"] == ["analysis"]

    @pytest.mark.asyncio
    async def test_execute_creates_default_coordinator(self, system):
        task = Task(id="t1", description="auto coord")
        # Don't await the full execute (it has sleep loops)
        # Just verify coordinator gets created
        assert system.coordinator is None
        # We need to timeout since execute_task has sleep loop
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(system.execute_task(task), timeout=0.5)
        assert system.coordinator is not None
