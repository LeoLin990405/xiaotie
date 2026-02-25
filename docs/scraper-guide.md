# 爬虫模块使用指南

## 概述

小铁（xiaotie）爬虫模块提供结构化的 Web 数据抓取能力，专为竞品数据采集场景设计。基于 `BaseScraper` 抽象基类，支持多线程并发、多种认证方式、数据稳定性验证和 Agent 工具集成。

### 核心特性

| 特性 | 说明 |
|------|------|
| BaseScraper 基类 | 抽象基类，子类只需实现 2 个方法即可完成爬虫开发 |
| 多线程并发 | 基于 `ThreadPoolExecutor`，可配置线程数和请求间隔 |
| 6 种认证方式 | 无认证、Bearer Token、Cookie、自定义 Header、MD5 签名、网关签名 |
| 3 次运行验证 | 自动执行 3 次抓取，取交集确保数据稳定性 |
| ScraperTool 集成 | 作为 xiaotie Tool 注册，Agent 可通过自然语言调用 |
| 输出管理 | 统一 CSV/JSON 输出，自动归档和稳定性报告 |

## 快速开始

### 安装

爬虫模块随 xiaotie 一起安装：

```bash
pip install -e ".[scraper]"
```

依赖项：`requests`, `pandas`, `tqdm`, `pyyaml`

### 30 秒上手

```python
from xiaotie.scraper import BaseScraper
import pandas as pd

class MyScraper(BaseScraper):
    """自定义爬虫 - 只需实现 2 个方法"""

    def get_brand_name(self) -> str:
        return "示例品牌"

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        session = self.create_session()
        resp = session.get("https://api.example.com/stores")
        data = resp.json().get("data", [])
        return pd.DataFrame(data)

# 测试模式运行
scraper = MyScraper(test_mode=True)
result = scraper.run()
print(f"抓取 {len(result)} 条数据")
```

## BaseScraper 教程

### 基类结构

`BaseScraper` 是所有爬虫的抽象基类，提供完整的抓取框架：

```
BaseScraper
├── 必须实现
│   ├── get_brand_name() -> str          # 品牌名称
│   └── fetch_data_single_run(run) -> DataFrame  # 单次抓取逻辑
├── 可选覆盖
│   ├── setup()                          # 抓取前初始化
│   ├── cleanup()                        # 抓取后清理
│   └── process_data(df) -> DataFrame    # 数据后处理
└── 内置功能
    ├── 3 次运行验证
    ├── 线程池管理
    ├── 会话管理（连接池复用）
    ├── 进度条显示
    ├── CSV 保存 & 稳定性报告
    └── 错误处理 & 重试
```

### 完整示例：带认证的爬虫

```python
from xiaotie.scraper import BaseScraper, AuthType
import pandas as pd

class BearerTokenScraper(BaseScraper):
    """使用 Bearer Token 认证的爬虫"""

    def get_brand_name(self) -> str:
        return "某品牌"

    def setup(self):
        """抓取前初始化：配置认证"""
        self.set_auth(AuthType.BEARER, token="your-token-here")

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        session = self.create_session()
        all_data = []

        # 分页抓取
        page = 1
        while True:
            resp = session.get(
                "https://api.example.com/stores",
                params={"page": page, "size": 20}
            )
            data = resp.json()
            items = data.get("list", [])
            if not items:
                break
            all_data.extend(items)
            page += 1

        return pd.DataFrame(all_data)

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据后处理：清洗和标准化"""
        if "phone" in df.columns:
            df["phone"] = df["phone"].str.replace("-", "")
        return df.drop_duplicates(subset=["store_id"])

# 运行
scraper = BearerTokenScraper(test_mode=False)
result = scraper.run()
```

### 多线程抓取

```python
from xiaotie.scraper import BaseScraper
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

class MultiThreadScraper(BaseScraper):
    """多线程并发抓取"""

    CITIES = ["北京", "上海", "广州", "深圳", "成都"]

    def get_brand_name(self) -> str:
        return "多城市品牌"

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        all_data = []
        cities = self.CITIES[:3] if self.test_mode else self.CITIES

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_city, city): city
                for city in cities
            }
            for future in as_completed(futures):
                city = futures[future]
                try:
                    data = future.result()
                    all_data.extend(data)
                except Exception as e:
                    print(f"  {city} 抓取失败: {e}")

        return pd.DataFrame(all_data)

    def _fetch_city(self, city: str) -> list:
        session = self.create_session()
        resp = session.get(
            "https://api.example.com/stores",
            params={"city": city}
        )
        return resp.json().get("data", [])
```

## 认证配置

### 支持的认证类型

