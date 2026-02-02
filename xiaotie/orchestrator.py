"""
Agent 编排模块

提供多 Agent 工作流编排能力：
- Pipeline: 顺序执行
- Parallel: 并行执行
- Router: 条件路由
- Orchestrator: 统一编排

使用示例:
    from xiaotie.orchestrator import Pipeline, Parallel, Router, Orchestrator

    # 顺序执行
    pipeline = Pipeline([
        ("analyzer", analyzer_agent),
        ("coder", coder_agent),
        ("reviewer", reviewer_agent),
    ])
    result = await pipeline.run("实现排序算法")

    # 并行执行
    parallel = Parallel([
        ("search", search_agent),
        ("analyze", analyze_agent),
    ])
    results = await parallel.run("查找相关代码")
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Union, Awaitable
import asyncio
import time
from abc import ABC, abstractmethod


class ExecutionMode(Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """步骤执行结果"""
    name: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == StepStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    final_output: Any = None
    total_time: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "steps": [s.to_dict() for s in self.steps],
            "final_output": self.final_output,
            "total_time": self.total_time,
            "error": self.error,
        }

    def get_step(self, name: str) -> Optional[StepResult]:
        """获取指定步骤的结果"""
        for step in self.steps:
            if step.name == name:
                return step
        return None


class OrchestrationError(Exception):
    """编排错误"""
    pass


class StepExecutionError(OrchestrationError):
    """步骤执行错误"""
    def __init__(self, step_name: str, message: str):
        self.step_name = step_name
        super().__init__(f"Step '{step_name}' failed: {message}")


# Agent 协议
AgentCallable = Callable[[Any], Awaitable[Any]]


class Step:
    """工作流步骤"""

    def __init__(
        self,
        name: str,
        agent: AgentCallable,
        condition: Optional[Callable[[Any], bool]] = None,
        transform_input: Optional[Callable[[Any], Any]] = None,
        transform_output: Optional[Callable[[Any], Any]] = None,
        on_error: Optional[Callable[[Exception], Any]] = None,
        timeout: Optional[float] = None,
    ):
        self.name = name
        self.agent = agent
        self.condition = condition
        self.transform_input = transform_input
        self.transform_output = transform_output
        self.on_error = on_error
        self.timeout = timeout

    async def execute(self, input_data: Any, context: Dict[str, Any] = None) -> StepResult:
        """执行步骤"""
        start_time = time.time()
        context = context or {}

        # 检查条件
        if self.condition and not self.condition(input_data):
            return StepResult(
                name=self.name,
                status=StepStatus.SKIPPED,
                execution_time=time.time() - start_time,
            )

        try:
            # 转换输入
            if self.transform_input:
                input_data = self.transform_input(input_data)

            # 执行 agent
            if self.timeout:
                output = await asyncio.wait_for(
                    self.agent(input_data),
                    timeout=self.timeout,
                )
            else:
                output = await self.agent(input_data)

            # 转换输出
            if self.transform_output:
                output = self.transform_output(output)

            return StepResult(
                name=self.name,
                status=StepStatus.COMPLETED,
                output=output,
                execution_time=time.time() - start_time,
            )

        except asyncio.TimeoutError:
            return StepResult(
                name=self.name,
                status=StepStatus.FAILED,
                error=f"Timeout after {self.timeout}s",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            # 错误处理
            if self.on_error:
                try:
                    fallback_output = self.on_error(e)
                    return StepResult(
                        name=self.name,
                        status=StepStatus.COMPLETED,
                        output=fallback_output,
                        execution_time=time.time() - start_time,
                        metadata={"fallback": True, "original_error": str(e)},
                    )
                except Exception:
                    pass

            return StepResult(
                name=self.name,
                status=StepStatus.FAILED,
                error=str(e),
                execution_time=time.time() - start_time,
            )


class Workflow(ABC):
    """工作流基类"""

    def __init__(self, name: str = "workflow"):
        self.name = name
        self._callbacks: List[Callable[[StepResult], None]] = []

    def on_step_complete(self, callback: Callable[[StepResult], None]) -> "Workflow":
        """注册步骤完成回调"""
        self._callbacks.append(callback)
        return self

    def _notify_callbacks(self, result: StepResult):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass

    @abstractmethod
    async def run(self, input_data: Any) -> WorkflowResult:
        """执行工作流"""
        pass


class Pipeline(Workflow):
    """顺序执行管道"""

    def __init__(
        self,
        steps: List[Union[tuple, Step]],
        name: str = "pipeline",
        stop_on_error: bool = True,
    ):
        super().__init__(name)
        self.steps = self._normalize_steps(steps)
        self.stop_on_error = stop_on_error

    def _normalize_steps(self, steps: List[Union[tuple, Step]]) -> List[Step]:
        """标准化步骤"""
        normalized = []
        for step in steps:
            if isinstance(step, Step):
                normalized.append(step)
            elif isinstance(step, tuple):
                name, agent = step[0], step[1]
                kwargs = step[2] if len(step) > 2 else {}
                normalized.append(Step(name=name, agent=agent, **kwargs))
            else:
                raise ValueError(f"Invalid step type: {type(step)}")
        return normalized

    async def run(self, input_data: Any) -> WorkflowResult:
        """执行管道"""
        start_time = time.time()
        results = []
        current_input = input_data
        error = None

        for step in self.steps:
            result = await step.execute(current_input)
            results.append(result)
            self._notify_callbacks(result)

            if result.status == StepStatus.FAILED:
                if self.stop_on_error:
                    error = f"Step '{step.name}' failed: {result.error}"
                    break
            elif result.status == StepStatus.COMPLETED:
                current_input = result.output

        # 获取最终输出
        final_output = None
        for result in reversed(results):
            if result.status == StepStatus.COMPLETED:
                final_output = result.output
                break

        return WorkflowResult(
            success=error is None,
            steps=results,
            final_output=final_output,
            total_time=time.time() - start_time,
            error=error,
        )


class Parallel(Workflow):
    """并行执行"""

    def __init__(
        self,
        steps: List[Union[tuple, Step]],
        name: str = "parallel",
        max_concurrency: Optional[int] = None,
    ):
        super().__init__(name)
        self.steps = self._normalize_steps(steps)
        self.max_concurrency = max_concurrency

    def _normalize_steps(self, steps: List[Union[tuple, Step]]) -> List[Step]:
        """标准化步骤"""
        normalized = []
        for step in steps:
            if isinstance(step, Step):
                normalized.append(step)
            elif isinstance(step, tuple):
                name, agent = step[0], step[1]
                kwargs = step[2] if len(step) > 2 else {}
                normalized.append(Step(name=name, agent=agent, **kwargs))
        return normalized

    async def run(self, input_data: Any) -> WorkflowResult:
        """并行执行所有步骤"""
        start_time = time.time()

        if self.max_concurrency:
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def limited_execute(step: Step):
                async with semaphore:
                    return await step.execute(input_data)

            tasks = [limited_execute(step) for step in self.steps]
        else:
            tasks = [step.execute(input_data) for step in self.steps]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        step_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                step_results.append(StepResult(
                    name=self.steps[i].name,
                    status=StepStatus.FAILED,
                    error=str(result),
                ))
            else:
                step_results.append(result)
                self._notify_callbacks(result)

        # 检查是否全部成功
        all_success = all(r.status == StepStatus.COMPLETED for r in step_results)

        # 合并输出
        outputs = {r.name: r.output for r in step_results if r.status == StepStatus.COMPLETED}

        return WorkflowResult(
            success=all_success,
            steps=step_results,
            final_output=outputs,
            total_time=time.time() - start_time,
        )


class Router(Workflow):
    """条件路由"""

    def __init__(
        self,
        routes: List[tuple],  # [(condition, step), ...]
        default: Optional[Union[tuple, Step]] = None,
        name: str = "router",
    ):
        super().__init__(name)
        self.routes = [(cond, self._normalize_step(step)) for cond, step in routes]
        self.default = self._normalize_step(default) if default else None

    def _normalize_step(self, step: Union[tuple, Step, None]) -> Optional[Step]:
        """标准化步骤"""
        if step is None:
            return None
        if isinstance(step, Step):
            return step
        if isinstance(step, tuple):
            name, agent = step[0], step[1]
            kwargs = step[2] if len(step) > 2 else {}
            return Step(name=name, agent=agent, **kwargs)
        raise ValueError(f"Invalid step type: {type(step)}")

    async def run(self, input_data: Any) -> WorkflowResult:
        """根据条件路由执行"""
        start_time = time.time()

        # 查找匹配的路由
        selected_step = None
        for condition, step in self.routes:
            if condition(input_data):
                selected_step = step
                break

        if selected_step is None:
            selected_step = self.default

        if selected_step is None:
            return WorkflowResult(
                success=False,
                total_time=time.time() - start_time,
                error="No matching route found",
            )

        # 执行选中的步骤
        result = await selected_step.execute(input_data)
        self._notify_callbacks(result)

        return WorkflowResult(
            success=result.status == StepStatus.COMPLETED,
            steps=[result],
            final_output=result.output,
            total_time=time.time() - start_time,
            error=result.error,
        )


class Orchestrator:
    """统一编排器"""

    def __init__(self, name: str = "orchestrator"):
        self.name = name
        self._workflows: Dict[str, Workflow] = {}
        self._context: Dict[str, Any] = {}
        self._callbacks: List[Callable[[WorkflowResult], None]] = []

    def register(self, name: str, workflow: Workflow) -> "Orchestrator":
        """注册工作流"""
        self._workflows[name] = workflow
        return self

    def unregister(self, name: str) -> bool:
        """注销工作流"""
        if name in self._workflows:
            del self._workflows[name]
            return True
        return False

    def get_workflow(self, name: str) -> Optional[Workflow]:
        """获取工作流"""
        return self._workflows.get(name)

    def set_context(self, key: str, value: Any) -> "Orchestrator":
        """设置上下文"""
        self._context[key] = value
        return self

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self._context.get(key, default)

    def on_complete(self, callback: Callable[[WorkflowResult], None]) -> "Orchestrator":
        """注册完成回调"""
        self._callbacks.append(callback)
        return self

    def _notify_callbacks(self, result: WorkflowResult):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass

    async def run(self, workflow_name: str, input_data: Any) -> WorkflowResult:
        """执行指定工作流"""
        workflow = self._workflows.get(workflow_name)
        if workflow is None:
            return WorkflowResult(
                success=False,
                error=f"Workflow '{workflow_name}' not found",
            )

        result = await workflow.run(input_data)
        self._notify_callbacks(result)
        return result

    async def run_sequence(
        self,
        workflow_names: List[str],
        input_data: Any,
    ) -> WorkflowResult:
        """顺序执行多个工作流"""
        start_time = time.time()
        all_steps = []
        current_input = input_data
        error = None

        for name in workflow_names:
            result = await self.run(name, current_input)
            all_steps.extend(result.steps)

            if not result.success:
                error = f"Workflow '{name}' failed: {result.error}"
                break

            current_input = result.final_output

        return WorkflowResult(
            success=error is None,
            steps=all_steps,
            final_output=current_input if error is None else None,
            total_time=time.time() - start_time,
            error=error,
        )

    async def run_parallel(
        self,
        workflow_names: List[str],
        input_data: Any,
    ) -> WorkflowResult:
        """并行执行多个工作流"""
        start_time = time.time()

        tasks = [self.run(name, input_data) for name in workflow_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_steps = []
        outputs = {}
        all_success = True

        for i, result in enumerate(results):
            name = workflow_names[i]
            if isinstance(result, Exception):
                all_success = False
            elif isinstance(result, WorkflowResult):
                all_steps.extend(result.steps)
                if result.success:
                    outputs[name] = result.final_output
                else:
                    all_success = False

        return WorkflowResult(
            success=all_success,
            steps=all_steps,
            final_output=outputs,
            total_time=time.time() - start_time,
        )


# 便捷函数
def pipeline(steps: List[Union[tuple, Step]], **kwargs) -> Pipeline:
    """创建管道"""
    return Pipeline(steps, **kwargs)


def parallel(steps: List[Union[tuple, Step]], **kwargs) -> Parallel:
    """创建并行执行"""
    return Parallel(steps, **kwargs)


def router(routes: List[tuple], **kwargs) -> Router:
    """创建路由"""
    return Router(routes, **kwargs)
