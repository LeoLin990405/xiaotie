"""
小铁框架综合示例

展示所有新功能的使用方法
"""

import asyncio
from datetime import datetime, timedelta

from xiaotie import (
    # 核心组件
    Agent,
    AgentBuilder,
    
    # 多Agent协作
    MultiAgentSystem,
    CoordinatorAgent,
    ExpertAgent,
    ExecutorAgent,
    AgentRole,
    
    # 记忆系统
    MemoryManager,
    ConversationMemory,
    MemoryType,
    
    # 规划系统
    PlanningSystem,
    TaskManager,
    Priority,
    
    # 反思机制
    ReflectionManager,
    ReflectiveAgentMixin,
)

# 从工具模块导入
from xiaotie.tools import PythonTool, BashTool


async def demo_multi_agent_collaboration():
    """演示多Agent协作"""
    print("🧠 演示多Agent协作...")
    
    # 创建多Agent系统
    multi_agent_system = MultiAgentSystem()
    
    # 创建协调者Agent
    coordinator = CoordinatorAgent("coordinator-1")
    await multi_agent_system.add_agent(coordinator)
    
    # 创建专家Agent
    coding_expert = ExpertAgent("coding-expert-1", "programming")
    research_expert = ExpertAgent("research-expert-1", "research")
    
    await multi_agent_system.add_agent(coding_expert)
    await multi_agent_system.add_agent(research_expert)
    
    # 创建执行者Agent
    executor = ExecutorAgent("executor-1")
    await multi_agent_system.add_agent(executor)
    
    # 添加任务到协调者
    await coordinator.add_agent(coding_expert)
    await coordinator.add_agent(research_expert)
    await coordinator.add_agent(executor)
    
    # 创建任务
    from xiaotie.multi_agent.coordinator import Task as MultiAgentTask
    task1 = MultiAgentTask(
        id="task-1",
        description="分析Python代码性能问题",
        metadata={"required_capabilities": ["expert_programming"]}
    )
    
    task2 = MultiAgentTask(
        id="task-2", 
        description="调研最新的AI技术趋势",
        metadata={"required_capabilities": ["expert_research"]}
    )
    
    coordinator.task_queue.extend([task1, task2])
    
    # 分发任务
    await coordinator.distribute_tasks()
    
    print("   ✅ 多Agent协作演示完成")


async def demo_memory_system():
    """演示记忆系统"""
    print("🧩 演示记忆系统...")
    
    # 创建记忆管理器
    memory_manager = MemoryManager()
    
    # 添加不同类型的记忆
    await memory_manager.add_memory(
        content="Python是一种高级编程语言",
        memory_type=MemoryType.SEMANTIC,
        importance=0.8,
        tags=["programming", "language", "python"]
    )
    
    await memory_manager.add_memory(
        content="今天完成了多Agent系统的设计",
        memory_type=MemoryType.EPISODIC,
        importance=0.9,
        tags=["work", "design", "multi-agent"]
    )
    
    # 检索记忆
    python_memories = await memory_manager.retrieve_memories("Python", top_k=5)
    print(f"   检索到 {len(python_memories)} 条关于Python的记忆")
    
    # 按标签搜索
    work_memories = await memory_manager.search_by_tags(["work"])
    print(f"   按标签检索到 {len(work_memories)} 条工作相关记忆")
    
    # 创建对话记忆
    conversation_memory = ConversationMemory(memory_manager)
    conversation_id = await conversation_memory.start_conversation("Python性能讨论")
    
    from xiaotie.schema import Message
    msg1 = Message(role="user", content="如何优化Python代码性能？")
    msg2 = Message(role="assistant", content="可以使用缓存、优化算法等方式")
    
    await conversation_memory.store_message(msg1)
    await conversation_memory.store_message(msg2)
    
    history = await conversation_memory.get_conversation_history()
    print(f"   对话历史包含 {len(history)} 条消息")
    
    summary = await conversation_memory.summarize_conversation()
    print(f"   对话总结: {summary[:50]}...")
    
    print("   ✅ 记忆系统演示完成")


async def demo_planning_system():
    """演示规划系统"""
    print("📋 演示规划系统...")
    
    # 创建规划系统
    planning_system = PlanningSystem()
    
    # 创建任务
    task_id = await planning_system.task_manager.create_task(
        description="开发一个天气预报应用",
        goal="创建一个能够获取并显示天气信息的应用",
        priority=Priority.HIGH
    )
    
    print(f"   创建任务: {task_id}")
    
    # 获取任务
    task = await planning_system.get_task_status(task_id)
    print(f"   任务状态: {task.status}")
    
    # 获取待处理任务
    pending_tasks = await planning_system.get_pending_tasks()
    print(f"   待处理任务数量: {len(pending_tasks)}")
    
    # 执行任务
    try:
        result = await planning_system.create_and_execute_task(
            description="实现用户界面设计",
            goal="创建直观易用的用户界面",
            priority=Priority.NORMAL
        )
        print(f"   任务执行完成: {result}")
    except Exception as e:
        print(f"   任务执行失败: {str(e)}")
    
    print("   ✅ 规划系统演示完成")


