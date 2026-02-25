"""
多Agent协作系统

实现多Agent之间的协调与合作
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from ..agent import Agent
from ..schema import Message
from ..events import Event, EventType, get_event_broker


class AgentRole(Enum):
    """Agent角色枚举"""
    COORDINATOR = "coordinator"  # 协调者
    EXPERT = "expert"            # 专家
    EXECUTOR = "executor"        # 执行者
    SUPERVISOR = "supervisor"    # 监督者
    RESEARCHER = "researcher"    # 研究者
    WRITER = "writer"           # 写作者
    REVIEWER = "reviewer"       # 评审者


@dataclass
class Task:
    """任务定义"""
    id: str
    description: str
    assigned_to: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    priority: int = 1       # 1-5, 5为最高优先级
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Agent状态"""
    agent_id: str
    role: AgentRole
    capabilities: List[str]  # 该Agent具备的能力
    status: str = "idle"     # idle, busy, unavailable
    last_activity: Optional[float] = None
    workload: int = 0        # 当前工作负载


class CommunicationProtocol:
    """通信协议"""
    
    def __init__(self):
        self.event_broker = get_event_broker()
    
    async def send_message(self, sender: str, receiver: str, content: str, message_type: str = "task"):
        """发送消息"""
        event_data = {
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "type": message_type,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        event = Event(
            type=EventType.MESSAGE_DELTA,
            data=event_data
        )
        
        await self.event_broker.publish(event)
    
    async def broadcast_message(self, sender: str, content: str, targets: Optional[List[str]] = None):
        """广播消息"""
        event_data = {
            "sender": sender,
            "content": content,
            "targets": targets,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        event = Event(
            type=EventType.MESSAGE_DELTA,
            data=event_data
        )
        
        await self.event_broker.publish(event)


class BaseAgent(ABC):
    """基础Agent抽象类"""
    
    def __init__(self, agent_id: str, role: AgentRole, capabilities: List[str]):
        self.id = agent_id
        self.role = role
        self.capabilities = capabilities
        self.state = AgentState(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities
        )
        self.communication = CommunicationProtocol()
        self.tasks: List[Task] = []
        self.subordinates: List['BaseAgent'] = []
        self.supervisor: Optional['BaseAgent'] = None
    
    @abstractmethod
    async def execute_task(self, task: Task) -> str:
        """执行任务"""
        pass
    
    async def assign_task(self, task: Task, agent: 'BaseAgent'):
        """分配任务给其他Agent"""
        task.assigned_to = agent.id
        await self.communication.send_message(
            sender=self.id,
            receiver=agent.id,
            content=f"任务分配: {task.description}",
            message_type="assignment"
        )
    
    async def report_status(self, task_id: str, status: str, result: Optional[str] = None):
        """报告任务状态"""
        if self.supervisor:
            await self.communication.send_message(
                sender=self.id,
                receiver=self.supervisor.id,
                content=f"任务 {task_id} 状态: {status}",
                message_type="status_update"
            )


class CoordinatorAgent(BaseAgent):
    """协调者Agent - 负责任务分配和进度跟踪"""
    
    def __init__(self, agent_id: str):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.COORDINATOR,
            capabilities=["task_coordination", "resource_allocation", "progress_tracking"]
        )
        self.task_queue: List[Task] = []
        self.agent_pool: List[BaseAgent] = []
    
    async def add_agent(self, agent: BaseAgent):
        """添加Agent到池中"""
        self.agent_pool.append(agent)
        agent.supervisor = self
    
    async def distribute_tasks(self):
        """分发任务给合适的Agent"""
        available_agents = [a for a in self.agent_pool if a.state.status == "idle"]
        
        for task in self.task_queue[:]:  # 使用切片避免在迭代时修改列表
            if task.status != "pending":
                continue
                
            # 寻找最适合的Agent
            suitable_agent = await self._find_suitable_agent(task)
            if suitable_agent:
                await self.assign_task(task, suitable_agent)
                suitable_agent.tasks.append(task)
                task.status = "running"
                self.task_queue.remove(task)
    
    async def _find_suitable_agent(self, task: Task) -> Optional[BaseAgent]:
        """查找适合执行任务的Agent"""
        for agent in self.agent_pool:
            # 检查能力匹配
            if any(cap in agent.capabilities for cap in task.metadata.get("required_capabilities", [])):
                # 检查工作负载
                if agent.state.workload < 3:  # 假设最大工作负载为3
                    return agent
        return None
    
    async def execute_task(self, task: Task) -> str:
        """执行协调任务"""
        # 将任务加入队列
        self.task_queue.append(task)
        
        # 尝试立即分发
        await self.distribute_tasks()
        
        return f"任务已加入协调队列，等待分配"
    
    async def track_progress(self):
        """跟踪任务进度"""
        for agent in self.agent_pool:
            for task in agent.tasks[:]:
                if task.status == "completed":
                    agent.tasks.remove(task)
                    agent.state.workload -= 1


class ExpertAgent(BaseAgent):
    """专家Agent - 专门处理特定领域任务"""
    
    def __init__(self, agent_id: str, expertise_area: str):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.EXPERT,
            capabilities=[f"expert_{expertise_area}", "analysis", "evaluation"]
        )
        self.expertise_area = expertise_area
        self.knowledge_base = {}  # 专业知识库
    
    async def execute_task(self, task: Task) -> str:
        """执行专家任务"""
        self.state.workload += 1
        self.state.status = "busy"
        
        try:
            # 这里应该集成具体的专家逻辑
            result = f"专家分析结果: 基于{self.expertise_area}领域知识对'{task.description}'进行分析"
            
            task.status = "completed"
            task.result = result
            
            await self.report_status(task.id, "completed", result)
            return result
        finally:
            self.state.workload -= 1
            self.state.status = "idle"


