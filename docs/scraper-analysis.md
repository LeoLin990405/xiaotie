# 竞品爬虫代码架构分析报告

**分析日期**: 2026-02-25
**代码版本**: v2.2.0 (py_2026-01-20)
**代码位置**: `/Users/leo/Desktop/竞品代码/新竞品代码/`

---

## 1. 项目概述

该竞品代码是一个面向中国台球/娱乐场所的多品牌门店数据抓取系统，覆盖19个品牌。系统从v1.0（每品牌独立脚本，500-1000行）演进到v2.0（基于继承的统一架构，100-200行/品牌），代码复用率从10%提升到90%。

### 核心指标
- 品牌数量: 19个
- 核心库模块: 10个 (`lib/` 目录)
- 认证方式: 6种
- 代码减少率: 平均75%
- 性能提升: 约17-20%（连接池复用）

---

## 2. 整体架构

### 2.1 目录结构

```
新竞品代码/
├── lib/                          # 核心共享库 (10个模块)
│   ├── __init__.py              # 模块导出 (v2.2.0)
│   ├── base_scraper.py          # BaseScraper 抽象基类 (330行)
│   ├── config.py                # ConfigManager 配置管理 (214行)
│   ├── threading_utils.py       # SessionManager + ThreadStats (183行)
│   ├── stability.py             # StabilityAnalyzer 稳定性分析 (279行)
│   ├── output.py                # OutputManager 输出管理 (189行)
│   ├── auth.py                  # AuthHandler 认证处理 (180行)
│   ├── data_processor.py        # DataProcessor 数据处理 (241行)
│   ├── field_aligner.py         # FieldAligner 字段对齐 (325行)
│   ├── geocoder.py              # TencentGeocoder 地理编码 (112行)
│   └── monitoring.py            # 性能监控+日志+链路追踪 (653行)
│
├── config/                       # YAML配置
│   ├── settings.yaml            # 全局设置
│   ├── brands.yaml              # 19品牌配置
│   ├── field_mapping.yaml       # 字段映射规则
│   └── secrets.env.example      # Token模板
│
├── archive/py_2026-01-20/       # 19个品牌脚本
└── output/                       # 统一输出目录
```

### 2.2 架构模式: Template Method + Strategy

核心设计采用模板方法模式。`BaseScraper` 定义了完整的抓取流程骨架（`run()` 方法），子类只需实现两个抽象方法：

```
BaseScraper.run()  流程:
  1. setup()              ← 可选钩子
  2. for i in range(3):   ← 3次抓取验证
       fetch_data_single_run(i)  ← 子类必须实现
  3. StabilityAnalyzer.compare_dataframes()
  4. filter_stable_data()
  5. process_data()       ← 可选钩子
  6. save_csv() + save_report()
  7. cleanup()            ← 可选钩子
```

子类合约：
- `get_brand_name() -> str` — 返回品牌中文名
- `fetch_data_single_run(run_number) -> pd.DataFrame` — 实现品牌特定的API调用逻辑

---

## 3. 核心模块详解

### 3.1 BaseScraper (base_scraper.py, 330行)

抽象基类，是整个系统的骨架。

关键职责：
- 编排3次抓取 + 稳定性分析 + 保存的完整流程
- 管理 ConfigManager、SessionManager、StabilityAnalyzer、OutputManager 的生命周期
- 提供 `create_thread_pool_executor()`、`create_session()`、`get_request_delay()` 等便捷方法
- 统计信息通过 `ThreadStats` 实例 (`self.stats`) 跟踪

设计亮点：
- 组合优于继承：内部组合了4个管理器对象
- 钩子方法：`setup()`、`cleanup()`、`process_data()` 提供扩展点
- 异常隔离：每次抓取失败不影响后续运行

### 3.2 ConfigManager (config.py, 214行)

基于 dataclass 的分层配置系统。

配置层次（优先级从高到低）：
1. 环境变量覆盖 (`MAX_WORKERS`, `REQUEST_DELAY`, `NUM_RUNS`, `STABILITY_THRESHOLD`)
2. YAML配置文件 (`config/settings.yaml`)
3. dataclass 默认值

四个配置域：
- `ThreadingConfig`: max_workers=10, request_delay=0.3, pool_connections=12, pool_maxsize=20
- `StabilityConfig`: num_runs=3, threshold=0.05, wait_between_runs=3
- `RetryConfig`: total=3, backoff_factor=0.5, status_forcelist=(429,500,502,503,504)
- `OutputConfig`: encoding='utf-8-sig', archive_days=7