async def demo_reflection_system():
    """演示反思系统"""
    print("🤔 演示反思系统...")
    
    # 创建记忆管理器
    memory_manager = MemoryManager()
    
    # 创建反思管理器
    reflection_manager = ReflectionManager(memory_manager)
    
    # 触发不同类型的反思
    from xiaotie.reflection.core import ReflectionType
    
    context1 = {
        "task_result": "成功完成了数据分析任务",
        "task_goal": "分析销售数据趋势",
        "time_taken": 120,
        "execution_steps": ["数据加载", "数据清洗", "趋势分析"]
    }
    
    reflection1 = await reflection_manager.trigger_reflection(
        reflection_type=ReflectionType.TASK_EVALUATION,
        trigger_event="task_completed_successfully",
        context=context1
    )
    
    print(f"   任务评估反思完成，评分为: {reflection1.rating}")
    
    # 从reflection.core模块导入正确类型
    from xiaotie.reflection.core import ReflectionType
    
    context2 = {
        "previous_strategy": "逐步分析法",
        "outcome": "成功解决问题",
        "alternatives_tried": ["快速扫描法", "逐步分析法"]
    }
    
    reflection2 = await reflection_manager.trigger_reflection(
        reflection_type=ReflectionType.STRATEGY_ADJUSTMENT,
        trigger_event="strategy_evaluated",
        context=context2
    )
    
    print(f"   策略调整反思完成，评分为: {reflection2.rating}")
    
    # 获取洞察摘要
    insights = await reflection_manager.get_insights_summary()
    print(f"   反思系统中有 {len(insights)} 种类型的洞察")
    
    print("   ✅ 反思系统演示完成")


async def demo_integrated_system():
    """演示集成系统"""
    print("🎯 演示集成系统...")
    
    # 创建记忆管理器
    memory_manager = MemoryManager()
    
    # 创建各子系统
    planning_system = PlanningSystem()
    reflection_manager = ReflectionManager(memory_manager)
    
    # 展示如何将各子系统集成在一起
    # （不实际构建Agent以避免API密钥问题）
    
    print("   演示如何集成记忆、规划和反思系统...")
    
    # 模拟一个任务流程
    task_description = "分析并优化Web应用性能"
    task_goal = "识别性能瓶颈并提供优化建议"
    
    # 1. 规划系统：创建任务
    task_id = await planning_system.task_manager.create_task(
        description=task_description,
        goal=task_goal,
        priority=Priority.HIGH
    )
    
    print(f"   - 规划系统创建任务: {task_description}")
    
    # 2. 记忆系统：记录任务相关信息
    await memory_manager.add_memory(
        content=f"新任务: {task_description}",
        memory_type=MemoryType.EPISODIC,
        importance=0.9,
        tags=["task", "performance", "optimization"]
    )
    
    print(f"   - 记忆系统记录任务信息")
    
    # 3. 反思系统：评估任务执行策略
    from xiaotie.reflection.core import ReflectionType
    
    context = {
        "task_description": task_description,
        "task_goal": task_goal,
        "approach": "performance_analysis"
    }
    
    await reflection_manager.trigger_reflection(
        reflection_type=ReflectionType.TASK_EVALUATION,
        trigger_event="task_created",
        context=context
    )
    
    print(f"   - 反思系统评估任务策略")
    
    # 4. 获取系统间的协同效果
    task_memories = await memory_manager.search_by_tags(["task"])
    print(f"   - 记忆系统中包含 {len(task_memories)} 个任务相关条目")
    
    reflection_count = len(reflection_manager.reflection_history)
    print(f"   - 反思系统中包含 {reflection_count} 条反思记录")
    
    pending_tasks = await planning_system.get_pending_tasks()
    print(f"   - 规划系统中有 {len(pending_tasks)} 个待处理任务")
    
    print("   ✅ 集成系统演示完成")


async def main():
    """主函数"""
    print("🚀 小铁框架 v0.9.2 综合演示\n")
    
    await demo_multi_agent_collaboration()
    print()
    
    await demo_memory_system()
    print()
    
    await demo_planning_system()
    print()
    
    await demo_reflection_system()
    print()
    
    await demo_integrated_system()
    print()
    
    print("🎉 所有演示完成！小铁框架 v0.9.2 功能齐全。")


if __name__ == "__main__":
    asyncio.run(main())