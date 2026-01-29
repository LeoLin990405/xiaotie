# ⚙️ 小铁 (XiaoTie)

轻量级 AI Agent 框架，基于 [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，参考 [OpenCode](https://github.com/opencode-ai/opencode) 设计。

```
 ▄███▄     小铁 XiaoTie v0.4.0
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

### 工具系统
- 📁 **文件操作** - 读取、写入、编辑文件
- 🖥️ **Bash 命令** - 执行 shell 命令
- 🐍 **Python 执行** - 运行 Python 代码
- 🔢 **计算器** - 数学计算
- 🌿 **Git 操作** - 版本控制（status/diff/log/commit）
- 🔍 **Web 搜索** - DuckDuckGo 搜索
- 🌐 **网页获取** - 获取网页内容
- 📊 **代码分析** - 提取类、函数、依赖关系

### 代码库感知 (RepoMap)
- 📂 **目录树** - 可视化项目结构
- 🗺️ **代码映射** - 提取类、函数定义
- 🔎 **智能搜索** - 按关键词查找相关文件

### 多 LLM 支持
- 🤖 **Anthropic Claude** - Claude 3.5/4 系列
- 🧠 **OpenAI GPT** - GPT-4o 等
- 🔮 **智谱 GLM-4.7** - 深度思考 + 工具流式
- 🌈 **MiniMax** - abab 系列

## 安装

```bash
# 克隆项目
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie

# 基础安装
pip install -e .

# 安装 TUI 支持
pip install -e ".[tui]"

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
│   ├── display.py        # 显示增强
│   ├── repomap.py        # 代码库映射
│   ├── plugins.py        # 插件系统
│   ├── tui/              # TUI 模块
│   │   ├── __init__.py
│   │   ├── app.py        # TUI 主应用
│   │   ├── widgets.py    # 自定义组件
│   │   └── main.py       # TUI 入口
│   ├── llm/
│   │   ├── base.py       # LLM 客户端基类
│   │   ├── wrapper.py    # 统一包装器
│   │   ├── anthropic_client.py
│   │   └── openai_client.py
│   └── tools/
│       ├── base.py       # 工具基类
│       ├── file_tools.py # 文件工具
│       ├── bash_tool.py  # Bash 工具
│       ├── python_tool.py # Python/计算器
│       ├── git_tool.py   # Git 工具
│       └── web_tool.py   # Web 工具
├── config/
│   ├── config.yaml.example
│   └── system_prompt.md
├── docs/
│   └── v0.3.0-plan.md    # 迭代计划
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
| 其他 | 自定义 | OpenAI 兼容 API |

## 版本历史

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

## License

MIT
