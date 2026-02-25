# 工具系统文档

小铁（xiaotie）提供丰富的内置工具，所有工具继承自 `Tool` 基类，可注册到 Agent 中通过自然语言或 API 调用。

## 工具列表

| 工具 | 类名 | 说明 |
|------|------|------|
| 文件读取 | `ReadTool` | 读取文件内容 |
| 文件写入 | `WriteTool` | 写入文件内容 |
| 文件编辑 | `EditTool` | 编辑文件（查找替换） |
| Bash 命令 | `BashTool` | 执行 shell 命令 |
| 增强 Bash | `EnhancedBashTool` | 持久化 shell 会话 |
| Python 执行 | `PythonTool` | 运行 Python 代码 |
| 计算器 | `CalculatorTool` | 数学计算 |
| Git 操作 | `GitTool` | 版本控制操作 |
| Web 搜索 | `WebSearchTool` | DuckDuckGo 搜索 |
| 网页获取 | `WebFetchTool` | 获取网页内容 |
| 代码分析 | `CodeAnalysisTool` | 提取类、函数、依赖 |
| 语义搜索 | `SemanticSearchTool` | 基于向量的代码搜索 |
| 系统信息 | `SystemInfoTool` | 获取系统硬件软件信息 |
| 进程管理 | `ProcessManagerTool` | 管理和监控进程 |
| 网络工具 | `NetworkTool` | 网络诊断和扫描 |
| Charles 代理 | `CharlesProxyTool` | 封装 Charles Proxy 抓包 |
| **内置代理** | **`ProxyServerTool`** | **内置 HTTP/HTTPS 代理抓包** |
| **爬虫工具** | **`ScraperTool`** | **结构化 Web 数据抓取，支持多线程和认证** |

## ProxyServerTool

内置 HTTP/HTTPS 代理服务器工具，无需外部依赖即可完成网络请求抓包。

### 基本信息

- **工具名称**: `proxy_server`
- **模块路径**: `xiaotie.tools.proxy_tool`
- **依赖**: 无外部依赖

### 参数定义

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["start", "stop", "status", "export", "export_cert",
               "analyze", "filter_miniapp", "list_requests", "clear"],
      "description": "操作类型"
    },
    "port": {
      "type": "integer",
      "description": "代理端口（默认 8080）",
      "default": 8080
    },
    "host": {
      "type": "string",
      "description": "监听地址（默认 127.0.0.1）",
      "default": "127.0.0.1"
    },
    "ssl_decrypt": {
      "type": "boolean",
      "description": "是否启用 HTTPS 解密",
      "default": false
    },
    "filter_domain": {
      "type": "string",
      "description": "过滤域名"
    },
    "filter_path": {
      "type": "string",
      "description": "过滤路径前缀"
    },
    "output_file": {
      "type": "string",
      "description": "导出文件路径"
    },
    "format": {
      "type": "string",
      "enum": ["json", "har"],
      "description": "导出格式（默认 json）",
      "default": "json"
    }
  },
  "required": ["action"]
}
```

### 操作说明

| action | 说明 | 关键参数 |
|--------|------|----------|
| `start` | 启动代理服务器 | `port`, `host`, `ssl_decrypt`, `filter_domain` |
| `stop` | 停止代理服务器并恢复系统代理 | - |
| `status` | 查看运行状态、端口、已捕获请求数 | - |
| `export` | 导出捕获的请求数据 | `output_file`, `format`, `filter_domain` |
| `export_cert` | 导出 CA 证书（HTTPS 解密用） | `output_file` |
| `analyze` | 分析捕获的请求，生成统计报告 | - |
| `filter_miniapp` | 过滤微信小程序相关请求 | `output_file` |
| `list_requests` | 列出已捕获的请求摘要 | `filter_domain` |
| `clear` | 清空已捕获的请求数据 | - |

### 使用示例

```python
from xiaotie.tools import ProxyServerTool

proxy = ProxyServerTool()

# 启动代理
await proxy.execute(action="start", port=8080, ssl_decrypt=True)

# 查看状态
result = await proxy.execute(action="status")
print(result.content)

# 导出数据
await proxy.execute(action="export", output_file="capture.json")

# 分析
result = await proxy.execute(action="analyze")
print(result.content)

# 停止
await proxy.execute(action="stop")
```

详细文档参见 [内置代理使用指南](./builtin-proxy-guide.md)。

## ScraperTool

结构化 Web 数据抓取工具，基于 `BaseScraper` 框架，支持多线程并发、6 种认证方式和数据稳定性验证。

### 基本信息

- **工具名称**: `scraper`
- **模块路径**: `xiaotie.tools.scraper_tool`
- **依赖**: `requests`, `pandas`, `tqdm`

### 参数定义

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["run", "status", "list_brands", "configure"],
      "description": "操作类型"
    },
    "brand": {
      "type": "string",
      "description": "品牌名称或 ID"
    },
    "mode": {
      "type": "string",
      "enum": ["test", "full"],
      "description": "运行模式（默认 test）",
      "default": "test"
    },
    "output_dir": {
      "type": "string",
      "description": "输出目录"
    },
    "auth_token": {
      "type": "string",
      "description": "认证 Token（可选）"
    }
  },
  "required": ["action"]
}
```

### 操作说明

| action | 说明 | 关键参数 |
|--------|------|----------|
| `run` | 执行爬虫抓取（3 次运行验证） | `brand`, `mode`, `output_dir` |
| `status` | 查看当前爬虫运行状态 | - |
| `list_brands` | 列出所有已注册的品牌爬虫 | - |
| `configure` | 配置品牌认证信息 | `brand`, `auth_token` |

### 使用示例

```python
from xiaotie.tools import ScraperTool

scraper = ScraperTool()

# 列出可用品牌
result = await scraper.execute(action="list_brands")
print(result.content)

# 测试模式运行
result = await scraper.execute(action="run", brand="熊猫球社", mode="test")
print(result.content)

# 完整模式运行
result = await scraper.execute(action="run", brand="熊猫球社", mode="full")
print(result.content)

# 配置认证
await scraper.execute(action="configure", brand="碰碰捌", auth_token="xxx")
```

详细文档参见 [爬虫模块使用指南](./scraper-guide.md) 和 [竞品对比](./scraper-vs-competitors.md)。

## CharlesProxyTool

封装外部 Charles Proxy 应用的抓包工具。

### 基本信息

- **工具名称**: `charles_proxy`
- **模块路径**: `xiaotie.tools.charles_tool`
- **依赖**: 需安装 [Charles Proxy](https://www.charlesproxy.com/)

### 操作说明

| action | 说明 |
|--------|------|
| `start` | 启动 Charles 代理 |
| `stop` | 停止 Charles 代理 |
| `status` | 查看运行状态 |
| `export` | 导出抓包数据（AppleScript 自动导出） |
| `analyze` | 分析会话数据 |
| `filter_miniapp` | 过滤小程序请求 |

详细文档参见 [Charles 代理工具指南](./charles-proxy-guide.md)。

## 工具基类

所有工具继承自 `xiaotie.tools.base.Tool`：

```python
from xiaotie.tools import Tool, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "工具描述"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入参数"}
            },
            "required": ["input"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="结果")
```

### ToolResult

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 操作是否成功 |
| `content` | `str` | 操作结果描述 |
| `error` | `str \| None` | 错误信息（失败时） |