支持点号路径访问：`config.get('threading.max_workers')`

### 3.3 SessionManager + ThreadStats (threading_utils.py, 183行)

线程安全的HTTP会话管理。

SessionManager 核心机制：
- **Thread-Local Storage**: 每个线程维护独立的 `requests.Session`，通过 `threading.local()` 实现
- **连接池复用**: 使用 `HTTPAdapter` 配置 `pool_connections=12`, `pool_maxsize=20`
- **自动重试**: 通过 `urllib3.util.retry.Retry` 实现指数退避重试
- **会话生命周期**: `create_session()` → 懒创建 → `close_session()` / `reset_session()`

ThreadStats 线程安全统计：
- 使用 `threading.Lock()` 保护所有读写操作
- 跟踪 `total_requests`, `success_requests`, `failed_requests`
- 支持 `increment()`, `set()`, `get()`, `reset()`, `to_dict()`

### 3.4 StabilityAnalyzer (stability.py, 279行)

3次抓取验证的核心算法。

验证流程：
1. 自动检测ID列（候选列表：id, store_id, storeId, shop_id, billiardsId 等）
2. 提取3次抓取的ID集合
3. 计算交集（三次都出现）和并集（至少出现一次）
4. 变化率 = (max_count - min_count) / avg_count
5. 稳定判定：变化率 <= 5% 为稳定

降级策略：
- 有ID列 → 基于ID精确对比 (`_compare_by_id`)
- 无ID列 → 基于数量对比 (`_compare_by_count`)

输出 `StabilityResult` dataclass，包含：is_stable, variation, coverage, common_ids, all_ids 等

`filter_stable_data()` 从第1次抓取数据中筛选出三次都出现的记录作为最终数据集。

### 3.5 AuthHandler (auth.py, 180行)

6种认证方式的统一处理。

| 认证类型 | 枚举值 | 使用品牌 | 实现方式 |
|---------|--------|---------|---------|
| 无认证 | `NONE` | 熊猫球社、帅猫、貘鱼、豆豆、脉冲、龙小球、球小闲 | 空headers |
| Bearer Token | `BEARER` | 新响袋、安及、雀发潮 | `Authorization: Bearer {token}` |
| Cookie | `COOKIE` | 碰碰捌 | `Cookie: JSESSIONID={token}` |
| 自定义Header | `CUSTOM_HEADER` | 度小球、小艾、甩杆青年、七悠球 | 品牌特定header名 |
| MD5签名 | `MD5_SIGN` | 四个朋友台球/棋牌 | `md5(channel_code + biz_content + api_key)` |
| 网关签名 | `GATEWAY_SIGN` | 谈小娱、KO台球 | 完整gateway payload构造 |

关键方法：
- `md5_sign()`: MD5哈希签名
- `create_gateway_payload()`: 构造KO/MINIAPP网关请求体（含channelType、platformType、appType、sign等）
- `load_token_from_env()`: 从环境变量安全加载token
- `inject_tokens_to_module()`: 动态注入token到模块属性

### 3.6 OutputManager (output.py, 189行)

统一的文件输出管理。

功能：
- CSV保存：自动命名 `{品牌}_{稳定版测试|稳定版完整}_{日期}.csv`
- 报告保存：`{品牌}_稳定性报告_{日期}.txt`
- 自动归档：超过N天的旧文件移动到 `output/archive/{日期}/`
- 敏感信息脱敏预览：递归处理dict/list中的敏感字段（password, token, phone等）

日期策略：默认使用最近的周日日期（`_get_sunday_date()`），适配周报场景。

### 3.7 DataProcessor (data_processor.py, 241行)

数据清洗和转换工具集。

核心能力：
- **智能地址列检测**: 支持10种列名变体（address, STORE_ADDR, 地址, fullAddress等）
- **JSON地址提取**: 从嵌套JSON/Python dict字符串中提取地址（支持3种解析策略）
- **嵌套值提取**: `extract_nested_value(data, 'result', 'data', 'list', 0, 'name')`
- **地址清洗**: 移除数字及后续内容用于地理编码
- **DataFrame去重/清理/列名标准化**

### 3.8 FieldAligner (field_aligner.py, 325行)

跨品牌字段标准化工具。

