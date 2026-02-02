"""
Agent 编排模块测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from xiaotie.orchestrator import (
    Step,
    StepResult,
    StepStatus,
    WorkflowResult,
    Pipeline,
    Parallel,
    Router,
    Orchestrator,
    pipeline,
    parallel,
    router,
    OrchestrationError,
)


# 测试用的 mock agent
async def echo_agent(input_data):
    """回显 agent"""
    return f"echo: {input_data}"


async def upper_agent(input_data):
    """大写 agent"""
    return str(input_data).upper()


async def error_agent(input_data):
    """错误 agent"""
    raise ValueError("Test error")


async def slow_agent(input_data):
    """慢速 agent"""
    await asyncio.sleep(0.1)
    return f"slow: {input_data}"


async def counter_agent(input_data):
    """计数 agent"""
    return len(str(input_data))


class TestStepResult:
    """测试步骤结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = StepResult(
            name="test",
            status=StepStatus.COMPLETED,
            output="output",
        )
        assert result.success is True
        assert result.output == "output"

    def test_failed_result(self):
        """测试失败结果"""
        result = StepResult(
            name="test",
            status=StepStatus.FAILED,
            error="error message",
        )
        assert result.success is False
        assert result.error == "error message"

    def test_to_dict(self):
        """测试转换为字典"""
        result = StepResult(
            name="test",
            status=StepStatus.COMPLETED,
            output="output",
        )
        d = result.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "completed"


