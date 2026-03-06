# Changelog

所有版本的重要变更记录。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [2.1.0] - 2026-03-07

### Integration (v2.0 modules wired into main flow)

- **AgentRuntime 接入 CLI/TUI** — `_setup_agent()` 现在创建 `AgentRuntime` 替代 `Agent`，旧 API 标记 `DeprecationWarning`
- **ContextEngine 接入 AgentRuntime** — LLM 调用前自动使用 token 预算组装上下文，支持优先级裁剪
- **RepoMapEngine 接入 AgentRuntime** — 自动从对话中提取文件路径，生成 PageRank 排序的代码地图
- **SecretManager 接入 Config.load()** — 配置加载时自动解析 `${secret:...}` / `${env:...}` 占位符
- **`/secret` 命令注册** — 交互模式中可直接使用 `/secret set|get|list|delete|migrate`

### Added

- `AgentRuntime._build_context_messages()` — 上下文构建方法，整合 ContextEngine + RepoMap
- `AgentRuntime._extract_mentioned_files()` — 从对话历史中提取代码文件路径
- 80+ 行兼容性 shim (tools, llm, stream, on_thinking, on_content 等属性)
- 21 个新测试用例 (context integration, file extraction, compatibility shims)

### Changed

- `Agent.__init__()` 现在发出 `DeprecationWarning`，建议迁移到 `AgentRuntime`
- `xiaotie/tui/main.py` 使用 `AgentRuntime` 替代 `Agent`
- 版本号: 2.0.0 → 2.1.0

### Test Results

- 1703 测试通过 / 15 跳过
- 覆盖率 61% (runtime 97%, executor 90%, secrets 91%, context_engine 90%)

---

## [2.0.0] - 2026-03-06

### Breaking Changes

- **AgentRuntime** 替代内部 Agent 循环（`Agent` 类仍可使用，保持向后兼容）
- 配置文件中的明文 API Key 应迁移到 keyring（`xiaotie secret migrate`）
- Prometheus 指标默认绑定 `127.0.0.1`（原为 `0.0.0.0`）
- 数据库序列化从 pickle 变更为 JSON

### New Features

- **AgentRuntime 状态机**: 显式状态机驱动 Agent 循环 (IDLE->THINKING->ACTING->OBSERVING->REFLECTING)，合法状态转移检查，运行时统计和遥测
- **ToolExecutor**: 从 Agent god class 提取的工具执行器，支持顺序/并行执行、权限检查、审计日志、敏感输出自动脱敏
- **ResponseHandler**: 流式/非流式 LLM 响应统一处理，Token 增量统计、预算管理、历史消息自动摘要
- **ContextEngine**: Token 预算上下文组装，优先级分配 (system 10% / repo_map 15% / memory 15% / conversation 50% / skills 5%)，超预算自动裁剪低优先级块
- **RepoMapEngine**: tree-sitter AST 解析 + NetworkX PageRank 代码导航，支持 Python/JS/TS/Go/Rust/Java/C/C++ 8 种语言，SQLite 标签缓存，正则 fallback
- **SandboxManager**: OS 级沙箱执行 (macOS Seatbelt / Linux Bubblewrap / Fallback rlimits)，基于 Capability 的权限模型 (READ_FS/WRITE_FS/NETWORK/SUBPROCESS/DANGEROUS)
- **SecretManager**: 分层密钥管理 (keyring -> 环境变量 -> 配置 fallback)，`${secret:...}` 和 `${env:...}` 配置占位符，明文密钥自动迁移
- **Secret CLI**: `xiaotie secret set/get/list/delete/migrate` 命令
- **CI/CD**: GitHub Actions 工作流 (lint/test/security/perf)，pre-commit hooks
- **AgentTelemetry**: 运行时遥测、工具调用延迟追踪、流式刷新统计

### Bug Fixes

- 修复 PythonTool 沙箱执行缺少 `await` 的问题
- 修复 Prometheus 指标绑定到 `0.0.0.0` (改为 `127.0.0.1`)
- 修复不安全的 pickle 反序列化 (改为 JSON)
- 修复 db_tool.py 中的 SQL 注入风险
- 修复全局单例线程安全问题 (events, database)
- 修复敏感输出过滤器误报问题 (改用高特异性正则)
- 修复 Token 估算增量计算在消息减少时的缓存不一致

### Security

- 文件工具路径遍历保护 (SandboxManager 强制工作区范围)
- Bash 工具危险命令检测 (ToolGuardrail 管线)
- 配置文件移除硬编码 API Key，推荐 keyring 管理
- 全面使用参数化查询，禁止原始 SQL
- 敏感输出检测: AWS Access Key、GitHub Token、GitLab Token、私钥、凭据赋值
- 沙箱环境变量过滤 (自动剥离 AWS_/ANTHROPIC_API/OPENAI_API/SSH_ 等前缀)

## [1.1.0] - 2026-02-01

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
- **内置 HTTP/HTTPS 代理服务器** - 基于 mitmproxy
- **多线程网络爬虫模块**
- **macOS 微信小程序自动化**
- 1264 个测试，97.4% 通过率，55.15% 代码覆盖率

## [1.0.1] - 2025-01-10

### Changed

- 事件系统优化 - 使用弱引用防止内存泄漏，改进异步性能
- 缓存系统增强 - 实现异步 LRU 缓存，支持 TTL 和 LRU 淘汰策略
- 记忆系统优化 - 改进容量管理，使用堆优化清理策略

## [1.0.0] - 2025-01-05

### Added

- **知识图谱集成** - 知识图谱的构建、存储、查询和推理

## [0.9.0] - 2024-11-10

### Added

- **Agent SDK v2** - AgentBuilder 构建器模式、YAML 配置
- **Provider 适配层** - 新增 Gemini、DeepSeek、Qwen 支持
- **测试模块** - Cassette 录制/回放系统

## [0.8.0] - 2024-10-25

### Added

- **语义搜索** - ChromaDB 向量数据库
- **SQLite 持久化** - aiosqlite 异步存储

## [0.5.0] - 2024-09-15

### Added

- **MCP 协议支持** - Model Context Protocol 客户端

## [0.4.0] - 2024-08-25

### Added

- **TUI 模式** - 基于 Textual 的终端界面
- 非交互模式、JSON 输出

## [0.3.0] - 2024-08-15

### Added

- 命令系统、显示增强、RepoMap、Git/Web 工具

## [0.1.0] - 2024-08-01

### Added

- 初始版本 - Agent 循环、文件/Bash 工具、多 LLM 支持
