# 内置代理 vs Charles：功能对比

## 概述

小铁提供两种网络抓包方案：
- **ProxyServerTool**（内置代理）：v1.2.0 新增，纯 Python 实现，零外部依赖
- **CharlesProxyTool**（Charles 封装）：v1.0.0 起支持，封装外部 Charles Proxy 应用

两者均可注册为 Agent 工具，通过自然语言或 API 控制。

## 功能对比

| 功能 | ProxyServerTool | CharlesProxyTool |
|------|:-:|:-:|
| **基础代理** | | |
| HTTP 请求捕获 | Y | Y |
| HTTPS 请求解密 | Y（内置 CA） | Y（Charles CA） |
| 系统代理自动配置 | Y | Y |
| 跨平台支持 | macOS / Linux / Windows | 同左 |
| **数据操作** | | |
| JSON 导出 | Y（直接内存导出） | Y（AppleScript / 手动） |
| HAR 导出 | Y | Y |
| 实时请求列表 | Y | - |
| 请求清空 | Y | - |
| 域名过滤 | Y | Y |
| 路径过滤 | Y | - |
| **分析功能** | | |
| 域名分布统计 | Y | Y |
| HTTP 方法统计 | Y | Y |
| 状态码分布 | Y | Y |
| API 端点列表 | Y | Y |
| 小程序请求过滤 | Y | Y |
| **集成** | | |
| Agent 工具注册 | Y | Y |
| 自然语言控制 | Y | Y |
| AgentBuilder 支持 | Y | Y |
| **依赖** | | |
| 外部应用 | 无 | Charles Proxy |
| 费用 | 免费 | Charles 需付费 |
| 安装复杂度 | pip install 即可 | 需单独安装 Charles |

## 选择建议

### 推荐使用内置代理 (ProxyServerTool) 的场景

- **自动化流水线**：CI/CD 中无法安装 GUI 应用，内置代理纯命令行运行
- **快速原型**：不想安装额外软件，pip install 后立即可用
- **Agent 深度集成**：需要实时获取请求列表、程序化清空数据等高级操作
- **团队协作**：无需每人购买 Charles 授权
- **轻量场景**：只需要基础抓包和分析，不需要 Charles 的高级 GUI 功能

### 推荐使用 Charles (CharlesProxyTool) 的场景

- **复杂调试**：需要 Charles 的断点、重写、限速等高级功能
- **可视化分析**：偏好 GUI 界面查看请求详情
- **已有 Charles 授权**：团队已经在使用 Charles 工作流
- **高级 SSL 配置**：需要 Charles 的精细 SSL Proxying 规则

## 代码对比

### 启动代理

```python
# 内置代理
from xiaotie.tools import ProxyServerTool
proxy = ProxyServerTool()
await proxy.execute(action="start", port=8080, ssl_decrypt=True)

# Charles
from xiaotie.tools import CharlesProxyTool
charles = CharlesProxyTool()
await charles.execute(action="start", port=8888)
```

### 导出数据

```python
# 内置代理 - 直接从内存导出，无需 GUI 操作
await proxy.execute(action="export", output_file="data.json")

# Charles - 尝试 AppleScript 自动导出，可能回退到手动说明
await charles.execute(action="export", output_file="data.json")
```

### 分析数据

```python
# 内置代理 - 直接分析内存中的请求
await proxy.execute(action="analyze")

# Charles - 需要先导出文件，再指定文件分析
await charles.execute(action="analyze", session_file="data.json")
```

### Agent 使用

```python
from xiaotie import create_agent
from xiaotie.tools import ProxyServerTool, CharlesProxyTool

# 两者都可以注册为 Agent 工具，用法一致
agent = create_agent(
    provider="anthropic",
    tools=[ProxyServerTool()]  # 或 CharlesProxyTool()
)
await agent.run("启动代理并抓取小程序请求")
```

## 迁移指南

从 CharlesProxyTool 迁移到 ProxyServerTool：

| CharlesProxyTool | ProxyServerTool | 说明 |
|-----------------|-----------------|------|
| `CharlesProxyTool()` | `ProxyServerTool()` | 替换类名 |
| `action="start", port=8888` | `action="start", port=8080` | 默认端口不同 |
| `action="export"` | `action="export"` | 接口一致 |
| `action="analyze", session_file=...` | `action="analyze"` | 内置代理无需指定文件 |
| `action="filter_miniapp", session_file=...` | `action="filter_miniapp"` | 同上 |
| - | `action="export_cert"` | 新增：导出 CA 证书 |
| - | `action="list_requests"` | 新增：实时请求列表 |
| - | `action="clear"` | 新增：清空请求 |
| - | `ssl_decrypt=True` | 新增：HTTPS 解密开关 |

核心 API（start/stop/status/export/analyze/filter_miniapp）保持兼容，迁移成本低。
