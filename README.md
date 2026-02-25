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
- 💻 **系统信息** - 获取系统硬件和软件信息
- 🔧 **进程管理** - 管理和监控系统进程
- 🌐 **网络工具** - 执行网络诊断和扫描操作
- 🔌 **内置代理** - HTTP/HTTPS 代理抓包，无需外部工具，支持小程序请求分析
- 📡 **Charles 集成** - 封装 Charles Proxy 自动化抓包
- 🕷️ **爬虫工具** - 结构化 Web 数据抓取，多线程并发、6 种认证、稳定性验证
- 🤖 **macOS 自动化** - 微信/小程序自动化，AppleScript + Accessibility API，支持截图、消息发送、代理抓包集成

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
│   ├── builder.py        # AgentBuilder (v0.9.0)
│   ├── cache.py          # 异步 LRU 缓存系统
│   ├── events.py         # 事件系统 (Pub/Sub)
│   ├── logging.py        # 统一日志管理
│   ├── enhancements.py   # 性能增强与优化
│   ├── database.py       # 数据库连接
│   ├── feedback.py       # 反馈循环
│   ├── input.py          # 增强输入
│   ├── permissions.py    # 权限系统
│   ├── profiles.py       # Profile 配置
│   ├── orchestrator.py   # 编排器
│   ├── sandbox.py        # 沙箱执行
│   ├── api_tool.py       # API 工具
│   ├── i18n.py           # 国际化
│   ├── keybindings.py    # 快捷键绑定
│   ├── config_watcher.py # 配置热更新
│   ├── knowledge_base.py # 知识库
│   ├── retry_v2.py       # 重试机制 v2
│   ├── context/          # 上下文感知
│   │   ├── core.py       # 上下文管理器
│   │   └── window.py     # 上下文窗口管理
│   ├── decision/         # 智能决策
│   │   └── core.py       # 决策引擎
│   ├── learning/         # 自适应学习
│   │   └── core.py       # 自适应学习器
│   ├── memory/           # 记忆系统
│   │   └── core.py       # 记忆管理器
│   ├── planning/         # 规划系统
│   │   └── core.py       # 规划管理器
│   ├── reflection/       # 反思机制
│   │   └── core.py       # 反思管理器
│   ├── skills/           # 技能学习
│   │   └── core.py       # 技能学习器
│   ├── multimodal/       # 多模态支持
│   │   └── core.py       # 多模态内容管理
│   ├── rl/               # 强化学习
│   │   └── core.py       # 强化学习引擎
│   ├── kg/               # 知识图谱
│   │   └── core.py       # 知识图谱管理器
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
│   ├── automation/       # 自动化模块
│   │   ├── __init__.py
│   │   ├── appium_driver.py  # Appium 驱动封装
│   │   ├── miniapp_automation.py # 小程序自动化
│   │   └── macos/        # macOS 原生自动化
│   │       ├── wechat_controller.py  # 微信控制器
│   │       ├── miniapp_controller.py # 小程序控制
│   │       └── proxy_integration.py  # 代理集成
│   ├── tui/              # TUI 模块
│   │   ├── __init__.py
│   │   ├── app.py        # TUI 主应用
│   │   ├── widgets.py    # 自定义组件
│   │   ├── themes.py     # 主题系统
│   │   ├── command_palette.py # 命令面板
│   │   ├── onboarding.py # 首次启动向导
│   │   ├── streaming.py  # 流式渲染
│   │   └── main.py       # TUI 入口
│   ├── testing/          # 测试模块
│   │   └── __init__.py   # Cassette/MockLLMClient
│   ├── llm/              # LLM 客户端
│   │   ├── __init__.py
│   │   ├── base.py       # LLM 客户端基类
│   │   ├── wrapper.py    # 统一包装器
│   │   ├── providers.py  # Provider 适配层
│   │   ├── anthropic_client.py
│   │   └── openai_client.py
│   └── tools/            # 工具系统
│       ├── __init__.py
│       ├── base.py       # 工具基类
│       ├── file_tools.py # 文件工具
│       ├── bash_tool.py  # Bash 工具
│       ├── enhanced_bash.py # 增强 Bash
│       ├── python_tool.py # Python/计算器
│       ├── git_tool.py   # Git 工具
│       ├── web_tool.py   # Web 工具
│       ├── code_analysis.py # 代码分析
│       ├── extended.py   # 扩展工具 (系统信息/进程/网络)
│       ├── semantic_search_tool.py # 语义搜索工具
│       ├── charles_tool.py # Charles 代理封装
│       ├── proxy_tool.py  # 内置代理服务器
│       ├── scraper_tool.py # 爬虫工具
│       └── automation_tool.py # macOS 自动化工具
├── tests/                # 测试目录
│   ├── conftest.py       # 测试配置
│   ├── fixtures/         # 测试数据
│   ├── unit/             # 单元测试
│   └── integration/      # 集成测试
├── config/
│   ├── config.yaml.example
│   └── system_prompt.md
├── docs/
│   ├── v0.3.0-plan.md
│   ├── v0.9.0-plan.md
│   ├── v0.10.0-plan.md
│   ├── v0.11.0-plan.md
│   ├── tools.md
│   └── macos-miniapp-automation-guide.md
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

### v1.1.0 (当前版本)
- 🧠 **认知架构增强** - 全面的认知能力提升
  - 自适应学习、上下文感知、智能决策、技能学习
  - 知识图谱、强化学习、规划系统、反思机制

完整版本历史请参阅 [CHANGELOG.md](CHANGELOG.md)。

## 致谢

本项目基于 [MiniMax-AI/Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，感谢原作者的开源贡献！

同时学习借鉴了以下优秀项目的设计模式：
- [Aider](https://github.com/Aider-AI/aider) - 命令系统、RepoMap
- [Open Interpreter](https://github.com/openinterpreter/open-interpreter) - 流式处理、显示
- [Devika](https://github.com/stitionai/devika) - 多 Agent 架构
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - MCP 协议实现参考

## License

MIT