class TestWorkflowResult:
    """测试工作流结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = WorkflowResult(
            success=True,
            final_output="final",
        )
        assert result.success is True

    def test_get_step(self):
        """测试获取步骤"""
        step1 = StepResult(name="step1", status=StepStatus.COMPLETED)
        step2 = StepResult(name="step2", status=StepStatus.COMPLETED)
        result = WorkflowResult(success=True, steps=[step1, step2])

        assert result.get_step("step1") is step1
        assert result.get_step("step2") is step2
        assert result.get_step("step3") is None


class TestStep:
    """测试步骤"""

    @pytest.mark.asyncio
    async def test_execute_simple(self):
        """测试简单执行"""
        step = Step(name="echo", agent=echo_agent)
        result = await step.execute("hello")

        assert result.status == StepStatus.COMPLETED
        assert result.output == "echo: hello"

    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        """测试执行错误"""
        step = Step(name="error", agent=error_agent)
        result = await step.execute("hello")

        assert result.status == StepStatus.FAILED
        assert "Test error" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_condition_true(self):
        """测试条件为真"""
        step = Step(
            name="echo",
            agent=echo_agent,
            condition=lambda x: len(x) > 3,
        )
        result = await step.execute("hello")

        assert result.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_with_condition_false(self):
        """测试条件为假"""
        step = Step(
            name="echo",
            agent=echo_agent,
            condition=lambda x: len(x) > 10,
        )
        result = await step.execute("hello")

        assert result.status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_execute_with_transform(self):
        """测试输入输出转换"""
        step = Step(
            name="upper",
            agent=upper_agent,
            transform_input=lambda x: x.strip(),
            transform_output=lambda x: f"[{x}]",
        )
        result = await step.execute("  hello  ")

        assert result.output == "[HELLO]"

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """测试超时"""
        step = Step(name="slow", agent=slow_agent, timeout=0.01)
        result = await step.execute("hello")

        assert result.status == StepStatus.FAILED
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_error_handler(self):
        """测试错误处理"""
        step = Step(
            name="error",
            agent=error_agent,
            on_error=lambda e: "fallback",
        )
        result = await step.execute("hello")

        assert result.status == StepStatus.COMPLETED
        assert result.output == "fallback"
        assert result.metadata.get("fallback") is True


class TestPipeline:
    """测试管道"""

    @pytest.mark.asyncio
    async def test_simple_pipeline(self):
        """测试简单管道"""
        p = Pipeline([
            ("echo", echo_agent),
            ("upper", upper_agent),
        ])
        result = await p.run("hello")

        assert result.success is True
        assert result.final_output == "ECHO: HELLO"

    @pytest.mark.asyncio
    async def test_pipeline_with_error(self):
        """测试管道错误"""
        p = Pipeline([
            ("echo", echo_agent),
            ("error", error_agent),
            ("upper", upper_agent),
        ])
        result = await p.run("hello")

        assert result.success is False
        assert len(result.steps) == 2  # 停在错误步骤

    @pytest.mark.asyncio
    async def test_pipeline_continue_on_error(self):
        """测试错误后继续"""
        p = Pipeline([
            ("echo", echo_agent),
            ("error", error_agent),
            ("upper", upper_agent),
        ], stop_on_error=False)
        result = await p.run("hello")

        assert result.success is False
        assert len(result.steps) == 3  # 全部执行

    @pytest.mark.asyncio
    async def test_pipeline_callback(self):
        """测试管道回调"""
        p = Pipeline([
            ("echo", echo_agent),
            ("upper", upper_agent),
        ])

        callbacks = []
        p.on_step_complete(lambda r: callbacks.append(r.name))

        await p.run("hello")
        assert callbacks == ["echo", "upper"]


class TestParallel:
    """测试并行执行"""

    @pytest.mark.asyncio
    async def test_simple_parallel(self):
        """测试简单并行"""
        p = Parallel([
            ("echo", echo_agent),
            ("upper", upper_agent),
            ("counter", counter_agent),
        ])
        result = await p.run("hello")

        assert result.success is True
        assert "echo" in result.final_output
        assert "upper" in result.final_output
        assert "counter" in result.final_output

    @pytest.mark.asyncio
    async def test_parallel_with_error(self):
        """测试并行错误"""
        p = Parallel([
            ("echo", echo_agent),
            ("error", error_agent),
        ])
        result = await p.run("hello")

        assert result.success is False
        assert "echo" in result.final_output

    @pytest.mark.asyncio
    async def test_parallel_with_concurrency(self):
        """测试并发限制"""
        p = Parallel([
            ("slow1", slow_agent),
            ("slow2", slow_agent),
            ("slow3", slow_agent),
        ], max_concurrency=2)

        result = await p.run("hello")
        assert result.success is True


class TestRouter:
    """测试路由"""

    @pytest.mark.asyncio
    async def test_simple_router(self):
        """测试简单路由"""
        r = Router([
            (lambda x: x.startswith("a"), ("upper", upper_agent)),
            (lambda x: x.startswith("b"), ("echo", echo_agent)),
        ])

        result = await r.run("abc")
        assert result.success is True
        assert result.final_output == "ABC"

        result = await r.run("bcd")
        assert result.success is True
        assert result.final_output == "echo: bcd"

    @pytest.mark.asyncio
    async def test_router_with_default(self):
        """测试默认路由"""
        r = Router([
            (lambda x: x.startswith("a"), ("upper", upper_agent)),
        ], default=("echo", echo_agent))

        result = await r.run("xyz")
        assert result.success is True
        assert result.final_output == "echo: xyz"

    @pytest.mark.asyncio
    async def test_router_no_match(self):
        """测试无匹配"""
        r = Router([
            (lambda x: x.startswith("a"), ("upper", upper_agent)),
        ])

        result = await r.run("xyz")
        assert result.success is False
        assert "No matching route" in result.error


class TestOrchestrator:
    """测试编排器"""

    @pytest.mark.asyncio
    async def test_register_and_run(self):
        """测试注册和运行"""
        orch = Orchestrator()
        orch.register("pipeline1", Pipeline([
            ("echo", echo_agent),
            ("upper", upper_agent),
        ]))

        result = await orch.run("pipeline1", "hello")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_nonexistent(self):
        """测试运行不存在的工作流"""
        orch = Orchestrator()
        result = await orch.run("nonexistent", "hello")

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_run_sequence(self):
        """测试顺序执行"""
        orch = Orchestrator()
        orch.register("echo", Pipeline([("echo", echo_agent)]))
        orch.register("upper", Pipeline([("upper", upper_agent)]))

        result = await orch.run_sequence(["echo", "upper"], "hello")
        assert result.success is True
        assert result.final_output == "ECHO: HELLO"

    @pytest.mark.asyncio
    async def test_run_parallel(self):
        """测试并行执行"""
        orch = Orchestrator()
        orch.register("echo", Pipeline([("echo", echo_agent)]))
        orch.register("upper", Pipeline([("upper", upper_agent)]))

        result = await orch.run_parallel(["echo", "upper"], "hello")
        assert result.success is True
        assert "echo" in result.final_output
        assert "upper" in result.final_output

    @pytest.mark.asyncio
    async def test_context(self):
        """测试上下文"""
        orch = Orchestrator()
        orch.set_context("key", "value")

        assert orch.get_context("key") == "value"
        assert orch.get_context("nonexistent", "default") == "default"

    @pytest.mark.asyncio
    async def test_callback(self):
        """测试回调"""
        orch = Orchestrator()
        orch.register("echo", Pipeline([("echo", echo_agent)]))

        results = []
        orch.on_complete(lambda r: results.append(r.success))

        await orch.run("echo", "hello")
        assert len(results) == 1
        assert results[0] is True


class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.mark.asyncio
    async def test_pipeline_function(self):
        """测试 pipeline 函数"""
        p = pipeline([("echo", echo_agent)])
        result = await p.run("hello")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_parallel_function(self):
        """测试 parallel 函数"""
        p = parallel([("echo", echo_agent), ("upper", upper_agent)])
        result = await p.run("hello")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_router_function(self):
        """测试 router 函数"""
        r = router([
            (lambda x: True, ("echo", echo_agent)),
        ])
        result = await r.run("hello")
        assert result.success is True


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_complex_workflow(self):
        """测试复杂工作流"""
        # 创建编排器
        orch = Orchestrator(name="test_orchestrator")

        # 注册工作流
        orch.register("preprocess", Pipeline([
            ("echo", echo_agent),
        ]))

        orch.register("process", Parallel([
            ("upper", upper_agent),
            ("counter", counter_agent),
        ]))

        # 执行
        result1 = await orch.run("preprocess", "hello")
        assert result1.success is True

        result2 = await orch.run("process", result1.final_output)
        assert result2.success is True
        assert "upper" in result2.final_output
        assert "counter" in result2.final_output

    @pytest.mark.asyncio
    async def test_nested_workflows(self):
        """测试嵌套工作流"""
        # 内部管道
        inner = Pipeline([
            ("echo", echo_agent),
            ("upper", upper_agent),
        ])

        # 外部管道使用内部管道的 run 方法
        async def inner_agent(input_data):
            result = await inner.run(input_data)
            return result.final_output

        outer = Pipeline([
            ("inner", inner_agent),
            ("counter", counter_agent),
        ])

        result = await outer.run("hello")
        assert result.success is True
        assert result.final_output == 12  # len("ECHO: HELLO")
