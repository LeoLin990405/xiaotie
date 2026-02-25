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

### 3.2 ScraperConfig — 配置管理

```python
# xiaotie/scraper/config.py

from dataclasses import dataclass, field
from typing import List, Tuple
import os


@dataclass
class ScraperConfig:
    """爬虫配置（对应竞品 GlobalConfig，简化为单一 dataclass）"""

    # 并发
    max_concurrency: int = 10          # 最大并发请求数（替代 max_workers）
    request_delay: float = 0.3         # 请求间隔秒数
    request_timeout: int = 15          # 单次请求超时

    # 连接池
    pool_limit: int = 20               # aiohttp 连接池大小

    # 稳定性验证
    num_runs: int = 3                  # 抓取次数
    stability_threshold: float = 0.05  # 变化率阈值 (5%)
    wait_between_runs: float = 3.0     # 两次抓取间等待秒数

    # 重试
    retry_total: int = 3
    retry_backoff: float = 0.5
    retry_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)

    # 输出
    output_dir: str = "./output"
    output_format: str = "json"        # json / csv
    encoding: str = "utf-8"

    # 敏感字段（输出时脱敏）
    sensitive_fields: List[str] = field(default_factory=lambda: [
        "password", "token", "cookie", "phone", "mobile"
    ])

    def __post_init__(self):
        """环境变量覆盖"""
        if v := os.getenv("SCRAPER_MAX_CONCURRENCY"):
            self.max_concurrency = int(v)
        if v := os.getenv("SCRAPER_REQUEST_DELAY"):
            self.request_delay = float(v)
        if v := os.getenv("SCRAPER_NUM_RUNS"):
            self.num_runs = int(v)
        if v := os.getenv("SCRAPER_THRESHOLD"):
            self.stability_threshold = float(v)
```

### 3.3 AsyncSessionManager — 异步会话管理

替代竞品的 `SessionManager`（基于 `threading.local` + `requests`），改用 `aiohttp` 连接池。

```python
# xiaotie/scraper/session.py

import aiohttp
from typing import Any, Dict, Optional

from .config import ScraperConfig
from .auth import AuthManager


class AsyncSessionManager:
    """
    异步 HTTP 会话管理器

    特性:
    - aiohttp.ClientSession 连接池复用
    - 自动重试（通过 aiohttp_retry 或手动实现）
    - 请求限速（asyncio.Semaphore）
    - 认证头自动注入
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.config.pool_limit,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(
                total=self.config.request_timeout
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "XiaoTie-Scraper/1.0",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    async def request(
        self,
        method: str,
        url: str,
        auth: Optional[AuthManager] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        发送限速请求

        自动注入认证头、限制并发、处理重试
        """
        async with self._semaphore:
            session = await self.get_session()

            # 注入认证头
            headers = kwargs.pop("headers", {})
            if auth:
                headers.update(auth.get_headers())
            kwargs["headers"] = headers

            # 请求间隔
            await asyncio.sleep(self.config.request_delay)

            # 重试逻辑
            for attempt in range(self.config.retry_total + 1):
                try:
                    async with session.request(
                        method, url, **kwargs
                    ) as resp:
                        if resp.status in self.config.retry_status_codes:
                            if attempt < self.config.retry_total:
                                wait = self.config.retry_backoff * (2 ** attempt)
                                await asyncio.sleep(wait)
                                continue
                        return {
                            "status": resp.status,
                            "data": await resp.json(content_type=None),
                            "headers": dict(resp.headers),
                        }
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt >= self.config.retry_total:
                        raise

    async def close_all(self):
        """关闭所有连接"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
```

### 3.4 StabilityVerifier — 稳定性验证器

对应竞品的 `StabilityAnalyzer`，核心逻辑保持一致（3次抓取取交集），适配 `List[Dict]` 数据格式。

