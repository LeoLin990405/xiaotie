# xiaotie 爬虫 vs 竞品代码对比

## 概述

本文对比 xiaotie 爬虫模块与现有竞品数据抓取脚本（`新竞品代码/`）的架构差异，说明 xiaotie 方案的优势和适用场景。

## 架构对比

### 竞品代码（新竞品代码 v2.0）

```
新竞品代码/
├── lib/
│   ├── base_scraper.py      # BaseScraper 抽象基类
│   ├── config.py             # ConfigManager (YAML)
│   ├── threading_utils.py    # SessionManager (线程安全)
│   ├── stability.py          # StabilityAnalyzer
│   ├── output.py             # OutputManager
│   └── auth.py               # AuthHandler (6种认证)
├── config/
│   ├── settings.yaml         # 全局配置
│   └── brands.yaml           # 19 个品牌配置
├── *.ipynb                   # Notebook 入口
└── archive/py_2026-01-20/    # 19 个品牌脚本
```

### xiaotie 爬虫模块

```
xiaotie/
├── scraper/
│   ├── base.py               # BaseScraper (异步 + 同步)
│   ├── auth.py               # AuthHandler (兼容竞品 6 种)
│   ├── session.py            # SessionManager (连接池)
│   ├── stability.py          # StabilityAnalyzer
│   └── output.py             # OutputManager
├── tools/
│   └── scraper_tool.py       # ScraperTool (Agent 集成)
└── config/
    └── config.yaml            # 统一配置
```

## 功能对比

| 功能 | 竞品代码 v2.0 | xiaotie 爬虫 |
|------|---------------|-------------|
| 基类模式 | `BaseScraper` (同步) | `BaseScraper` (同步 + 异步) |
| 子类代码量 | ~135 行 | ~100 行 |
| 认证方式 | 6 种 | 6 种（完全兼容） |
| 多线程 | `ThreadPoolExecutor` | `ThreadPoolExecutor` + `asyncio` |
| 稳定性验证 | 3 次运行取交集 | 3 次运行取交集（相同算法） |
| 配置管理 | YAML + 环境变量 | YAML + 环境变量（统一配置） |
| 输出格式 | CSV + TXT 报告 | CSV + JSON + HAR |
| Agent 集成 | 无 | ScraperTool 原生集成 |
| 自然语言调用 | 不支持 | Agent 可通过对话触发 |
| 进度显示 | tqdm | tqdm + Agent 事件流 |
| 错误重试 | 基础重试 | 指数退避 + 智能重试 |
| 数据后处理 | 手动 | `process_data()` 钩子 |
| 品牌管理 | 独立脚本 | 统一注册 + 动态发现 |
| 定时任务 | launchd / cron | Agent 调度 + cron |
| 测试支持 | 手动测试模式 | pytest 集成 |

## 关键差异分析

### 1. Agent 集成（xiaotie 独有）

竞品代码是独立的 Python 脚本，需要手动运行。xiaotie 将爬虫封装为 `ScraperTool`，Agent 可以通过自然语言调用：

```
用户: "帮我抓取熊猫球社的门店数据"
Agent: [调用 ScraperTool] -> 自动执行爬虫 -> 返回结果
```

### 2. 异步支持

竞品代码完全基于同步 `requests`。xiaotie 同时支持同步和异步模式：

```python
# 竞品代码 - 仅同步
class MyScraper(BaseScraper):
    def fetch_data_single_run(self, run_number):
        session = self.create_session()
        resp = session.get(url)
        return pd.DataFrame(resp.json())

# xiaotie - 支持异步
class MyScraper(BaseScraper):
    async def fetch_data_single_run(self, run_number):
        async with self.create_async_session() as session:
            resp = await session.get(url)
            return pd.DataFrame(await resp.json())
```

### 3. 统一工具生态

xiaotie 爬虫与其他工具（代理抓包、代码分析、Web 搜索）共享同一个 Tool 框架：

```python
from xiaotie.tools import ScraperTool, ProxyServerTool, WebSearchTool

# 所有工具统一接口
tools = [ScraperTool(), ProxyServerTool(), WebSearchTool()]
agent = Agent(tools=tools)
```

### 4. 代码复用对比

竞品代码 v2.0 已经实现了 90% 的代码复用（从 v1.0 的 550 行降到 135 行）。xiaotie 在此基础上进一步优化：

| 指标 | 竞品 v1.0 | 竞品 v2.0 | xiaotie |
|------|-----------|-----------|---------|
| 平均脚本行数 | ~550 | ~135 | ~100 |
| 代码复用率 | ~10% | ~90% | ~95% |
| 新增品牌工作量 | 2-4 小时 | 30 分钟 | 15 分钟 |
| 需要了解的 API | 全部 | 2 个方法 | 2 个方法 |

### 5. 认证管理

两者都支持 6 种认证方式，但 xiaotie 提供更灵活的配置：

```python
# 竞品代码 - 环境变量或代码硬编码
token = os.getenv('BEARER_TOKEN', '')

# xiaotie - 多层配置优先级
# 1. 代码参数 > 2. 环境变量 > 3. YAML 配置 > 4. 默认值
self.set_auth(AuthType.BEARER, token="xxx")
```

## 迁移指南

从竞品代码迁移到 xiaotie 爬虫非常简单：

### 迁移前（竞品代码 v2.0）

```python
from lib import BaseScraper, ConfigManager

class PandaScraper(BaseScraper):
    def get_brand_name(self):
        return "熊猫球社"

    def fetch_data_single_run(self, run_number):
        session = self.create_session()
        # ... 抓取逻辑
        return pd.DataFrame(data)

scraper = PandaScraper(test_mode=True)
scraper.run()
```

### 迁移后（xiaotie）

```python
from xiaotie.scraper import BaseScraper

class PandaScraper(BaseScraper):
    def get_brand_name(self):
        return "熊猫球社"

    def fetch_data_single_run(self, run_number):
        session = self.create_session()
        # ... 抓取逻辑完全相同
        return pd.DataFrame(data)

scraper = PandaScraper(test_mode=True)
scraper.run()
```

核心抓取逻辑无需修改，只需更改 import 路径。

## 适用场景

| 场景 | 推荐方案 |
|------|----------|
| 快速单次抓取 | 竞品代码（直接运行 Notebook） |
| Agent 自动化调度 | xiaotie（ScraperTool 集成） |
| 新品牌开发 | xiaotie（更少代码、更好测试） |
| 与代理抓包联动 | xiaotie（ProxyServerTool 配合） |
| 定时批量任务 | 两者均可（xiaotie 有 Agent 调度优势） |
| 已有品牌维护 | 竞品代码（已稳定运行） |

## 总结

xiaotie 爬虫模块在竞品代码 v2.0 的 `BaseScraper` 架构基础上，增加了 Agent 集成、异步支持和统一工具生态。对于需要 AI Agent 自动化调度的场景，xiaotie 是更好的选择；对于已有的稳定运行脚本，可以按需逐步迁移。
