"""
规划系统

实现任务分解、优先级管理、进度跟踪等功能
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from ..schema import Message


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(Enum):
    """优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ExecutionMode(Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"      # 并行执行
    ADAPTIVE = "adaptive"      # 自适应模式


@dataclass
class TaskDependency:
    """任务依赖"""
    task_id: str
    dependency_type: str = "finish_to_start"  # finish_to_start, start_to_start, etc.
    condition: Optional[Callable[[Any], bool]] = None  # 完成条件


@dataclass
class PlanStep:
    """计划步骤"""
    id: str
    description: str
    expected_outcome: str
    estimated_duration: timedelta
    dependencies: List[TaskDependency] = field(default_factory=list)
    resources_needed: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """任务定义"""
    id: str
    description: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.NORMAL
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL  # 添加执行模式
    created_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    dependencies: List[TaskDependency] = field(default_factory=list)
    parent_task: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0.0 to 1.0
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_ready_to_execute(self) -> bool:
        """检查任务是否准备好执行"""
        if self.status != TaskStatus.PENDING:
            return False
        
        # 检查所有依赖是否完成
        for dep in self.dependencies:
            # 这里需要访问任务管理系统来检查依赖状态
            # 简化实现：假设依赖已完成
            pass
        
        return True


class BasePlanner(ABC):
    """规划器基类"""
    
    @abstractmethod
    async def create_plan(self, goal: str, context: List[Message] = None) -> List[PlanStep]:
        """创建计划"""
        pass
    
    @abstractmethod
    async def refine_plan(self, plan: List[PlanStep], feedback: str) -> List[PlanStep]:
        """优化计划"""
        pass


class SimplePlanner(BasePlanner):
    """简单规划器实现"""
    
    async def create_plan(self, goal: str, context: List[Message] = None) -> List[PlanStep]:
        """创建简单计划"""
        # 这里应该集成LLM来生成计划
        # 为了演示，我们创建一个简单的默认计划
        steps = [
            PlanStep(
                id=str(uuid.uuid4()),
                description="分析任务目标和要求",
                expected_outcome="明确任务的具体要求和约束条件",
                estimated_duration=timedelta(minutes=10)
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                description="收集相关信息和资源",
                expected_outcome="获得完成任务所需的信息和工具",
                estimated_duration=timedelta(minutes=15)
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                description="制定详细执行步骤",
                expected_outcome="形成可执行的详细计划",
                estimated_duration=timedelta(minutes=20)
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                description="执行计划并监控进度",
                expected_outcome="完成任务并达到预期目标",
                estimated_duration=timedelta(minutes=30)
            ),
            PlanStep(
                id=str(uuid.uuid4()),
                description="评估结果并总结",
                expected_outcome="验证任务完成情况并记录经验",
                estimated_duration=timedelta(minutes=10)
            )
        ]
        
        return steps
    
    async def refine_plan(self, plan: List[PlanStep], feedback: str) -> List[PlanStep]:
        """优化计划 - 简单实现"""
        # 根据反馈调整计划
        # 这里应该使用更智能的算法来优化计划
        return plan


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.planner: BasePlanner = SimplePlanner()
        self.active_tasks: List[str] = []
    
    async def create_task(self, description: str, goal: str, 
                         priority: Priority = Priority.NORMAL,
                         due_date: Optional[datetime] = None,
                         parent_task: Optional[str] = None) -> str:
        """创建任务"""
        task_id = str(uuid.uuid4())
        
        # 创建计划
        plan = await self.planner.create_plan(goal)
        
        task = Task(
            id=task_id,
            description=description,
            goal=goal,
            steps=plan,
            priority=priority,
            due_date=due_date,
            parent_task=parent_task
        )
        
        self.tasks[task_id] = task
        
        if parent_task and parent_task in self.tasks:
            self.tasks[parent_task].subtasks.append(task_id)
        
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    async def update_task_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        if task_id in self.tasks:
            old_status = self.tasks[task_id].status
            self.tasks[task_id].status = status
            
            # 更新进度
            if status == TaskStatus.COMPLETED:
                self.tasks[task_id].progress = 1.0
            elif status == TaskStatus.IN_PROGRESS:
                self.tasks[task_id].progress = 0.5
            elif status == TaskStatus.PENDING:
                self.tasks[task_id].progress = 0.0
            
            # 如果状态改变，更新依赖的任务
            await self._update_dependent_tasks(task_id, old_status, status)
    
    async def _update_dependent_tasks(self, task_id: str, old_status: TaskStatus, new_status: TaskStatus):
        """更新依赖任务的状态"""
        # 查找依赖于当前任务的其他任务
        for tid, task in self.tasks.items():
            for dep in task.dependencies:
                if dep.task_id == task_id:
                    # 根据依赖类型更新状态
                    if new_status == TaskStatus.COMPLETED:
                        if task.status == TaskStatus.BLOCKED:
                            # 检查是否还有其他阻塞因素
                            is_still_blocked = False
                            for other_dep in task.dependencies:
                                if other_dep.task_id != task_id:
                                    other_task = self.tasks.get(other_dep.task_id)
                                    if other_task and other_task.status not in [TaskStatus.COMPLETED]:
                                        is_still_blocked = True
                                        break
                            
                            if not is_still_blocked:
                                await self.update_task_status(tid, TaskStatus.PENDING)
    
    async def assign_task(self, task_id: str, agent_id: str):
        """分配任务给Agent"""
        if task_id in self.tasks:
            self.tasks[task_id].assigned_to = agent_id
            # 如果任务处于待处理状态，改为进行中
            if self.tasks[task_id].status == TaskStatus.PENDING:
                await self.update_task_status(task_id, TaskStatus.IN_PROGRESS)
    
    async def complete_task(self, task_id: str, result: str = None):
        """完成任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.progress = 1.0
    
    async def fail_task(self, task_id: str, error: str = None):
        """标记任务失败"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error = error
            task.progress = 0.0
    
    async def get_ready_tasks(self) -> List[Task]:
        """获取准备执行的任务"""
        ready_tasks = []
        for task in self.tasks.values():
            if task.is_ready_to_execute():
                ready_tasks.append(task)
        # 按优先级排序
        ready_tasks.sort(key=lambda t: t.priority.value, reverse=True)
        return ready_tasks
    
    async def get_task_by_priority(self, priority: Priority) -> List[Task]:
        """按优先级获取任务"""
        return [t for t in self.tasks.values() if t.priority == priority]
    
    async def get_overdue_tasks(self) -> List[Task]:
        """获取逾期任务"""
        overdue = []
        now = datetime.now()
        for task in self.tasks.values():
            if task.due_date and task.due_date < now and task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                overdue.append(task)
        return overdue
    
    async def get_task_hierarchy(self, root_task_id: str) -> Dict[str, Any]:
        """获取任务层级结构"""
        def build_hierarchy(tid: str) -> Dict[str, Any]:
            task = self.tasks[tid]
            return {
                "task": task,
                "subtasks": [build_hierarchy(subtid) for subtid in task.subtasks if subtid in self.tasks]
            }
        
        if root_task_id in self.tasks:
            return build_hierarchy(root_task_id)
        return {}


class PlanExecutor:
    """计划执行器"""
    
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.execution_log: List[Dict[str, Any]] = []
    
    async def execute_plan(self, task_id: str) -> bool:
        """执行计划"""
        task = await self.task_manager.get_task(task_id)
        if not task:
            return False

        await self.task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)

        try:
            # 根据任务执行模式决定如何执行步骤
            if task.execution_mode == ExecutionMode.PARALLEL and len(task.steps) > 1:
                success = await self._execute_steps_parallel(task, task.steps)
            else:
                success = await self._execute_steps_sequential(task, task.steps)

            if success:
                # 所有步骤完成，标记任务完成
                await self.task_manager.complete_task(task_id, "计划执行完成")
                return True
            else:
                return False

        except Exception as e:
            await self.task_manager.fail_task(task_id, str(e))
            return False
    
    async def _execute_steps_sequential(self, task: Task, steps: List[PlanStep]) -> bool:
        """顺序执行步骤"""
        for step in steps:
            step_result = await self._execute_step(step, task)

            if step_result["success"]:
                # 记录成功执行的步骤
                self.execution_log.append({
                    "task_id": task.id,
                    "step_id": step.id,
                    "status": "completed",
                    "result": step_result["result"],
                    "timestamp": datetime.now()
                })
            else:
                # 步骤执行失败
                self.execution_log.append({
                    "task_id": task.id,
                    "step_id": step.id,
                    "status": "failed",
                    "error": step_result["error"],
                    "timestamp": datetime.now()
                })

                # 标记整个任务失败
                await self.task_manager.fail_task(task.id, step_result["error"])
                return False
        
        return True
    
    async def _execute_steps_parallel(self, task: Task, steps: List[PlanStep]) -> bool:
        """并行执行步骤"""
        # 按依赖关系对步骤进行分组
        step_groups = self._group_steps_by_dependencies(steps)
        
        for group in step_groups:
            # 对同一组内的步骤进行并行执行
            step_tasks = [self._execute_step_async(step, task) for step in group]
            step_results = await asyncio.gather(*step_tasks, return_exceptions=True)
            
            # 检查执行结果
            for i, result in enumerate(step_results):
                step = group[i]
                if isinstance(result, Exception):
                    # 如果是异常，记录错误
                    error_result = {
                        "success": False,
                        "error": str(result)
                    }
                else:
                    error_result = result
                
                if not error_result["success"]:
                    self.execution_log.append({
                        "task_id": task.id,
                        "step_id": step.id,
                        "status": "failed",
                        "error": error_result["error"],
                        "timestamp": datetime.now()
                    })

                    # 标记整个任务失败
                    await self.task_manager.fail_task(task.id, error_result["error"])
                    return False
                else:
                    # 记录成功执行的步骤
                    self.execution_log.append({
                        "task_id": task.id,
                        "step_id": step.id,
                        "status": "completed",
                        "result": error_result["result"],
                        "timestamp": datetime.now()
                    })
        
        return True
    
    async def _execute_step_async(self, step: PlanStep, task: Task) -> Dict[str, Any]:
        """异步执行单个步骤"""
        return await self._execute_step(step, task)
    
    def _group_steps_by_dependencies(self, steps: List[PlanStep]) -> List[List[PlanStep]]:
        """根据依赖关系对步骤进行分组"""
        # 构建依赖图
        dependencies = {step.id: set(step.dependencies) for step in steps}
        step_lookup = {step.id: step for step in steps}
        
        # 拓扑排序算法对步骤进行分组
        groups = []
        remaining_steps = set(step.id for step in steps)
        
        while remaining_steps:
            # 找到没有未完成依赖的步骤
            ready_steps = []
            for step_id in list(remaining_steps):
                deps = dependencies[step_id]
                if not (deps & remaining_steps):  # 没有依赖步骤还在remaining_steps中
                    ready_steps.append(step_id)
            
            if not ready_steps:
                # 循环依赖，返回原始步骤（不并行执行）
                return [steps]
            
            # 添加这一组步骤
            group = [step_lookup[step_id] for step_id in ready_steps]
            groups.append(group)
            
            # 从剩余步骤中移除已完成的步骤
            for step_id in ready_steps:
                remaining_steps.remove(step_id)
        
        return groups
    
    async def _execute_step(self, step: PlanStep, task: Task) -> Dict[str, Any]:
        """执行单个步骤"""
        # 这里应该集成具体的执行逻辑
        # 为了演示，我们模拟执行
        try:
            # 模拟执行时间
            await asyncio.sleep(0.1)
            
            return {
                "success": True,
                "result": f"步骤 '{step.description}' 执行成功"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_execution_log(self, task_id: str = None) -> List[Dict[str, Any]]:
        """获取执行日志"""
        if task_id:
            return [log for log in self.execution_log if log["task_id"] == task_id]
        return self.execution_log
    
    async def rollback_task(self, task_id: str) -> bool:
        """回滚任务"""
        # 实现任务回滚逻辑
        # 这里需要根据执行日志反向执行补偿操作
        task = await self.task_manager.get_task(task_id)
        if not task:
            return False
        
        # 将任务状态改回待处理
        await self.task_manager.update_task_status(task_id, TaskStatus.PENDING)
        return True


class AdaptivePlanner(BasePlanner):
    """自适应规划器"""
    
    def __init__(self):
        self.known_patterns: Dict[str, List[PlanStep]] = {}
    
    async def create_plan(self, goal: str, context: List[Message] = None) -> List[PlanStep]:
        """创建自适应计划"""
        # 尝试匹配已知模式
        for pattern, steps in self.known_patterns.items():
            if pattern.lower() in goal.lower():
                # 返回匹配的模式，可能需要根据具体情况进行调整
                return [PlanStep(**step.__dict__) for step in steps]
        
        # 如果没有匹配的模式，使用基础规划器
        return await SimplePlanner().create_plan(goal, context)
    
    async def refine_plan(self, plan: List[PlanStep], feedback: str) -> List[PlanStep]:
        """根据反馈优化计划"""
        # 分析反馈并调整计划
        refined_plan = []
        for step in plan:
            # 根据反馈调整步骤
            new_step = PlanStep(**step.__dict__)
            refined_plan.append(new_step)
        
        # 学习新模式
        self._learn_pattern(plan, feedback)
        
        return refined_plan
    
    def _learn_pattern(self, plan: List[PlanStep], feedback: str):
        """从计划和反馈中学习模式"""
        # 简化的学习算法
        # 在实际实现中，这将涉及更复杂的机器学习技术
        pass


class PlanningSystem:
    """规划系统主类"""
    
    def __init__(self):
        self.task_manager = TaskManager()
        self.plan_executor = PlanExecutor(self.task_manager)
        self.adaptive_planner = AdaptivePlanner()
    
    async def create_and_execute_task(self, description: str, goal: str, 
                                   priority: Priority = Priority.NORMAL) -> str:
        """创建并执行任务"""
        # 创建任务
        task_id = await self.task_manager.create_task(description, goal, priority)
        
        # 执行任务
        success = await self.plan_executor.execute_plan(task_id)
        
        if success:
            return task_id
        else:
            task = await self.task_manager.get_task(task_id)
            if task and task.error:
                raise Exception(f"任务执行失败: {task.error}")
            else:
                raise Exception("任务执行失败，但没有错误信息")
    
    async def get_task_status(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        return await self.task_manager.get_task(task_id)
    
    async def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return [t for t in self.task_manager.tasks.values() if t.status == TaskStatus.PENDING]
    
    async def get_active_tasks(self) -> List[Task]:
        """获取活动任务"""
        return [t for t in self.task_manager.tasks.values() 
                if t.status in [TaskStatus.PLANNING, TaskStatus.IN_PROGRESS]]
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.task_manager.tasks:
            await self.task_manager.update_task_status(task_id, TaskStatus.CANCELLED)
            return True
        return False
    
    async def reassign_task(self, task_id: str, new_agent_id: str) -> bool:
        """重新分配任务"""
        if task_id in self.task_manager.tasks:
            await self.task_manager.assign_task(task_id, new_agent_id)
            return True
        return False