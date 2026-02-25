# ScraperTool 架构设计文档

> 版本: 1.0.0 | 模块: xiaotie.scraper | 设计者: architect

## 1. 设计目标

将竞品代码的多线程爬虫框架（BaseScraper + 6大核心模块）重构为 xiaotie 原生的异步爬虫系统，完全融入 xiaotie 的 Agent 工具链、事件驱动架构和认知系统。

核心原则：
- **异步优先**：用 `asyncio` + `aiohttp` 替代 `threading` + `requests`
- **Tool 原生**：继承 `xiaotie.tools.base.Tool`，通过 action 模式暴露给 Agent
- **事件驱动**：所有关键节点发布事件，与 xiaotie EventBroker 集成
- **可组合**：各子模块独立可测试，通过依赖注入组合

---

## 2. 模块总览

```
xiaotie/
├── scraper/                    # 爬虫核心模块
│   ├── __init__.py
│   ├── base.py                 # BaseScraper 异步抽象基类
│   ├── config.py               # ScraperConfig 配置管理
│   ├── session.py              # AsyncSessionManager 异步会话管理
│   ├── stability.py            # StabilityVerifier 稳定性验证器
│   ├── auth.py                 # AuthManager 认证管理器
│   ├── output.py               # OutputManager 输出管理
│   └── registry.py             # ScraperRegistry 爬虫注册表
├── tools/
│   └── scraper_tool.py         # ScraperTool (Agent 工具接口)
```

---

## 3. 核心组件设计

### 3.1 BaseScraper — 异步抽象基类

竞品的 `BaseScraper` 基于同步 threading，xiaotie 版本改为全异步设计。

```python
# xiaotie/scraper/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import asyncio
import time

from .config import ScraperConfig
from .session import AsyncSessionManager
from .stability import StabilityVerifier, StabilityResult
from .auth import AuthManager, AuthType
from .output import OutputManager


@dataclass
class ScrapeResult:
    """单次抓取结果"""
    success: bool
    data: List[Dict[str, Any]]       # 原始数据列表
    record_count: int = 0
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScraperRunResult:
    """完整运行结果（含稳定性验证）"""
    brand_name: str
    final_data: List[Dict[str, Any]]
    stability: Optional[StabilityResult] = None
    run_results: List[ScrapeResult] = field(default_factory=list)
    total_elapsed: float = 0.0
    output_path: Optional[str] = None


class BaseScraper(ABC):
    """
    异步爬虫抽象基类

    子类必须实现:
        - brand_name: 品牌名称属性
        - fetch_single_run(run_number) -> ScrapeResult: 单次抓取逻辑

    可选覆盖:
        - setup(): 抓取前初始化
        - cleanup(): 抓取后清理
        - get_id_field() -> str: 返回数据唯一标识字段名
        - process_data(data) -> data: 数据后处理
    """

    def __init__(
        self,
        config: Optional[ScraperConfig] = None,
        auth: Optional[AuthManager] = None,
        output_dir: Optional[str] = None,
    ):
        self.config = config or ScraperConfig()
        self.auth = auth or AuthManager(AuthType.NONE)
        self.session_manager = AsyncSessionManager(self.config)
        self.verifier = StabilityVerifier(
            threshold=self.config.stability_threshold
        )
        self.output = OutputManager(
            output_dir or self.config.output_dir
        )

    @property
    @abstractmethod
    def brand_name(self) -> str:
        """品牌名称"""
        ...

    @abstractmethod
    async def fetch_single_run(self, run_number: int) -> ScrapeResult:
        """
        执行单次数据抓取（子类必须实现）

        Args:
            run_number: 第几次运行 (1-based)

        Returns:
            ScrapeResult 包含抓取到的数据
        """
        ...

    def get_id_field(self) -> Optional[str]:
        """返回数据的唯一标识字段名，用于稳定性对比"""
        return None  # 默认自动检测

    async def setup(self):
        """抓取前初始化（可选覆盖）"""
        pass

    async def cleanup(self):
        """抓取后清理（可选覆盖）"""
        await self.session_manager.close_all()

    def process_data(
        self, data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """数据后处理（可选覆盖）"""
        return data

    async def run(self, test_mode: bool = False) -> ScraperRunResult:
        """
        执行完整抓取流程：setup → N次抓取 → 稳定性验证 → 保存 → cleanup

        Args:
            test_mode: 测试模式（限制数据量）

        Returns:
            ScraperRunResult 完整运行结果
        """
        await self.setup()
        start = time.monotonic()

        run_results: List[ScrapeResult] = []
        num_runs = self.config.num_runs

        for i in range(num_runs):
            result = await self.fetch_single_run(run_number=i + 1)
            run_results.append(result)

            # 发布事件（与 xiaotie EventBroker 集成）
            # await self._publish_run_event(i + 1, result)

            if i < num_runs - 1:
                await asyncio.sleep(self.config.wait_between_runs)

        # 稳定性验证
        datasets = [r.data for r in run_results]
        stability = self.verifier.verify(
            datasets, id_field=self.get_id_field()
        )

        # 筛选稳定数据
        final_data = self.verifier.filter_stable(
            datasets[0], stability
        )
        final_data = self.process_data(final_data)

        # 保存
        output_path = self.output.save(
            final_data,
            brand_name=self.brand_name,
            test_mode=test_mode,
        )

        elapsed = time.monotonic() - start
        await self.cleanup()

        return ScraperRunResult(
            brand_name=self.brand_name,
            final_data=final_data,
            stability=stability,
            run_results=run_results,
            total_elapsed=elapsed,
            output_path=output_path,
        )
```

**与竞品对比：**

| 特性 | 竞品 BaseScraper | xiaotie BaseScraper |
|------|-----------------|---------------------|
| 并发模型 | `threading.ThreadPoolExecutor` | `asyncio` + `aiohttp` |
| 会话管理 | `threading.local()` + `requests.Session` | `aiohttp.ClientSession` 连接池 |
| 数据格式 | `pd.DataFrame` | `List[Dict]`（轻量，按需转 DataFrame） |
| 事件通知 | `print()` 直接输出 | `EventBroker` 发布事件 |
| 配置 | YAML + env | Pydantic dataclass + env |
| 输出 | CSV only | JSON / CSV / HAR |
