# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2025-01-15

### Added
- **认知架构增强** - 全面的认知能力提升
  - `AdaptiveLearner` - 自适应学习器，基于经验自我改进
  - `ContextManager` - 上下文感知管理器，理解环境和历史
  - `DecisionEngine` - 智能决策引擎，基于目标和上下文做决策
  - `SkillLearningAgentMixin` - Agent 技能学习混入
  - `KnowledgeGraphManager` - 知识图谱管理器，实体关系推理
  - `ReinforcementLearningEngine` - 强化学习引擎，基于奖励学习
  - `PlanningSystem` - 智能规划系统，任务分解与执行
  - `ReflectionManager` - 反思管理器，经验总结与改进

## [1.0.1] - 2025-01-10

### Changed
- 事件系统优化 - 使用弱引用防止内存泄漏，改进异步性能
- 缓存系统增强 - 实现异步 LRU 缓存，支持 TTL 和 LRU 淘汰策略
- 记忆系统优化 - 改进容量管理，使用堆优化清理策略
- 工具执行监控 - 异步指标记录，不阻塞主执行流程
- 计划执行优化 - 支持并行执行模式，按依赖关系分组执行
- 异步性能改进 - 使用 perf_counter 高精度计时，优化异步任务调度

## [1.0.0] - 2025-01-05

### Added
- **知识图谱集成** - 实现知识图谱的构建、存储、查询和推理
  - `KnowledgeGraphManager` - 知识图谱管理器
  - `KnowledgeGraphAgentMixin` - 知识图谱 Agent 混入
  - 基于 NetworkX 的图存储和分析
  - 实体关系提取和路径推理
  - 知识查询和概念映射功能

## [0.9.9] - 2024-12-28

### Added
- **强化学习机制** - 实现基于奖励的强化学习算法
  - `ReinforcementLearningEngine` - 强化学习引擎
  - `RLAgentMixin` - 强化学习 Agent 混入
  - 支持 Q-Learning、SARSA、Monte Carlo 等算法
  - 动作价值评估和策略优化
  - 自适应参数调整和经验回放

## [0.9.8] - 2024-12-20

### Added
- **多模态支持** - 实现图像、音频、视频等多模态数据处理
  - `MultimodalContentManager` - 多模态内容管理器
  - `MultimodalAgentMixin` - 多模态 Agent 混入
  - 支持文本、图像、音频、视频、文档等模态
  - 图像分析和文档分析工具
  - 内容缓存和内容搜索功能

## [0.9.7] - 2024-12-15

### Added
- **技能学习系统** - 实现 Agent 技能的获取、评估和改进
  - `SkillLearningAgentMixin` - 技能学习 Agent 混入
  - `SkillAcquirer` - 技能获取器
  - 多种技能类型 (工具使用、沟通、问题解决等)
  - 技能评估和反馈机制
  - 知识迁移和推荐系统

## [0.9.6] - 2024-12-10

### Added
- **上下文窗口管理** - 实现动态上下文窗口管理和优化
  - `ContextWindowManager` - 上下文窗口管理器
  - `ContextAwareWindowManager` - 上下文感知窗口管理器
  - 多种压缩方法 (摘要、截断、滑动窗口、相关性过滤)
  - 自适应窗口大小调整
  - 压缩分析和性能指标

## [0.9.5] - 2024-12-05

### Added
- **智能决策引擎** - 实现基于上下文和学习经验的智能决策
  - `DecisionEngine` - 决策引擎
  - `DecisionAwareAgentMixin` - 决策感知 Agent 混入
  - 多种决策策略 (效用基础、概率型、规则基础)
  - 决策评估和影响分析

## [0.9.4] - 2024-12-01

### Added
- **上下文感知** - 实现智能上下文理解和管理
  - `ContextManager` - 上下文管理器
  - `ContextAwareAgentMixin` - 上下文感知 Agent 混入
  - 多种上下文类型 (对话、主题、时间、任务等)
  - 实体提取和关系计算
  - 显著性评分和话题转换检测

## [0.9.3] - 2024-11-25

### Added
- **自适应学习** - 实现持续学习和自我改进
  - `AdaptiveLearner` - 自适应学习器
  - `LearningAgentMixin` - 学习型 Agent 混入
  - 多种学习策略 (强化学习、监督学习、无监督学习)
  - 技能熟练度管理
  - 学习目标设定与追踪

## [0.9.2] - 2024-11-20

### Added
- **多 Agent 协作** - 实现多 Agent 协同工作机制
  - `MultiAgentSystem` - 多 Agent 系统管理器
  - `CoordinatorAgent` - 任务协调者
  - `ExpertAgent` - 专业领域专家
  - `ExecutorAgent` - 任务执行者
  - `SupervisorAgent` - 质量监督者
- **记忆系统** - 实现短期和长期记忆管理
  - `MemoryManager` - 统一记忆管理
  - `ConversationMemory` - 对话记忆管理
  - 支持多种记忆类型 (短期、长期、情节、语义)
- **规划系统** - 实现任务分解和进度跟踪
  - `PlanningSystem` - 统一规划管理
  - `TaskManager` - 任务生命周期管理
  - `PlanExecutor` - 计划执行器