class ExecutorAgent(BaseAgent):
    """执行者Agent - 执行具体操作"""
    
    def __init__(self, agent_id: str):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.EXECUTOR,
            capabilities=["execution", "operation", "implementation"]
        )
    
    async def execute_task(self, task: Task) -> str:
        """执行具体任务"""
        self.state.workload += 1
        self.state.status = "busy"
        
        try:
            # 执行任务的具体逻辑
            result = f"执行结果: 已完成任务 '{task.description}'"
            
            task.status = "completed"
            task.result = result
            
            await self.report_status(task.id, "completed", result)
            return result
        finally:
            self.state.workload -= 1
            self.state.status = "idle"


class SupervisorAgent(BaseAgent):
    """监督者Agent - 质量控制和评估"""
    
    def __init__(self, agent_id: str):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.SUPERVISOR,
            capabilities=["quality_control", "evaluation", "verification"]
        )
    
    async def execute_task(self, task: Task) -> str:
        """执行监督任务"""
        # 对任务结果进行评估
        evaluation = f"监督评估: 任务 '{task.description}' 符合质量标准"
        
        task.status = "completed"
        task.result = evaluation
        
        return evaluation


class MultiAgentSystem:
    """多Agent系统管理器"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.coordinator: Optional[CoordinatorAgent] = None
        self.communication = CommunicationProtocol()
        self.task_registry: Dict[str, Task] = {}
    
    async def add_agent(self, agent: BaseAgent):
        """添加Agent到系统"""
        self.agents[agent.id] = agent
        
        # 如果是协调者，特殊处理
        if isinstance(agent, CoordinatorAgent):
            self.coordinator = agent
    
    async def create_task(self, description: str, required_capabilities: List[str] = None, 
                         priority: int = 1, dependencies: List[str] = None) -> Task:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata={"required_capabilities": required_capabilities or []}
        )
        
        self.task_registry[task_id] = task
        return task
    
    async def execute_task(self, task: Task) -> str:
        """执行任务（通过协调者）"""
        if not self.coordinator:
            # 如果没有协调者，创建一个默认的
            self.coordinator = CoordinatorAgent("default-coordinator")
            await self.add_agent(self.coordinator)
        
        # 将任务交给协调者
        result = await self.coordinator.execute_task(task)
        
        # 定期检查进度
        for _ in range(10):  # 最多等待10次检查
            await asyncio.sleep(1)
            if task.status == "completed":
                return task.result or result
        
        return f"任务执行超时: {task.description}"
    
    async def run_workflow(self, tasks: List[Task]) -> Dict[str, str]:
        """运行工作流"""
        results = {}
        
        for task in tasks:
            result = await self.execute_task(task)
            results[task.id] = result
        
        return results