```python
# xiaotie/scraper/stability.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class StabilityResult:
    """稳定性验证结果"""
    is_stable: bool
    counts: List[int]                  # 每次抓取的数据量
    avg_count: float
    variation: float                   # 变化率 = (max-min)/avg
    common_count: int                  # 交集数量
    total_unique: int                  # 并集数量
    coverage: float                    # common/total 百分比
    common_ids: Set[Any] = field(default_factory=set)
    id_field: Optional[str] = None


class StabilityVerifier:
    """
    稳定性验证器

    核心算法（与竞品一致）:
    1. 执行 N 次抓取
    2. 提取每次数据的 ID 集合
    3. 计算交集（三次都出现的记录）
    4. 变化率 = (max_count - min_count) / avg_count
    5. 变化率 <= threshold 则判定为稳定
    """

    # 自动检测的 ID 字段候选列表
    ID_CANDIDATES = [
        "id", "ID", "store_id", "storeId", "STORE_ID",
        "shop_id", "shopId", "billiards_id", "billiardsId",
        "point_id", "pointId",
    ]

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def verify(
        self,
        datasets: List[List[Dict[str, Any]]],
        id_field: Optional[str] = None,
    ) -> StabilityResult:
        """
        验证多次抓取数据的稳定性

        Args:
            datasets: N 次抓取的数据列表
            id_field: 唯一标识字段名（None 则自动检测）
        """
        counts = [len(ds) for ds in datasets]
        avg = sum(counts) / len(counts) if counts else 0
        mx, mn = max(counts, default=0), min(counts, default=0)
        variation = (mx - mn) / avg if avg > 0 else 0

        # 自动检测 ID 字段
        if id_field is None:
            id_field = self._detect_id_field(datasets)

        if not id_field:
            # 无 ID 字段，仅基于数量判断
            return StabilityResult(
                is_stable=variation <= self.threshold,
                counts=counts, avg_count=avg, variation=variation,
                common_count=mn, total_unique=mx,
                coverage=(mn / mx * 100) if mx > 0 else 0,
            )

        # 基于 ID 对比
        id_sets = [
            {record.get(id_field) for record in ds if id_field in record}
            for ds in datasets
        ]
        common = set.intersection(*id_sets) if id_sets else set()
        total = set.union(*id_sets) if id_sets else set()

        return StabilityResult(
            is_stable=variation <= self.threshold,
            counts=counts, avg_count=avg, variation=variation,
            common_count=len(common), total_unique=len(total),
            coverage=(len(common) / len(total) * 100) if total else 0,
            common_ids=common, id_field=id_field,
        )

    def filter_stable(
        self,
        data: List[Dict[str, Any]],
        result: StabilityResult,
    ) -> List[Dict[str, Any]]:
        """筛选出稳定数据（三次都出现的记录）"""
        if not result.id_field or not result.common_ids:
            return data
        return [
            r for r in data
            if r.get(result.id_field) in result.common_ids
        ]

    def _detect_id_field(
        self, datasets: List[List[Dict]]
    ) -> Optional[str]:
        """自动检测 ID 字段"""
        if not datasets or not datasets[0]:
            return None
        sample_keys = set(datasets[0][0].keys())
        for candidate in self.ID_CANDIDATES:
            if candidate in sample_keys:
                return candidate
        # 回退：找包含 'id' 的字段
        for key in sample_keys:
            if "id" in key.lower():
                return key
        return None
```

### 3.5 AuthManager — 认证管理器

对应竞品的 `AuthHandler`，支持相同的 6 种认证方式，增加异步 token 刷新能力。

```python
# xiaotie/scraper/auth.py

import hashlib
import json
import os
from enum import Enum
from typing import Any, Callable, Dict, Optional


class AuthType(Enum):
    """认证类型（与竞品完全对齐）"""
    NONE = "none"                  # 无认证
    BEARER = "bearer"              # Bearer Token
    COOKIE = "cookie"              # Cookie 认证
    CUSTOM_HEADER = "custom_header"  # 自定义 Header
    MD5_SIGN = "md5_sign"          # MD5 签名
    GATEWAY_SIGN = "gateway_sign"  # 网关签名 (KO/MINIAPP)


class AuthManager:
    """
    认证管理器

    支持 6 种认证方式 + token 自动加载 + 动态刷新回调
    """

    def __init__(
        self,
        auth_type: AuthType = AuthType.NONE,
        token: Optional[str] = None,
        token_env_key: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        refresh_callback: Optional[Callable] = None,
    ):
        self.auth_type = auth_type
        self._token = token
        self._token_env_key = token_env_key
        self._custom_headers = custom_headers or {}
        self._refresh_callback = refresh_callback

    @property
    def token(self) -> str:
        """获取 token（优先环境变量）"""
        if self._token_env_key:
            env_val = os.getenv(self._token_env_key, "")
            if env_val.strip():
                return env_val.strip()
        return self._token or ""

    def get_headers(self, **kwargs) -> Dict[str, str]:
        """根据认证类型生成请求头"""
        if self.auth_type == AuthType.NONE:
            return {}
        elif self.auth_type == AuthType.BEARER:
            return {"Authorization": f"Bearer {self.token}"}
        elif self.auth_type == AuthType.COOKIE:
            return {"Cookie": self.token}
        elif self.auth_type == AuthType.CUSTOM_HEADER:
            return self._custom_headers
        return {}

    @staticmethod
    def md5_sign(
        channel_code: str, biz_content: str, api_key: str
    ) -> str:
        """MD5 签名（四个朋友、KO台球等）"""
        sign_str = f"{channel_code}{biz_content}{api_key}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    @staticmethod
    def create_gateway_payload(
        method: str,
        biz_dict: dict,
        channel_code: str = "h5_api_get",
        api_key: str = "",
        token: Optional[str] = None,
    ) -> dict:
        """创建网关签名请求体（KO台球）"""
        biz_content = json.dumps(
            biz_dict, separators=(",", ":"), ensure_ascii=False
        )
        sign = AuthManager.md5_sign(channel_code, biz_content, api_key)
        payload = {
            "method": method,
            "channelCode": channel_code,
            "channelType": "KO",
            "platformType": "MINIAPP",
            "appType": "WEIXIN",
            "deviceType": "IOS",
            "timestamp": "123123",
            "bizContent": biz_content,
            "sign": sign,
        }
        if token:
            payload["token"] = token
        return payload

    async def refresh_token(self) -> Optional[str]:
        """异步刷新 token（如果设置了回调）"""
        if self._refresh_callback:
            self._token = await self._refresh_callback()
            return self._token
        return None
```

