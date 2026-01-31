<p align="center">
  <img src="https://img.shields.io/badge/AI%20Agent-Framework-blue?style=for-the-badge" alt="AI Agent Framework">
  <img src="https://img.shields.io/badge/Version-0.8.1-green?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/LLM-Multi--Provider-orange?style=for-the-badge" alt="Multi-Provider">
</p>

<h1 align="center">⚙️ 小铁 (XiaoTie)</h1>

<p align="center">
  <strong>Lightweight AI Agent Framework</strong>
  <br>
  <em>Based on Mini-Agent architecture, inspired by OpenCode design</em>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-providers">Providers</a> •
  <a href="#-installation">Installation</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Anthropic-Claude-8A2BE2?logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/OpenAI-GPT-412991?logo=openai&logoColor=white" alt="OpenAI">
  <img src="https://img.shields.io/badge/Textual-TUI-4EAA25?logo=textual&logoColor=white" alt="Textual">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

**English** | [中文](#中文)

---

## Overview

**XiaoTie (小铁)** is a lightweight AI Agent framework based on [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) architecture, inspired by [OpenCode](https://github.com/opencode-ai/opencode) design.

### Why XiaoTie?

| Challenge | Solution |
|-----------|----------|
| Complex agent setup | **Lightweight framework** - easy to start |
| Single LLM limitation | **Multi-provider** - Claude, GPT, GLM, MiniMax |
| No visual interface | **TUI mode** - modern terminal UI |
| Limited extensibility | **Plugin system** - custom tools |

---

## Features

### Core

| Feature | Description |
|---------|-------------|
| **Agent Loop** | Automatic tool calling and task completion |
| **Streaming** | Real-time thinking process display |
| **Deep Thinking** | GLM-4.7 thinking mode support |
| **Session Management** | Save/load conversation history |
| **Token Management** | Auto-summarize history messages |
| **Parallel Tools** | Multi-tool parallel execution |

### Interface

| Feature | Description |
|---------|-------------|
| **TUI Mode** | Modern terminal UI based on Textual |
| **CLI Mode** | Traditional command-line interface |
| **Non-Interactive** | Single query and JSON output |

### Extensibility

| Feature | Description |
|---------|-------------|
| **MCP Support** | Model Context Protocol integration |
| **LSP Integration** | Language Server Protocol diagnostics |
| **Plugin System** | Custom tool hot-loading |
| **Multi-Agent** | Sub-task decomposition |

---

## Quick Start

### Installation

```bash
# Clone
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie

# Install all features
pip install -e ".[all]"

# Run
xiaotie
```

### Basic Usage

```bash
# Interactive CLI
xiaotie

# TUI mode
xiaotie --tui

# Non-interactive
xiaotie -p "Hello, what can you do?"

# JSON output
xiaotie -p "Hello" -f json
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      XiaoTie Architecture                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │   CLI/TUI   │ │   Agent     │ │   Session   │               │
│  │  Interface  │ │    Loop     │ │  Management │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│         │               │               │                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Tool System                           │   │
│  │  File │ Bash │ Python │ Git │ Web │ Semantic Search     │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │               │               │                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   LLM Providers                          │   │
│  │  Claude │ OpenAI │ GLM-4.7 │ MiniMax                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Providers

| Provider | API Base | Description |
|----------|----------|-------------|
| Anthropic | api.anthropic.com | Claude 3.5/4 series |
| OpenAI | api.openai.com | GPT-4o etc. |
| 智谱 GLM | open.bigmodel.cn | GLM-4.7 deep thinking |
| MiniMax | api.minimax.io | abab series |

---

## Tools

| Tool | Description |
|------|-------------|
| **File** | Read, write, edit files |
| **Bash** | Execute shell commands |
| **Python** | Run Python code |
| **Calculator** | Math calculations |
| **Git** | Version control (status/diff/log/commit) |
| **Web Search** | DuckDuckGo search |
| **Web Fetch** | Fetch web content |
| **Code Analysis** | Extract classes, functions, dependencies |
| **Semantic Search** | Vector-based code search |

---

## Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/help` | `/h` | Show help |
| `/quit` | `/q` | Exit program |
| `/reset` | `/r` | Reset conversation |
| `/tools` | `/t` | Show available tools |
| `/save` | `/s` | Save session |
| `/load <id>` | `/l` | Load session |
| `/tree [depth]` | | Show directory structure |
| `/map [tokens]` | | Show codebase overview |
| `/plugins` | | Show loaded plugins |

---

## 中文

### 概述

**小铁 (XiaoTie)** 是一个轻量级 AI Agent 框架，基于 [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) 架构复现，参考 [OpenCode](https://github.com/opencode-ai/opencode) 设计。

### 核心功能

| 功能 | 描述 |
|------|------|
| **Agent 执行循环** | 自动工具调用与任务完成 |
| **流式输出** | 实时显示思考过程和回复 |
| **深度思考** | 支持 GLM-4.7 thinking 模式 |
| **会话管理** | 保存/加载对话历史 |
| **并行工具执行** | 多工具调用并行执行 |
| **TUI 模式** | 基于 Textual 的现代化终端界面 |
| **MCP 协议支持** | 连接 MCP 服务器，扩展工具能力 |
| **多 Agent 协作** | 子任务分解与并行执行 |

### 安装

```bash
# 克隆项目
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie

# 安装所有功能
pip install -e ".[all]"

# 运行
xiaotie
```

### 使用方法

```bash
# 启动交互式 CLI
xiaotie

# 启动 TUI 模式
xiaotie --tui

# 非交互模式
xiaotie -p "帮我分析这段代码"
```

### 支持的 LLM

| Provider | 描述 |
|----------|------|
| Anthropic Claude | Claude 3.5/4 系列 |
| OpenAI GPT | GPT-4o 等 |
| 智谱 GLM-4.7 | 深度思考 + 工具流式 |
| MiniMax | abab 系列 |

### 工具系统

| 工具 | 描述 |
|------|------|
| **文件操作** | 读取、写入、编辑文件 |
| **Bash 命令** | 执行 shell 命令 |
| **Python 执行** | 运行 Python 代码 |
| **Git 操作** | 版本控制 |
| **Web 搜索** | DuckDuckGo 搜索 |
| **语义搜索** | 基于向量的代码语义搜索 |

---

## Version History

| Version | Highlights |
|---------|------------|
| v0.8.1 | TUI optimization, 10 themes, Toast notifications |
| v0.8.0 | Semantic search with ChromaDB |
| v0.7.0 | SQLite persistence |
| v0.6.0 | Multi-Agent collaboration |
| v0.5.0 | MCP protocol support |
| v0.4.0 | TUI mode with Textual |

---

## Contributors

- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - Project Lead
- **Claude** (Anthropic Claude Opus 4.5) - Architecture & Implementation

## Acknowledgements

- **[MiniMax-AI/Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent)** - Original architecture
- **[Aider](https://github.com/Aider-AI/aider)** - Command system, RepoMap
- **[Open Interpreter](https://github.com/openinterpreter/open-interpreter)** - Streaming, display
- **[OpenCode](https://github.com/opencode-ai/opencode)** - TUI design inspiration

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with collaboration between human and AI</sub>
</p>
