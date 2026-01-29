# ⚙️ 小铁 (XiaoTie)

轻量级 AI Agent 框架，基于 [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现。

```
 ▄███▄     小铁 XiaoTie v0.1.0
 █ ⚙ █    GLM-4.7 · OpenAI
 ▀███▀     ~/workspace
```

## 特性

- 🔄 **Agent 执行循环** - 自动工具调用与任务完成
- 🔧 **多工具支持** - 文件操作、Bash 命令执行
- 🤖 **多 LLM Provider** - 支持 Anthropic Claude 和 OpenAI 兼容 API
- 🔁 **自动重试** - 指数退避重试机制
- 📝 **Token 管理** - 自动摘要历史消息
- ⚡ **优雅取消** - 支持 Ctrl+C 中断

## 安装

```bash
# 克隆项目
git clone https://github.com/leo/xiaotie.git
cd xiaotie

# 安装依赖
pip install -e .
```

## 配置

1. 复制配置文件模板：

```bash
cp config/config.yaml.example config/config.yaml
```

2. 编辑 `config/config.yaml`，填入你的 API Key：

```yaml
api_key: YOUR_API_KEY_HERE
api_base: https://api.anthropic.com
model: claude-sonnet-4-20250514
provider: anthropic
```

## 使用

### 命令行

```bash
# 启动交互式 CLI
xiaotie

# 或者
python -m xiaotie.cli
```

### 代码调用

```python
import asyncio
from xiaotie import Agent
from xiaotie.llm import LLMClient
from xiaotie.tools import ReadTool, WriteTool, BashTool

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
    ]

    # 创建 Agent
    agent = Agent(
        llm_client=llm,
        system_prompt="你是小铁，一个智能助手。",
        tools=tools,
    )

    # 运行
    result = await agent.run("帮我创建一个 hello.py 文件")
    print(result)

asyncio.run(main())
```

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
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py       # LLM 客户端基类
│   │   ├── wrapper.py    # 统一包装器
│   │   ├── anthropic_client.py
│   │   └── openai_client.py
│   └── tools/
│       ├── __init__.py
│       ├── base.py       # 工具基类
│       ├── file_tools.py # 文件工具
│       └── bash_tool.py  # Bash 工具
├── config/
│   ├── config.yaml.example
│   └── system_prompt.md
├── pyproject.toml
└── README.md
```

## 支持的 LLM Provider

| Provider | API Base | 说明 |
|----------|----------|------|
| Anthropic | https://api.anthropic.com | Claude 官方 API |
| OpenAI | https://api.openai.com/v1 | GPT 系列 |
| MiniMax | https://api.minimax.io | 自动处理 URL 后缀 |
| 其他 | 自定义 | OpenAI 兼容 API |

## CLI 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/quit` | 退出程序 |
| `/reset` | 重置对话 |
| `/tools` | 显示可用工具 |

## 致谢

本项目基于 [MiniMax-AI/Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，感谢原作者的开源贡献！

Mini-Agent 是一个优秀的轻量级 AI Agent 框架，提供了清晰的架构设计和完整的功能实现。小铁在其基础上进行了学习和复现，并添加了一些个性化功能。

## License

MIT