基于 `config/field_mapping.yaml` 配置驱动：
- 将不同品牌的异构字段映射到统一标准字段
- 支持直接映射、JSON路径提取、多字段组合
- 保留原始字段（加 `raw_` 前缀）
- 字段清洗：空值处理、类型转换、值映射
- 按标准顺序重排列

### 3.9 TencentGeocoder (geocoder.py, 112行)

腾讯地图地理编码服务封装。

- 地址 → 省/市/区 转换
- 内置速率限制（默认4次/秒）
- 降级机制：主地址失败时尝试备用关键词
- 用于补全缺少省市区信息的门店数据

### 3.10 Monitoring (monitoring.py, 653行)

企业级可观测性模块（最大的单个模块）。

三大支柱：
1. **PerformanceMonitor**: 后台线程采集CPU/内存指标，告警系统（高内存>500MB、高CPU>80%、高错误率>10%）
2. **StructuredLogger**: 基于loguru的结构化日志，自动注入trace_id/span_id，日志轮转（每日/保留7天）
3. **TracingContext**: 分布式链路追踪（Singleton + Thread-Local），Span嵌套，`@trace_operation` 装饰器

附加：
- `PerformanceDashboard`: 基于FastAPI+WebSocket的实时监控仪表盘（Chart.js可视化）
- 全局单例访问：`get_monitor()`, `get_logger()`, `get_tracing()`

---

## 4. 三次抓取验证机制详解

这是整个系统最核心的数据质量保障机制。

### 4.1 流程

```
Run 1 → DataFrame A (e.g., 500条)
  ↓ 等待3秒
Run 2 → DataFrame B (e.g., 498条)
  ↓ 等待3秒
Run 3 → DataFrame C (e.g., 501条)
  ↓
StabilityAnalyzer.compare_dataframes(A, B, C)
  ↓
1. 自动检测ID列 (id/store_id/billiardsId...)
2. IDs_A ∩ IDs_B ∩ IDs_C = common_ids (三次都出现)
3. variation = (max-min)/avg = (501-498)/499.7 = 0.6%
4. 0.6% <= 5% → is_stable = True
  ↓
filter_stable_data(A, result) → 只保留common_ids中的记录
  ↓
保存CSV + 生成稳定性报告
```

### 4.2 设计意图

- 消除API返回数据的随机波动（分页、排序不稳定等）
- 确保最终数据集的可靠性（只保留三次都出现的记录）
- 5%阈值平衡了数据完整性和实际波动

---

## 5. 多线程架构和线程安全

### 5.1 线程模型

```
主线程
  ├── ThreadPoolExecutor (max_workers=10)
  │   ├── Worker 1 → Thread-Local Session → HTTP请求
  │   ├── Worker 2 → Thread-Local Session → HTTP请求
  │   ├── ...
  │   └── Worker 10 → Thread-Local Session → HTTP请求
  │
  ├── ThreadStats (threading.Lock 保护)
  └── tqdm 进度条 (主线程更新)
```

### 5.2 线程安全机制

| 共享资源 | 保护方式 | 位置 |
|---------|---------|------|
| HTTP Session | Thread-Local Storage | `SessionManager._session_local` |
| 请求统计 | `threading.Lock` | `ThreadStats._lock` |
| 数据收集 | `as_completed()` + 主线程聚合 | 各品牌脚本 |
| 监控指标 | `threading.Lock` | `PerformanceMonitor._alert_lock` |
| 日志输出 | loguru `enqueue=True` | `StructuredLogger` |

### 5.3 连接池配置

```python
HTTPAdapter(
    max_retries=Retry(total=3, backoff_factor=0.5),
    pool_connections=12,  # 连接池中保持的连接数
    pool_maxsize=20,      # 连接池最大连接数
)
```

---

## 6. 六种认证方式实现

| # | 类型 | 品牌 | Token来源 | 签名算法 |
|---|------|------|----------|---------|
| 1 | 无认证 | 8个品牌 | - | - |
| 2 | Bearer Token | 新响袋、安及、雀发潮 | `BEARER_TOKEN` env | - |
| 3 | Cookie | 碰碰捌 | `JSESSIONID` env | - |
| 4 | 自定义Header | 度小球(`User-Token`)、小艾(`itmp-token`)、甩杆(`access-token`)、七悠球(`token`) | 各自env变量 | - |
| 5 | MD5签名 | 四个朋友台球/棋牌 | 内置api_key | `md5(channel_code + biz_content + api_key)` |
| 6 | 网关签名 | 谈小娱、KO台球 | 内置api_key | MD5签名 + 完整gateway payload |