### 3.6 OutputManager — 输出管理

```python
# xiaotie/scraper/output.py

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class OutputManager:
    """输出管理器 — JSON/CSV 保存 + 脱敏预览"""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        data: List[Dict[str, Any]],
        brand_name: str,
        test_mode: bool = False,
        fmt: str = "json",
    ) -> str:
        """保存数据，返回文件路径"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        mode_str = "test" if test_mode else "full"
        ext = "json" if fmt == "json" else "csv"
        filename = f"{brand_name}_{mode_str}_{date_str}.{ext}"
        filepath = self.output_dir / filename

        if fmt == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            self._save_csv(data, filepath)

        return str(filepath)

    def _save_csv(self, data: List[Dict], filepath: Path):
        if not data:
            filepath.write_text("")
            return
        keys = list(data[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
```

### 3.7 ScraperRegistry — 爬虫注册表

```python
# xiaotie/scraper/registry.py

from typing import Dict, List, Optional, Type
from .base import BaseScraper


class ScraperRegistry:
    """
    爬虫注册表 — 管理所有可用的爬虫类

    支持:
    - 按名称注册/查找爬虫
    - 动态加载爬虫模块
    - 列出所有可用爬虫
    """

    _scrapers: Dict[str, Type[BaseScraper]] = {}

    @classmethod
    def register(cls, name: str):
        """装饰器：注册爬虫类"""
        def decorator(scraper_cls: Type[BaseScraper]):
            cls._scrapers[name] = scraper_cls
            return scraper_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseScraper]]:
        return cls._scrapers.get(name)

    @classmethod
    def list_all(cls) -> List[Dict[str, str]]:
        return [
            {"name": name, "class": klass.__name__}
            for name, klass in cls._scrapers.items()
        ]

    @classmethod
    def load_from_directory(cls, directory: str):
        """从目录动态加载爬虫模块"""
        import importlib.util
        from pathlib import Path
        for py_file in Path(directory).glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(
                py_file.stem, py_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
```

---

## 4. ScraperTool — Agent 工具接口

这是 xiaotie Agent 调用爬虫的唯一入口，继承 `xiaotie.tools.base.Tool`，遵循 action 模式（与 `ProxyServerTool` 一致）。

```python
# xiaotie/tools/scraper_tool.py

class ScraperTool(Tool):
    """
    爬虫工具 — 将爬虫模块集成到 xiaotie Agent 框架

    Actions:
        - scrape: 运行指定爬虫抓取数据（单次）
        - verify: 运行爬虫并执行 3 次稳定性验证
        - export: 导出上次抓取结果
        - list_scrapers: 列出所有可用爬虫
        - status: 查看当前爬虫运行状态
        - create_scraper: 从模板创建新爬虫
    """

    @property
    def name(self) -> str:
        return "scraper"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "scrape", "verify", "export",
                        "list_scrapers", "status", "create_scraper",
                    ],
                },
                "scraper_name": {"type": "string"},
                "test_mode": {"type": "boolean", "default": True},
                "output_format": {
                    "type": "string", "enum": ["json", "csv"],
                },
                "config": {"type": "object"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        dispatch = {
            "scrape": self._action_scrape,
            "verify": self._action_verify,
            "export": self._action_export,
            "list_scrapers": self._action_list,
            "status": self._action_status,
            "create_scraper": self._action_create,
        }
        handler = dispatch.get(action)
        if not handler:
            return ToolResult(success=False, error=f"未知操作: {action}")
        return await handler(**kwargs)
```

完整实现见 `xiaotie/tools/scraper_tool.py`。

---

## 5. 事件集成

ScraperTool 通过 xiaotie 的 `EventBroker` 发布以下事件：

