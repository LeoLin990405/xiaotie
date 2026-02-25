# 认知架构使用指南

> 小铁 (XiaoTie) v1.1.0 认知模块完整使用手册

## 概述

小铁的认知架构由 9 个模块组成，分为 5 个层次。每个模块可独立使用，也可通过 Mixin 模式组合到 Agent 中。

```
L4 能力层:  SkillAcquirer | KnowledgeGraphManager | MultimodalContentManager
L3 决策层:  DecisionEngine | PlanningSystem
L2 学习层:  AdaptiveLearner | ReinforcementLearningEngine
L1 感知层:  ContextManager | ReflectionManager
L0 基础层:  MemoryManager | EventBroker
```

---

## 1. 记忆系统 (MemoryManager)

记忆系统是认知架构的基础，提供五种记忆类型和两种存储后端。

### 记忆类型

| 类型 | 用途 | 默认容量 |
|------|------|----------|
| `SHORT_TERM` | 临时工作缓冲 | 100 |
| `LONG_TERM` | 持久化知识 | 10000 |
| `EPISODIC` | 事件序列记录 | 1000 |
| `SEMANTIC` | 概念和语义网络 | 5000 |
| `WORKING` | 当前任务上下文 | 50 |

### 基本用法

```python
from xiaotie import MemoryManager, MemoryType, MemoryChunk

# 创建记忆管理器（内存后端）
memory = MemoryManager()

# 存储记忆
chunk = MemoryChunk(
    content="用户偏好使用 Python 进行数据分析",
    memory_type=MemoryType.LONG_TERM,
    importance=0.8,
    metadata={"source": "conversation", "topic": "preference"}
)
await memory.store(chunk)

# 检索记忆
results = await memory.retrieve(
    query="用户的编程偏好",
    memory_type=MemoryType.LONG_TERM,
    limit=5
)

# 使用数据库后端（持久化）
from xiaotie.memory.core import DatabaseBackend
db_backend = DatabaseBackend(db_path="memory.db")
persistent_memory = MemoryManager(backend=db_backend)
```

### 对话记忆

```python
from xiaotie import ConversationMemory

conv_memory = ConversationMemory(max_turns=50)
conv_memory.add_message(role="user", content="帮我写一个排序算法")
conv_memory.add_message(role="assistant", content="好的，这是快速排序...")

# 获取最近对话
recent = conv_memory.get_recent(n=10)
```

---

## 2. 上下文感知 (ContextManager)

上下文管理器负责从对话中提取实体、检测话题转换、评估上下文相关性。

### 基本用法

```python
from xiaotie import ContextManager, ContextType

# 创建上下文管理器（可注入记忆系统）
ctx = ContextManager(memory_manager=memory)

# 更新上下文
frame = await ctx.update_context(
    user_input="我想用 pandas 分析这个 CSV 文件",
    conversation_history=recent
)

# 获取当前上下文帧
current = ctx.get_current_frame()
print(current.entities)      # 提取的实体: ["pandas", "CSV"]
print(current.topic)         # 当前话题
print(current.context_type)  # ContextType.TOPICAL

# 检测话题转换
shifted = ctx.detect_topic_shift(
    previous="我们讨论排序算法",
    current="帮我配置 Docker"
)
```

### 通过 Mixin 集成

```python
from xiaotie import ContextAwareAgentMixin

class MyAgent(ContextAwareAgentMixin):
    def __init__(self):
        self.context_manager = ContextManager()

    async def process(self, user_input):
        # Mixin 提供的上下文感知方法
        frame = await self.update_context(user_input)
        # 利用上下文做出响应...
```

---

## 3. 决策引擎 (DecisionEngine)

决策引擎支持三种策略：效用评估、概率选择（softmax）、规则匹配，并内置 epsilon-greedy 探索机制。

### 基本用法

```python
from xiaotie import DecisionEngine, DecisionOption, DecisionStrategy

# 创建决策引擎（注入依赖）
engine = DecisionEngine(
    context_manager=ctx,
    learner=learner,          # 可选
    memory_manager=memory     # 可选
)

# 定义选项
options = [
    DecisionOption(
        name="use_pandas",
        description="使用 pandas 处理数据",
        utility=0.85,
        metadata={"tool": "pandas"}
    ),
    DecisionOption(
        name="use_sql",
        description="使用 SQL 查询数据",
        utility=0.72,
        metadata={"tool": "sqlite"}
    ),
]

# 做出决策
outcome = await engine.make_decision(
    options=options,
    strategy=DecisionStrategy.UTILITY_BASED,
    context=current_frame
)
print(outcome.chosen_option)  # "use_pandas"
print(outcome.confidence)     # 0.85
```