| 类型 | AuthType | 说明 | 示例品牌 |
|------|----------|------|----------|
| 无认证 | `NONE` | 公开 API | 谈小娱、熊猫球社 |
| Bearer Token | `BEARER` | Authorization 头 | 新响袋、安及 |
| Cookie | `COOKIE` | Cookie 头 | 碰碰捌 |
| 自定义 Header | `CUSTOM_HEADER` | 任意 Header 名 | 度小球、小艾台球 |
| MD5 签名 | `MD5_SIGN` | 请求参数签名 | 四个朋友 |
| 网关签名 | `GATEWAY_SIGN` | 网关级签名 | KO台球 |

### 配置方式

```python
# 方式 1：代码中设置
self.set_auth(AuthType.BEARER, token="xxx")

# 方式 2：环境变量（推荐生产环境）
# export BEARER_TOKEN=xxx
self.set_auth(AuthType.BEARER)  # 自动读取环境变量

# 方式 3：YAML 配置文件
# config/brands.yaml 中配置
```

### 环境变量对照表

| 环境变量 | 认证类型 | 用途 |
|----------|----------|------|
| `BEARER_TOKEN` | Bearer | 通用 Bearer Token |
| `JSESSIONID` | Cookie | Java Session ID |
| `USER_TOKEN` | Custom Header | 用户 Token |
| `ITMP_TOKEN` | Custom Header | ITMP Token |
| `ACCESS_TOKEN` | Custom Header | 访问 Token |

## API 参考

### BaseScraper

```python
class BaseScraper(ABC):
    def __init__(
        self,
        output_dir: str | None = None,  # 输出目录
        test_mode: bool = False,         # 测试模式
        max_workers: int = 10,           # 最大线程数
        request_delay: float = 0.3,      # 请求间隔(秒)
        num_runs: int = 3,               # 验证运行次数
        stability_threshold: float = 0.05  # 稳定性阈值
    ): ...

    # 必须实现
    @abstractmethod
    def get_brand_name(self) -> str: ...

    @abstractmethod
    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame: ...

    # 可选覆盖
    def setup(self) -> None: ...
    def cleanup(self) -> None: ...
    def process_data(self, df: pd.DataFrame) -> pd.DataFrame: ...

    # 内置方法
    def run(self) -> pd.DataFrame: ...
    def create_session(self, headers: dict = None) -> requests.Session: ...
    def set_auth(self, auth_type: AuthType, **kwargs) -> None: ...
```

### ScraperTool

```python
class ScraperTool(Tool):
    """Agent 集成的爬虫工具"""

    name = "scraper"
    description = "执行结构化 Web 数据抓取"

    # 参数
    parameters = {
        "action": "run | status | list_brands | configure",
        "brand": "品牌名称或 ID",
        "mode": "test | full",
        "output_dir": "输出目录",
        "auth_token": "认证 Token（可选）"
    }
```

#### ScraperTool 操作

| action | 说明 | 关键参数 |
|--------|------|----------|
| `run` | 执行爬虫抓取 | `brand`, `mode` |
| `status` | 查看运行状态 | - |
| `list_brands` | 列出可用品牌 | - |
| `configure` | 配置爬虫参数 | `brand`, `auth_token` |

### 使用示例

```python
from xiaotie.tools import ScraperTool

scraper_tool = ScraperTool()

# 列出可用品牌
result = await scraper_tool.execute(action="list_brands")
print(result.content)

# 运行爬虫
result = await scraper_tool.execute(
    action="run",
    brand="熊猫球社",
    mode="test"
)
print(result.content)
```

## 故障排查

### 常见问题

#### 1. Token 过期

```
错误: 401 Unauthorized
```

解决方案：
- 通过微信小程序抓包获取新 Token
- 更新环境变量：`export BEARER_TOKEN=新token`
- 或在代码中更新：`self.set_auth(AuthType.BEARER, token="新token")`

#### 2. 请求被限流

```
错误: 429 Too Many Requests
```

解决方案：
- 降低线程数：`max_workers=5`
- 增加请求间隔：`request_delay=1.0`
- 或通过环境变量：`MAX_WORKERS=5 REQUEST_DELAY=1.0 python3 script.py`

#### 3. 数据不稳定

```
警告: 稳定性检查未通过 (变化率: 12%)
```

解决方案：
- 检查 API 是否有实时变动的数据
- 提高稳定性阈值：`stability_threshold=0.15`
- 增加运行次数：`num_runs=5`

#### 4. 连接超时

```
错误: ConnectionTimeout
```

解决方案：
- 检查网络连接
- 增加超时时间（在 `create_session` 中配置）
- 检查目标 API 是否可访问

#### 5. SSL 证书错误

```
错误: SSLError
```

解决方案：
- 更新 `certifi` 包：`pip install --upgrade certifi`
- 如果是自签名证书，在 session 中设置 `verify=False`（仅开发环境）

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

scraper = MyScraper(test_mode=True)
scraper.run()
```

### 性能优化建议

1. 合理设置 `max_workers`（建议 5-15）
2. 使用 `create_session()` 复用连接池
3. 测试模式先验证，再跑完整模式
4. 大数据量时使用分页 + 多线程组合