| 事件类型 | 触发时机 | 数据 |
|---------|---------|------|
| `SCRAPER_START` | 爬虫开始运行 | `{brand_name, test_mode, num_runs}` |
| `SCRAPER_RUN_COMPLETE` | 单次抓取完成 | `{run_number, record_count, elapsed}` |
| `SCRAPER_VERIFY_COMPLETE` | 稳定性验证完成 | `{StabilityResult}` |
| `SCRAPER_COMPLETE` | 整体运行完成 | `{ScraperRunResult}` |
| `SCRAPER_ERROR` | 抓取出错 | `{error, run_number}` |

---

## 6. 与 xiaotie Agent 系统集成

### 6.1 工具注册

```python
# xiaotie/tools/__init__.py 中添加
from .scraper_tool import ScraperTool

# Agent 构建时注册
agent = (
    AgentBuilder()
    .with_tools([ScraperTool(scraper_dir="./scrapers")])
    .build()
)
```

### 6.2 Agent 自然语言调用示例

```
用户: 帮我抓取谈小娱的数据，测试模式
Agent: [调用 scraper tool, action=scrape, scraper_name=tanxiaoyu, test_mode=true]

用户: 验证一下数据稳定性
Agent: [调用 scraper tool, action=verify, scraper_name=tanxiaoyu]

用户: 有哪些可用的爬虫？
Agent: [调用 scraper tool, action=list_scrapers]
```

### 6.3 与认知系统集成

- **MemoryManager**: 存储历史抓取结果和稳定性趋势
- **DecisionEngine**: 根据历史数据决定是否需要重新抓取
- **PlanningSystem**: 编排多品牌批量抓取计划
- **ReflectionManager**: 分析抓取失败原因，调整策略

---

## 7. 数据流图

```
Agent 收到用户指令
    |
    v
ScraperTool.execute(action="verify", scraper_name="xxx")
    |
    v
ScraperRegistry.get("xxx") -> XxxScraper 类
    |
    v
BaseScraper.run()
    +-- setup()
    +-- for i in range(3):
    |   +-- fetch_single_run(i+1)
    |   |   +-- AsyncSessionManager.request()  <- AuthManager.get_headers()
    |   |   +-- return ScrapeResult
    |   +-- EventBroker.publish(SCRAPER_RUN_COMPLETE)
    +-- StabilityVerifier.verify(datasets)
    +-- StabilityVerifier.filter_stable()
    +-- process_data()
    +-- OutputManager.save()
    +-- cleanup()
    |
    v
ScraperTool -> ToolResult(content="验证完成: ...")
    |
    v
Agent 返回结果给用户
```

---

## 8. 创建新爬虫指南

只需实现 2 个方法，约 50-100 行代码：

```python
from xiaotie.scraper.base import BaseScraper, ScrapeResult
from xiaotie.scraper.auth import AuthManager
from xiaotie.scraper.registry import ScraperRegistry


@ScraperRegistry.register("tanxiaoyu")
class TanXiaoYuScraper(BaseScraper):

    BASE_URL = "https://gatewayapi.example.com/api/gateway"
    API_KEY = "example_key"

    @property
    def brand_name(self) -> str:
        return "谈小娱"

    def get_id_field(self) -> str:
        return "billiardsId"

    async def fetch_single_run(self, run_number: int) -> ScrapeResult:
        all_items = []
        tasks = []
        for city_id in range(1, 600):
            tasks.append(self._fetch_city(city_id))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_items.extend(r)
        return ScrapeResult(
            success=True, data=all_items, record_count=len(all_items),
        )

    async def _fetch_city(self, city_id: int) -> list:
        payload = AuthManager.create_gateway_payload(
            method="com.example.api.list",
            biz_dict={"cityId": city_id, "page": {"start": 1, "limit": 15}},
            api_key=self.API_KEY,
        )
        resp = await self.session_manager.request("POST", self.BASE_URL, json=payload)
        return resp.get("data", {}).get("items", [])
```

---

## 9. 架构决策记录 (ADR)

### ADR-S01: 用 asyncio 替代 threading

- **决策**: 全异步架构
- **理由**: xiaotie 核心是 async/await（ADR-006），爬虫模块必须保持一致。aiohttp 在高并发 I/O 场景下性能优于 threading + requests。

### ADR-S02: 用 List[Dict] 替代 DataFrame

- **决策**: 核心数据结构使用 `List[Dict[str, Any]]`
- **理由**: 避免强依赖 pandas（xiaotie 是轻量框架），Dict 列表更适合 JSON 序列化和 Agent 工具链传递。

### ADR-S03: 注册表模式管理爬虫

- **决策**: 使用 `ScraperRegistry` + 装饰器注册
- **理由**: 支持动态发现和加载爬虫，Agent 可通过名称调用，无需硬编码导入。

### ADR-S04: Action 模式暴露工具

- **决策**: ScraperTool 使用 action 参数分发操作（与 ProxyServerTool 一致）
- **理由**: 保持 xiaotie 工具系统的一致性，Agent 通过单一工具名 + action 参数调用所有爬虫功能。