### 探索与利用

```python
# epsilon-greedy: 10% 概率随机探索
engine = DecisionEngine(epsilon=0.1)

# 概率策略: softmax 温度控制
outcome = await engine.make_decision(
    options=options,
    strategy=DecisionStrategy.PROBABILISTIC
)
```

---

## 4. 自适应学习 (AdaptiveLearner)

学习系统支持 Q-Learning、监督学习、无监督学习三种算法，自动根据性能切换策略。

### 基本用法

```python
from xiaotie import AdaptiveLearner, LearningStrategy, Skill

# 创建学习器
learner = AdaptiveLearner(
    memory_manager=memory,
    reflection_manager=reflection  # 可选
)

# 记录学习经验
await learner.learn(
    state="user_asks_data_analysis",
    action="suggest_pandas",
    reward=1.0,  # 正反馈
    next_state="user_satisfied"
)

# 查询最佳行动
best_action = await learner.get_best_action(
    state="user_asks_data_analysis"
)

# 技能追踪
skill = Skill(
    name="python_data_analysis",
    proficiency=0.6,
    practice_count=15
)
await learner.update_skill(skill, performance=0.85)
print(skill.proficiency)  # 提升后的熟练度
```

### 策略自适应

```python
# 学习器自动根据性能切换策略
# 初始: Q-Learning -> 性能下降时切换到监督学习
learner = AdaptiveLearner(
    initial_strategy=LearningStrategy.Q_LEARNING,
    adaptation_threshold=0.3  # 性能下降 30% 时切换
)
```

---

## 5. 反思系统 (ReflectionManager)

反思系统包含 5 种反思器，支持多维度的自我评估和策略调整。

### 反思器类型

| 反思器 | 职责 |
|--------|------|
| `TaskEvaluator` | 评估任务完成质量 |
| `StrategyAdjuster` | 调整执行策略 |
| `KnowledgeUpdater` | 更新知识库 |
| `BehaviorLearner` | 学习行为模式 |
| `PerformanceAnalyzer` | 分析整体性能趋势 |

### 基本用法

```python
from xiaotie import ReflectionManager, ReflectionType

reflection = ReflectionManager(memory_manager=memory)

# 触发反思
result = await reflection.reflect(
    context={
        "task": "数据分析",
        "outcome": "成功",
        "duration": 5.2,
        "user_satisfaction": 0.9
    },
    reflection_type=ReflectionType.TASK_EVALUATION
)
print(result.insights)       # 反思洞察
print(result.suggestions)    # 改进建议

# 全面反思（触发所有反思器）
all_results = await reflection.full_reflection(context)
```

---

## 6. 规划系统 (PlanningSystem)

规划系统支持任务分解、依赖管理、拓扑排序并行执行。

### 基本用法

```python
from xiaotie import PlanningSystem, PlanningTask, Priority, TaskStatus

planning = PlanningSystem()

# 创建任务
task = PlanningTask(
    name="构建数据管道",
    description="从 CSV 读取、清洗、分析、可视化",
    priority=Priority.HIGH
)

# 自动分解为子步骤
plan = await planning.create_plan(task)
for step in plan.steps:
    print(f"{step.order}. {step.name} (依赖: {step.dependencies})")

# 执行计划（支持并行步骤）
executor = planning.get_executor()
results = await executor.execute(plan)
```

### 自适应规划

```python
from xiaotie.planning.core import AdaptivePlanner

# 自适应规划器根据执行反馈动态调整计划
planner = AdaptivePlanner()
plan = await planner.create_plan(task)

# 步骤失败时自动重新规划
await executor.execute(plan, on_failure="replan")
```

---

## 7. 技能习得 (SkillAcquirer)

技能系统模拟人类技能发展的 5 个阶段，支持多种习得方式。

### 发展阶段

```
NOVICE -> ADVANCED_BEGINNER -> COMPETENT -> PROFICIENT -> EXPERT
```

### 基本用法

```python
from xiaotie import SkillAcquirer, SkillAcquisitionMethod, SkillType

acquirer = SkillAcquirer(learner=learner, memory_manager=memory)

# 通过练习习得技能
await acquirer.acquire(
    skill_name="code_review",
    skill_type=SkillType.COGNITIVE,
    method=SkillAcquisitionMethod.PRACTICE,
    examples=[...]  # 练习样本
)

# 通过迁移学习
await acquirer.transfer_learn(
    source_skill="python_coding",
    target_skill="javascript_coding",
    transfer_ratio=0.6  # 60% 知识可迁移
)

# 查看技能发展阶段
stage = acquirer.get_development_stage("code_review")
# SkillDevelopmentStage.COMPETENT
```