网关签名payload结构（KO台球）：
```json
{
  "method": "com.yuyuka.billiards.api.new.billiards.rcmd.list",
  "channelCode": "h5_api_get",
  "channelType": "KO",
  "platformType": "MINIAPP",
  "appType": "WEIXIN",
  "deviceType": "IOS",
  "timestamp": "123123",
  "bizContent": "{...}",
  "sign": "md5(channelCode + bizContent + apiKey)"
}
```

---

## 7. 可复用的设计模式和组件

### 7.1 直接可复用的模式

| 模式 | 组件 | 复用价值 | 适用场景 |
|------|------|---------|---------|
| Template Method | `BaseScraper` | 高 | 任何多品牌/多源数据抓取 |
| Thread-Local Session | `SessionManager` | 高 | 多线程HTTP请求场景 |
| 3次验证 | `StabilityAnalyzer` | 高 | 数据质量要求高的抓取 |
| 分层配置 | `ConfigManager` | 中 | YAML + env变量配置管理 |
| 统一认证 | `AuthHandler` | 中 | 多种认证方式的API调用 |
| 字段标准化 | `FieldAligner` | 中 | 异构数据源字段统一 |

### 7.2 架构层面的可借鉴点

1. **继承 + 组合的平衡**: BaseScraper用继承定义流程，用组合管理功能模块
2. **配置驱动**: 通过YAML集中管理19个品牌的差异化配置
3. **渐进式降级**: ID对比 → 数量对比；主地址 → 备用关键词
4. **敏感信息管理**: 环境变量 > 配置文件 > 硬编码，预览时自动脱敏
5. **可观测性**: 结构化日志 + 链路追踪 + 性能监控三位一体

### 7.3 值得注意的局限

1. `BaseScraper.run()` 硬编码了3个DataFrame参数传递给 `compare_dataframes()`，不够灵活
2. 品牌脚本中仍有部分硬编码（如API密钥、默认坐标），未完全从brands.yaml读取
3. `monitoring.py` 依赖 `psutil` 和可选的 `loguru`/`fastapi`，增加了依赖复杂度
4. 地理编码是串行的（逐行iterrows），未利用多线程
5. 部分品牌脚本调用 `run_v21()` 而非 `run()`，说明基类可能有版本分支

---

## 8. 品牌脚本实现模式

### 8.1 典型结构（以熊猫球社为例）

```python
class PandaBallScraper(BaseScraper):
    # 1. API端点常量
    BASE_CITY = 'https://api.pandaball.cc/api/location/city'
    BASE_SHOP_LIST = 'https://api.pandaball.cc/api/shop/lists'

    # 2. 构造函数：设置output_dir + 品牌特定参数
    def __init__(self, test_mode=False, output_dir=None): ...

    # 3. 必须实现：品牌名
    def get_brand_name(self) -> str: return "熊猫球社"

    # 4. 必须实现：单次抓取逻辑
    def fetch_data_single_run(self, run_number) -> pd.DataFrame:
        cities = self.get_city_list()
        # ThreadPoolExecutor并发获取各城市门店
        # tqdm显示进度
        return pd.DataFrame(all_shops)

    # 5. 品牌特定辅助方法
    def get_city_list(self) -> List: ...
    def fetch_city_shops(self, city_id, max_pages) -> tuple: ...
```

### 8.2 复杂品牌（KO台球）的额外特性

- 网关签名认证（`call_gateway()` 封装）
- 城市ID范围遍历（1-600）而非城市列表API
- 嵌套JSON响应展平（`flatten_list_items()`）
- 可选地理编码增强（`enrich_with_geocoding()`）

---

## 9. 总结

该竞品代码展示了一个成熟的多品牌数据抓取框架，核心价值在于：

1. **BaseScraper模板方法** — 将通用流程（3次验证、稳定性分析、输出管理）与品牌特定逻辑完全解耦
2. **3次抓取验证机制** — 通过交集过滤确保数据质量，是该系统最独特的设计
3. **线程安全的Session管理** — Thread-Local + 连接池复用，兼顾并发性能和安全性
4. **配置驱动架构** — YAML + 环境变量的分层配置，支持19个品牌的差异化管理
5. **完整的可观测性** — 从结构化日志到链路追踪到实时监控仪表盘

对于xiaotie项目，最值得借鉴的是BaseScraper的模板方法模式、StabilityAnalyzer的数据验证机制、以及SessionManager的线程安全设计。
