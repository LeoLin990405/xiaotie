# ⚙️ 小铁 (XiaoTie)

轻量级 AI Agent 框架，基于 [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，参考 [OpenCode](https://github.com/opencode-ai/opencode) 设计。

```
 ▄███▄     小铁 XiaoTie v0.9.0
 █ ⚙ █    GLM-4.7 · OpenAI
 ▀███▀     ~/workspace
```

## 特性

### 核心功能
- 🔄 **Agent 执行循环** - 自动工具调用与任务完成
- 🌊 **流式输出** - 实时显示思考过程和回复
- 💭 **深度思考** - 支持 GLM-4.7 thinking 模式
- 💾 **会话管理** - 保存/加载对话历史
- 📝 **Token 管理** - 自动摘要历史消息
- ⚡ **优雅取消** - 支持 Ctrl+C 中断
- 🚀 **并行工具执行** - 多工具调用并行执行，提升效率
- 🖥️ **TUI 模式** - 基于 Textual 的现代化终端界面
- 📤 **非交互模式** - 支持单次查询和 JSON 输出
- 🔌 **MCP 协议支持** - 连接 MCP 服务器，扩展工具能力
- 🔬 **LSP 集成** - 语言服务器协议，实时诊断
- 🤖 **多 Agent 协作** - 子任务分解与并行执行
- 💾 **SQLite 持久化** - 高性能会话与消息存储
- 🔍 **语义搜索** - 基于向量的代码语义搜索

### 工具系统
- 📁 **文件操作** - 读取、写入、编辑文件
- 🖥️ **Bash 命令** - 执行 shell 命令
- 🐍 **Python 执行** - 运行 Python 代码
- 🔢 **计算器** - 数学计算
- 🌿 **Git 操作** - 版本控制（status/diff/log/commit）
- 🔍 **Web 搜索** - DuckDuckGo 搜索
- 🌐 **网页获取** - 获取网页内容
- 📊 **代码分析** - 提取类、函数、依赖关系
- 🔎 **语义搜索** - 基于向量的代码语义搜索

### 代码库感知 (RepoMap)
- 📂 **目录树** - 可视化项目结构
- 🗺️ **代码映射** - 提取类、函数定义
- 🔎 **智能搜索** - 按关键词查找相关文件

### 多 LLM 支持
- 🤖 **Anthropic Claude** - Claude 3.5/4 系列
- 🧠 **OpenAI GPT** - GPT-4o 等
- 🔮 **智谱 GLM-4.7** - 深度思考 + 工具流式
- 🌈 **MiniMax** - abab 系列
- 🌟 **Google Gemini** - Gemini Pro/Flash (v0.9.0 新增)
- 🔷 **DeepSeek** - DeepSeek Chat/Coder (v0.9.0 新增)
- 🟣 **Qwen** - 通义千问系列 (v0.9.0 新增)

## 安装

```bash
# 克隆项目
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie

# 基础安装
pip install -e .

# 安装 TUI 支持
pip install -e ".[tui]"

# 安装语义搜索支持
pip install -e ".[search]"

# 安装所有功能
pip install -e ".[all]"
```

## 配置

1. 复制配置文件模板：

```bash
cp config/config.yaml.example config/config.yaml
```

2. 编辑 `config/config.yaml`，填入你的 API Key：

```yaml
# Anthropic Claude
api_key: YOUR_API_KEY
api_base: https://api.anthropic.com
model: claude-sonnet-4-20250514
provider: anthropic

# 或者 智谱 GLM-4.7
api_key: YOUR_API_KEY
api_base: https://open.bigmodel.cn/api/coding/paas/v4
model: GLM-4.7
provider: openai
```

### MCP 配置

小铁支持 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)，可以连接 MCP 服务器扩展工具能力。

在 `config/config.yaml` 中添加 MCP 配置：

```yaml
# MCP 配置
mcp:
  enabled: true  # 启用 MCP 支持
  servers:
    # 文件系统服务器
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      enabled: true

    # GitHub 服务器
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "your-token"
      enabled: true
```

启动后，MCP 服务器提供的工具会自动加载，工具名称格式为 `mcp_<服务器名>_<工具名>`。

## 使用

### 命令行模式

```bash
# 启动交互式 CLI
xiaotie

# 启动 TUI 模式 (需要安装 tui 依赖)
xiaotie --tui

# 非交互模式 - 直接执行查询
xiaotie -p "帮我分析这段代码"

# JSON 输出格式
xiaotie -p "你好" -f json

# 安静模式 - 只输出结果
xiaotie -p "1+1等于多少" -q

# 禁用流式输出
xiaotie --no-stream

# 禁用深度思考
xiaotie --no-thinking
```

### TUI 模式快捷键

| 快捷键 | 说明 |
|--------|------|
| `Ctrl+K` | 打开命令面板 |
| `Ctrl+B` | 切换侧边栏 |
| `Ctrl+N` | 新建会话 |
| `Ctrl+S` | 保存会话 |
| `Ctrl+L` | 清屏 |
| `Ctrl+Q` | 退出 |
| `F1` | 帮助 |

### CLI 命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `/help` | `/h`, `/?` | 显示帮助 |
| `/quit` | `/q`, `/exit` | 退出程序 |
| `/reset` | `/r` | 重置对话 |
| `/tools` | `/t` | 显示可用工具 |
| `/save` | `/s` | 保存当前会话 |
| `/load <id>` | `/l` | 加载会话 |
| `/sessions` | | 列出所有会话 |
| `/new [标题]` | | 创建新会话 |
| `/stream` | | 切换流式输出 |
| `/think` | | 切换深度思考 |
| `/parallel` | | 切换工具并行执行 |
| `/tokens` | `/tok` | 显示 Token 使用 |
| `/config` | `/cfg` | 显示当前配置 |
| `/status` | | 显示系统状态 |
| `/compact` | | 压缩对话历史 |
| `/copy` | | 复制最后回复到剪贴板 |
| `/undo` | | 撤销最后一轮对话 |
| `/retry` | | 重试最后一次请求 |
| `/tree [深度]` | | 显示目录结构 |
| `/map [tokens]` | | 显示代码库概览 |
| `/find <关键词>` | | 搜索相关文件 |
| `/history` | `/hist` | 显示对话历史 |
| `/plugins` | | 显示已加载插件 |
| `/plugin-new <名称>` | | 创建插件模板 |
| `/plugin-reload <名称>` | | 重新加载插件 |
| `/clear` | `/c` | 清屏 |

### 代码调用

```python
import asyncio
from xiaotie import Agent
from xiaotie.llm import LLMClient
from xiaotie.tools import ReadTool, WriteTool, BashTool, GitTool

async def main():
    # 创建 LLM 客户端
    llm = LLMClient(
        api_key="your-api-key",
        api_base="https://api.anthropic.com",
        model="claude-sonnet-4-20250514",
        provider="anthropic",
    )

    # 创建工具
    tools = [
        ReadTool(workspace_dir="."),
        WriteTool(workspace_dir="."),
        BashTool(),
        GitTool(workspace_dir="."),
    ]

    # 创建 Agent
    agent = Agent(
        llm_client=llm,
        system_prompt="你是小铁，一个智能助手。",
        tools=tools,
        stream=True,
        enable_thinking=True,
        parallel_tools=True,  # 并行执行工具
    )

    # 运行
    result = await agent.run("帮我创建一个 hello.py 文件")
    print(result)

asyncio.run(main())
```

### Agent SDK v2 (v0.9.0)

```python
from xiaotie import AgentBuilder
from xiaotie.tools import ReadTool, WriteTool, BashTool

# 使用构建器模式创建 Agent
agent = (
    AgentBuilder("my-agent")
    .with_llm("claude-sonnet-4")
    .with_tools([ReadTool(), WriteTool(), BashTool()])
    .with_memory(max_tokens=4000)
    .with_hooks(
        on_start=lambda: print("Agent started"),
        on_tool_call=lambda t: print(f"Calling {t.name}"),
    )
    .build()
)

# 运行
result = await agent.run("帮我分析这段代码")
```

或使用 YAML 配置：

```yaml
# agent.yaml
name: code-reviewer
llm:
  provider: anthropic
  model: claude-sonnet-4
tools:
  - read
  - write
  - bash
memory:
  type: conversation
  max_tokens: 4000
hooks:
  on_tool_call: log_tool_call
```

```python
from xiaotie import AgentBuilder

agent = AgentBuilder.from_yaml("agent.yaml").build()
```

### 事件订阅

```python
import asyncio
from xiaotie import Agent, EventBroker, EventType, get_event_broker

async def main():
    # 获取事件代理
    broker = get_event_broker()

    # 订阅事件
    queue = await broker.subscribe([
        EventType.AGENT_START,
        EventType.TOOL_START,
        EventType.TOOL_COMPLETE,
        EventType.MESSAGE_DELTA,
    ])

    # 创建 Agent 并运行...
    agent = Agent(...)

    # 在另一个任务中处理事件
    async def handle_events():
        while True:
            event = await queue.get()
            if event.type == EventType.TOOL_START:
                print(f"工具开始: {event.data.get('tool_name')}")
            elif event.type == EventType.MESSAGE_DELTA:
                print(event.data.get('content'), end='')

    asyncio.create_task(handle_events())
    await agent.run("你好")
```

## 插件系统

小铁支持通过插件扩展功能。插件是放置在 `~/.xiaotie/plugins/` 目录下的 Python 文件。

### 创建插件

```bash
# 使用命令创建插件模板
/plugin-new my_tool
```

或手动创建 `~/.xiaotie/plugins/my_tool.py`:

```python
from xiaotie.tools import Tool, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "我的自定义工具"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入参数"}
            },
            "required": ["input"]
        }

    async def execute(self, input: str) -> ToolResult:
        return ToolResult(success=True, content=f"结果: {input}")
```

### 管理插件

| 命令 | 说明 |
|------|------|
| `/plugins` | 查看已加载的插件 |
| `/plugin-new <名称>` | 创建插件模板 |
| `/plugin-reload <名称>` | 热重载插件 |

## 自定义命令

小铁支持 OpenCode 风格的自定义命令，可以创建预定义的提示模板。

### 命令位置

- **用户命令** (前缀 `user:`):
  - `~/.config/xiaotie/commands/`
  - `~/.xiaotie/commands/`
- **项目命令** (前缀 `project:`):
  - `<项目目录>/.xiaotie/commands/`

### 创建命令

```bash
# 创建用户命令
/cmd-new review-code

# 创建项目命令
/cmd-new-project deploy
```

或手动创建 Markdown 文件，如 `~/.xiaotie/commands/review-code.md`:

```markdown
# 代码审查

请审查以下文件的代码质量：

文件: $FILE_PATH

重点关注：
1. 代码风格
2. 潜在 bug
3. 性能问题
4. 安全漏洞

RUN git diff $FILE_PATH
```

### 命名参数

使用 `$NAME` 格式定义参数（大写字母、数字、下划线，必须以字母开头）：

```markdown
# 分析 Issue

RUN gh issue view $ISSUE_NUMBER --json title,body,comments
RUN git grep "$SEARCH_PATTERN" .
```

执行命令时，系统会提示输入参数值。

### 子目录组织

可以使用子目录组织命令：

```
~/.xiaotie/commands/
├── git/
│   ├── commit.md      -> user:git:commit
│   └── review.md      -> user:git:review
└── deploy/
    └── staging.md     -> user:deploy:staging
```

### 命令管理

| 命令 | 说明 |
|------|------|
| `/commands` | 列出所有自定义命令 |
| `/run <命令ID>` | 执行自定义命令 |
| `/cmd-new <名称>` | 创建用户命令 |
| `/cmd-new-project <名称>` | 创建项目命令 |
| `/cmd-reload` | 重新加载命令 |
| `/cmd-show <命令ID>` | 显示命令内容 |

## 项目结构

```
xiaotie/
├── xiaotie/
│   ├── __init__.py       # 包入口
│   ├── agent.py          # Agent 核心循环
│   ├── cli.py            # CLI 入口
│   ├── config.py         # 配置管理
│   ├── schema.py         # 数据模型
│   ├── retry.py          # 重试机制
│   ├── banner.py         # 启动动画
│   ├── session.py        # 会话管理
│   ├── commands.py       # 命令系统
│   ├── custom_commands.py # 自定义命令
│   ├── display.py        # 显示增强
│   ├── repomap.py        # 代码库映射
│   ├── plugins.py        # 插件系统
│   ├── mcp/              # MCP 协议支持
│   │   ├── __init__.py
│   │   ├── protocol.py   # 协议类型定义
│   │   ├── transport.py  # Stdio 传输
│   │   ├── client.py     # MCP 客户端
│   │   └── tools.py      # 工具包装器
│   ├── lsp/              # LSP 协议支持
│   │   ├── __init__.py
│   │   ├── protocol.py   # LSP 协议类型
│   │   ├── client.py     # LSP 客户端
│   │   ├── manager.py    # 服务器管理
│   │   └── diagnostics.py # 诊断工具
│   ├── storage/          # SQLite 存储
│   │   ├── __init__.py
│   │   ├── database.py   # 数据库连接
│   │   ├── models.py     # 数据模型
│   │   ├── session_store.py # 会话存储
│   │   └── message_store.py # 消息存储
│   ├── search/           # 语义搜索
│   │   ├── __init__.py
│   │   ├── embeddings.py # 嵌入生成
│   │   ├── vector_store.py # 向量存储
│   │   └── semantic_search.py # 语义搜索
│   ├── multi_agent/      # 多 Agent 协作
│   │   ├── __init__.py
│   │   ├── roles.py      # 角色定义
│   │   ├── task_agent.py # 任务 Agent
│   │   ├── coordinator.py # 协调器
│   │   └── agent_tool.py # Agent 工具
│   ├── tui/              # TUI 模块
│   │   ├── __init__.py
│   │   ├── app.py        # TUI 主应用
│   │   ├── widgets.py    # 自定义组件
│   │   ├── themes.py     # 主题系统
│   │   ├── command_palette.py # 命令面板 (v0.9.0)
│   │   ├── onboarding.py # 首次启动向导 (v0.9.0)
│   │   ├── streaming.py  # 流式渲染 (v0.9.0)
│   │   └── main.py       # TUI 入口
│   ├── testing/          # 测试模块 (v0.9.0)
│   │   └── __init__.py   # Cassette/MockLLMClient
│   ├── llm/
│   │   ├── base.py       # LLM 客户端基类
│   │   ├── wrapper.py    # 统一包装器
│   │   ├── providers.py  # Provider 适配层 (v0.9.0)
│   │   ├── anthropic_client.py
│   │   └── openai_client.py
│   ├── builder.py        # AgentBuilder (v0.9.0)
│   └── tools/
│       ├── base.py       # 工具基类
│       ├── file_tools.py # 文件工具
│       ├── bash_tool.py  # Bash 工具
│       ├── python_tool.py # Python/计算器
│       ├── git_tool.py   # Git 工具
│       ├── web_tool.py   # Web 工具
│       └── semantic_search_tool.py # 语义搜索工具
├── tests/                # 测试目录
│   ├── conftest.py       # 测试配置
│   ├── unit/             # 单元测试
│   └── integration/      # 集成测试
├── config/
│   ├── config.yaml.example
│   └── system_prompt.md
├── docs/
│   ├── v0.3.0-plan.md    # 迭代计划
│   └── v0.9.0-plan.md    # v0.9.0 计划
├── pyproject.toml
└── README.md
```

## 支持的 LLM Provider

| Provider | API Base | 说明 |
|----------|----------|------|
| Anthropic | https://api.anthropic.com | Claude 官方 API |
| OpenAI | https://api.openai.com/v1 | GPT 系列 |
| 智谱 GLM | https://open.bigmodel.cn/api/coding/paas/v4 | GLM-4.7 深度思考 |
| MiniMax | https://api.minimax.io | 自动处理 URL 后缀 |
| Gemini | https://generativelanguage.googleapis.com | Google AI (v0.9.0) |
| DeepSeek | https://api.deepseek.com | DeepSeek (v0.9.0) |
| Qwen | https://dashscope.aliyuncs.com | 通义千问 (v0.9.0) |
| 其他 | 自定义 | OpenAI 兼容 API |

## 版本历史

### v0.9.0
- 🏗️ **Agent SDK v2** - 声明式 Agent 构建
  - `AgentBuilder` 构建器模式，链式 API
  - `AgentSpec` YAML/JSON 配置支持
  - 生命周期 hooks (on_start, on_step, on_tool_call, on_complete)
  - 策略/记忆/工具解耦设计
- 🔌 **Provider 适配层** - 统一 LLM 接口
  - 新增 Gemini、DeepSeek、Qwen 支持
  - 能力矩阵 (流式、工具调用、并行工具、视觉)
  - 自动路由/降级策略
- 🎯 **命令面板增强** - 模糊搜索算法
  - 精确匹配、前缀匹配、包含匹配、子序列匹配
  - 快速模型切换器
  - 命令分类与图标
- 🚀 **首次启动向导** - 零配置体验
  - 5 步引导流程
  - API Key 配置
  - 连接测试
- 🌊 **流式渲染优化** - 实时响应显示
  - 50ms 防抖动更新
  - Token/秒速度统计
  - 平滑光标动画
- 🧪 **测试模块** - LLM 响应录制
  - Cassette 录制/回放系统
  - MockLLMClient 测试客户端
  - Textual Pilot TUI 测试

### v0.8.2
- 🎨 **主题管理器** - 全局主题状态管理
  - `ThemeManager` 单例模式管理主题状态
  - 主题变更事件订阅/发布机制
  - 实时 CSS 变量更新
- 🔧 **TUI 组件增强**
  - `ThemeSelectorItem` - 带颜色预览的主题选择项
  - 主题选择器显示配色方案预览
  - 改进的主题切换响应

### v0.8.1
- 🎨 **TUI 优化** - 参考 OpenCode 像素级复刻
  - 10 个主题配色 (Nord, Dracula, Catppuccin, Tokyo Night 等)
  - 模型选择器 (Ctrl+M)
  - 主题选择器 (Ctrl+T)
  - Toast 通知系统
  - Nerd Font 图标支持
  - 改进的状态行显示
  - 思考指示器动画
- 🔧 **TUI 组件增强**
  - `Toast` - 通知提示 (success/error/warning/info)
  - `ModelSelector` - 模型选择器
  - `ThemeSelector` - 主题选择器
  - `SelectorItem` - 通用选择项
- 📦 **主题系统** - `xiaotie/tui/themes.py`
  - 完整的颜色变量定义
  - Diff 颜色、Markdown 颜色、语法高亮颜色
  - CSS 变量导出支持

### v0.8.0
- 🔍 **语义搜索** - 基于向量的代码语义搜索
  - 使用 ChromaDB 向量数据库
  - 支持 OpenAI Embeddings
  - 自动代码分块 (按函数/类)
  - 余弦相似度搜索
  - 支持 20+ 代码文件扩展名
- 🔧 **SemanticSearchTool** - 语义搜索工具
  - 集成到 Agent 工具系统
  - 支持查询、结果数量、文件过滤
  - 自动索引工作区代码
- 📦 **新模块** - `xiaotie/search/`
  - `embeddings.py` - 嵌入生成器
  - `vector_store.py` - 向量存储
  - `semantic_search.py` - 语义搜索引擎

### v0.7.0
- 💾 **SQLite 持久化** - 高性能存储系统
  - 使用 aiosqlite 异步操作
  - 会话、消息、文件三表设计
  - 自动数据库迁移
  - WAL 模式提高并发性能
  - 级联删除保证数据一致性
- 📦 **新模块** - `xiaotie/storage/`
  - `database.py` - 数据库连接管理
  - `models.py` - 数据模型定义
  - `session_store.py` - 会话存储
  - `message_store.py` - 消息存储

### v0.6.1
- 🤖 **多 Agent 协作** - 实现 Agent 间协作
  - Agent 角色系统 (MAIN, TASK, ANALYZER, TESTER, DOCUMENTER)
  - 轻量级 TaskAgent 用于探索任务
  - AgentCoordinator 协调器管理多 Agent
  - AgentTool 工具用于生成子 Agent
- 📦 **新模块** - `xiaotie/multi_agent/`
  - `roles.py` - 角色定义与配置
  - `task_agent.py` - 任务 Agent 实现
  - `coordinator.py` - Agent 协调器
  - `agent_tool.py` - Agent 工具

### v0.6.0
- 🧪 **测试基础设施** - 完整的测试体系
  - pytest 配置与 fixtures
  - 单元测试覆盖核心模块
  - 集成测试验证端到端流程
  - GitHub Actions CI 自动化测试
- 📦 **新目录** - `tests/`
  - `tests/unit/` - 单元测试
  - `tests/integration/` - 集成测试
  - `tests/conftest.py` - 测试配置

### v0.5.2
- 🔬 **LSP 集成** - 语言服务器协议支持
  - LSP 客户端实现 (stdio 通信)
  - 实时诊断信息获取
  - 多语言服务器管理
  - diagnostics 工具集成
- 📦 **新模块** - `xiaotie/lsp/`
  - `protocol.py` - LSP 协议类型
  - `client.py` - LSP 客户端
  - `manager.py` - 服务器管理
  - `diagnostics.py` - 诊断工具

### v0.5.1
- 📜 **自定义命令系统** - 参考 OpenCode 设计
  - 用户命令: `~/.xiaotie/commands/`
  - 项目命令: `.xiaotie/commands/`
  - 支持 Markdown 文件定义命令
  - 支持命名参数 `$ARG_NAME`
  - 支持子目录组织命令
- 🔧 **新命令** - /commands, /run, /cmd-new, /cmd-new-project, /cmd-reload, /cmd-show

### v0.5.0
- 🔌 **MCP 协议支持** - 实现 Model Context Protocol 客户端
  - Stdio 传输协议支持
  - 自动工具发现与调用
  - 多 MCP 服务器管理
  - 配置文件集成
- 📦 **新模块** - `xiaotie/mcp/` 模块
  - `protocol.py` - MCP 协议类型定义
  - `transport.py` - Stdio 传输实现
  - `client.py` - MCP 客户端
  - `tools.py` - MCP 工具包装器

### v0.4.3
- 🔒 **权限系统** - Human-in-the-Loop 安全机制，命令风险分类
- 🔄 **Lint/Test 反馈循环** - 自动错误检测，参考 Aider 设计
- 📋 **Profile 配置系统** - 多配置文件支持，参考 Open Interpreter
- 🖥️ **增强 Bash 工具** - 持久化 Shell 会话，命令注入检测
- 🔧 **新命令** - /lint, /test, /profiles, /profile
- 🐛 **Bug 修复** - 修复 asyncio 事件循环冲突问题

### v0.4.2
- 🎨 **TUI 重构** - 完全参考 OpenCode 设计重构 TUI
- 📐 **分割布局** - 消息区 + 会话侧边栏分割布局
- ⌨️ **Ctrl+K 命令面板** - 支持搜索过滤的命令面板
- 📱 **侧边栏切换** - Ctrl+B 切换会话侧边栏显示
- 🎯 **状态行优化** - 显示模型、Token、会话、状态、模式
- 💭 **思考指示器** - 动画显示 AI 思考状态
- 📡 **事件驱动架构** - Pub/Sub 事件系统，实时 UI 更新
- 🔒 **会话状态管理** - 防止并发请求冲突
- 📊 **智能摘要优化** - 阈值触发、保留关键消息
- ⚡ **工具执行优化** - 支持顺序/并行模式切换

### v0.4.1
- ⌨️ **增强输入** - 命令自动补全、历史记录、Ctrl+R 搜索
- 🎯 **新命令** - /config, /status, /compact, /copy, /undo, /retry
- 📊 **优化显示** - 工具执行结果预览、耗时统计
- 🔧 **更多别名** - /c, /r, /s, /l, /t, /tok, /hist, /cfg
- 🐛 **Bug 修复** - GLM-4.7 参数传递、重复输出问题

### v0.4.0
- 🖥️ **TUI 模式** - 基于 Textual 的现代化终端界面
- 📤 **非交互模式** - 支持 `-p` 参数直接执行查询
- 🎨 **JSON 输出** - 支持 `-f json` 格式化输出
- ⌨️ **命令面板** - Ctrl+P 快速访问命令
- 🎯 **命令行参数** - 支持 --tui, --no-stream, --no-thinking 等
- 参考 [OpenCode](https://github.com/opencode-ai/opencode) 设计

### v0.3.1
- 🚀 **工具并行执行** - 多工具调用使用 asyncio.gather 并行执行
- 🔌 **插件系统** - 支持自定义工具热加载
- 新命令：/parallel, /plugins, /plugin-new, /plugin-reload
- 执行时间统计

### v0.3.0
- 命令系统重构（约定优于配置）
- 显示增强（rich 库支持）
- 代码库感知（RepoMap）
- Git 工具
- Web 搜索/获取工具
- 新命令：/tree, /map, /find, /tokens, /history

### v0.2.0
- 流式输出 + 深度思考
- 会话管理
- Python/计算器工具
- GLM-4.7/MiniMax 适配

### v0.1.0
- 初始版本
- Agent 执行循环
- 文件/Bash 工具
- 多 LLM Provider 支持

## 致谢

本项目基于 [MiniMax-AI/Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，感谢原作者的开源贡献！

同时学习借鉴了以下优秀项目的设计模式：
- [Aider](https://github.com/Aider-AI/aider) - 命令系统、RepoMap
- [Open Interpreter](https://github.com/openinterpreter/open-interpreter) - 流式处理、显示
- [Devika](https://github.com/stitionai/devika) - 多 Agent 架构
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - MCP 协议实现参考

## License

MIT