---

## 8. 强化学习引擎 (ReinforcementLearningEngine)

提供 Q-Table、SARSA、Monte Carlo 三种经典 RL 算法，支持经验回放。

### 基本用法

```python
from xiaotie import ReinforcementLearningEngine, RLAlgorithm, State, Action

rl = ReinforcementLearningEngine(
    algorithm=RLAlgorithm.Q_TABLE,
    learning_rate=0.1,
    discount_factor=0.95,
    epsilon=0.1
)

# 定义状态和动作
state = State(features={"task_type": "coding", "complexity": "high"})
action = Action(name="use_chain_of_thought")

# 学习
await rl.update(state, action, reward=1.0, next_state=new_state)

# 选择最优动作
best = await rl.select_action(state)

# 经验回放
rl.store_experience(state, action, reward, next_state)
await rl.replay(batch_size=32)
```

---

## 9. 知识图谱 (KnowledgeGraphManager)

基于 NetworkX 的知识图谱，支持实体关系管理、PageRank、路径查找、关系推理。

### 基本用法

```python
from xiaotie import (
    KnowledgeGraphManager, KGNode, KGEdge,
    NodeType, RelationType,
    KnowledgeGraphBuilder, KnowledgeGraphQueryEngine
)

kg = KnowledgeGraphManager()

# 添加节点和边
python_node = KGNode(name="Python", node_type=NodeType.CONCEPT)
pandas_node = KGNode(name="Pandas", node_type=NodeType.CONCEPT)
await kg.add_node(python_node)
await kg.add_node(pandas_node)

edge = KGEdge(
    source="Python", target="Pandas",
    relation=RelationType.HAS_PART
)
await kg.add_edge(edge)

# 从文本自动构建
builder = KnowledgeGraphBuilder(kg)
await builder.build_from_text(
    "Python 是一种编程语言，Pandas 是 Python 的数据分析库"
)

# 查询
query_engine = KnowledgeGraphQueryEngine(kg)
results = await query_engine.query("Python 相关的库有哪些？")
pagerank = await query_engine.get_pagerank()
path = await query_engine.find_path("Python", "数据分析")
```

---

## 10. Mixin 组合最佳实践

### 推荐组合

```python
# 基础 Agent: 记忆 + 上下文
class BasicAgent(ContextAwareAgentMixin):
    pass

# 学习型 Agent: + 学习 + 反思
class LearningAgent(
    ContextAwareAgentMixin,
    LearningAgentMixin,
    ReflectiveAgentMixin,
):
    pass

# 全能 Agent: 所有认知能力
class FullCognitiveAgent(
    ContextAwareAgentMixin,
    DecisionAwareAgentMixin,
    LearningAgentMixin,
    ReflectiveAgentMixin,
    SkillLearningAgentMixin,
    RLAgentMixin,
    KnowledgeGraphAgentMixin,
    MultimodalAgentMixin,
):
    pass
```

### 初始化顺序

认知模块有依赖关系，初始化时应遵循从底层到高层的顺序：

```python
# 1. 基础层
memory = MemoryManager()
event_broker = EventBroker()

# 2. 感知层
context = ContextManager(memory_manager=memory)
reflection = ReflectionManager(memory_manager=memory)

# 3. 学习层
learner = AdaptiveLearner(memory_manager=memory, reflection_manager=reflection)

# 4. 决策层
decision = DecisionEngine(
    context_manager=context,
    learner=learner,
    memory_manager=memory
)
planning = PlanningSystem()

# 5. 能力层
skills = SkillAcquirer(learner=learner, memory_manager=memory)
kg = KnowledgeGraphManager(memory_manager=memory)
```

### 使用 AgentBuilder（推荐）

```python
from xiaotie import AgentBuilder

agent = (
    AgentBuilder()
    .with_provider("anthropic", model="claude-sonnet-4-20250514")
    .with_memory()
    .with_context()
    .with_decision()
    .with_learning()
    .with_reflection()
    .build()
)
```

---

## 11. 事件监听

所有认知模块的活动都通过 EventBroker 发布事件，可用于监控和调试。

```python
from xiaotie import EventBroker, EventType, get_event_broker

broker = get_event_broker()

# 订阅事件
queue = await broker.subscribe([
    EventType.AGENT_START,
    EventType.TOOL_START,
    EventType.TOOL_COMPLETE,
])

# 消费事件
while True:
    event = await queue.get()
    print(f"[{event.type.value}] {event.data}")
```