- **反思机制** - 实现自我评估和学习能力
  - `ReflectionManager` - 反思管理器
  - `ReflectiveAgentMixin` - 反思式 Agent 混入

## [0.9.1] - 2024-11-15

### Changed
- 性能优化 - 改进事件系统，使用弱引用防止内存泄漏
- `AsyncLRUCache` 异步缓存系统，支持 TTL 和 LRU 淘汰
- `EventBroker` 使用弱引用优化内存管理

### Added
- `SystemInfoTool` - 获取系统软硬件信息
- `ProcessManagerTool` - 管理和监控系统进程
- `NetworkTool` - 执行网络诊断和扫描操作
- 统一日志管理系统，支持文件和控制台输出

## [0.9.0] - 2024-11-10

### Added
- **Agent SDK v2** - 声明式 Agent 构建
  - `AgentBuilder` 构建器模式，链式 API
  - `AgentSpec` YAML/JSON 配置支持
  - 生命周期 hooks (on_start, on_step, on_tool_call, on_complete)
- **Provider 适配层** - 统一 LLM 接口
  - 新增 Gemini、DeepSeek、Qwen 支持
  - 能力矩阵 (流式、工具调用、并行工具、视觉)
  - 自动路由/降级策略
- **命令面板增强** - 模糊搜索算法
- **首次启动向导** - 零配置体验
- **流式渲染优化** - 50ms 防抖动更新
- **测试模块** - Cassette 录制/回放系统

## [0.8.2] - 2024-11-05

### Added
- **主题管理器** - `ThemeManager` 单例模式管理主题状态
- 主题变更事件订阅/发布机制
- `ThemeSelectorItem` - 带颜色预览的主题选择项

## [0.8.1] - 2024-11-01

### Added
- **TUI 优化** - 参考 OpenCode 像素级复刻
  - 10 个主题配色 (Nord, Dracula, Catppuccin, Tokyo Night 等)
  - 模型选择器 (Ctrl+M)、主题选择器 (Ctrl+T)
  - Toast 通知系统、Nerd Font 图标支持

## [0.8.0] - 2024-10-25

### Added
- **语义搜索** - 基于向量的代码语义搜索
  - 使用 ChromaDB 向量数据库
  - 支持 OpenAI Embeddings
  - 自动代码分块 (按函数/类)
- `xiaotie/search/` 模块

## [0.7.0] - 2024-10-15

### Added
- **SQLite 持久化** - 高性能存储系统
  - 使用 aiosqlite 异步操作
  - WAL 模式提高并发性能
- `xiaotie/storage/` 模块

## [0.6.1] - 2024-10-10

### Added
- **多 Agent 协作** - Agent 角色系统
  - 轻量级 TaskAgent、AgentCoordinator 协调器
- `xiaotie/multi_agent/` 模块

## [0.6.0] - 2024-10-05

### Added
- **测试基础设施** - pytest 配置、单元测试、集成测试、CI

## [0.5.2] - 2024-09-28

### Added
- **LSP 集成** - 语言服务器协议支持
- `xiaotie/lsp/` 模块

## [0.5.1] - 2024-09-20

### Added
- **自定义命令系统** - 参考 OpenCode 设计
  - 用户命令、项目命令、命名参数、子目录组织

## [0.5.0] - 2024-09-15

### Added
- **MCP 协议支持** - Model Context Protocol 客户端
- `xiaotie/mcp/` 模块

## [0.4.3] - 2024-09-10

### Added
- 权限系统 - Human-in-the-Loop 安全机制
- Lint/Test 反馈循环
- Profile 配置系统
- 增强 Bash 工具 - 持久化 Shell 会话

### Fixed
- 修复 asyncio 事件循环冲突问题

## [0.4.2] - 2024-09-05

### Changed
- **TUI 重构** - 完全参考 OpenCode 设计
- 分割布局、Ctrl+K 命令面板、侧边栏切换
- 事件驱动架构 (Pub/Sub)
- 会话状态管理、智能摘要优化

## [0.4.1] - 2024-09-01

### Added
- 增强输入 - 命令自动补全、历史记录、Ctrl+R 搜索
- 新命令: /config, /status, /compact, /copy, /undo, /retry

### Fixed
- GLM-4.7 参数传递、重复输出问题

## [0.4.0] - 2024-08-25

### Added
- **TUI 模式** - 基于 Textual 的现代化终端界面
- 非交互模式 (`-p` 参数)、JSON 输出 (`-f json`)
- 命令面板 (Ctrl+P)

## [0.3.1] - 2024-08-20

### Added
- 工具并行执行 (asyncio.gather)
- 插件系统 - 自定义工具热加载

## [0.3.0] - 2024-08-15

### Added
- 命令系统重构
- 显示增强 (rich 库)
- 代码库感知 (RepoMap)
- Git 工具、Web 搜索/获取工具

## [0.2.0] - 2024-08-10

### Added
- 流式输出 + 深度思考
- 会话管理
- Python/计算器工具
- GLM-4.7/MiniMax 适配

## [0.1.0] - 2024-08-01

### Added
- 初始版本
- Agent 执行循环
- 文件/Bash 工具
- 多 LLM Provider 支持
