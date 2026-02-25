# 小铁内置代理服务器架构设计

> 版本: 0.1.0 | 核心库: mitmproxy | 状态: 设计阶段

## 1. 设计目标

替换外部 Charles Proxy 依赖，在 xiaotie 框架内实现轻量级 HTTPS 代理服务器，专注于小程序流量捕获与分析。

**核心需求:**
- 零外部依赖启动（不再需要安装 Charles）
- 自动 HTTPS 解密（CA 证书自动生成与管理）
- 小程序流量智能识别与过滤
- HAR 格式导出，兼容现有分析管线
- 与 xiaotie 异步架构无缝集成

**非目标:**
- 不做通用代理网关
- 不做流量修改/重放（v1 不含）
- 不做 GUI 界面

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    xiaotie Agent                        │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ ProxyServer  │◄──►│  EventBroker │                   │
│  │    Tool      │    │  (Pub/Sub)   │                   │
│  └──────┬───────┘    └──────────────┘                   │
│         │                                               │
│  ┌──────▼───────────────────────────────────────────┐   │
│  │              ProxyServer (核心)                    │   │
│  │                                                   │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │   │
│  │  │ CertManager │  │ FlowCapture  │  │ MiniApp  │ │   │
│  │  │ (证书管理)   │  │ (流量捕获)    │  │ Detector │ │   │
│  │  └─────────────┘  └──────┬───────┘  └──────────┘ │   │
│  │                          │                        │   │
│  │  ┌───────────────────────▼────────────────────┐   │   │
│  │  │          FlowStorage (存储层)               │   │   │
│  │  │  ┌────────────┐  ┌─────────────────────┐   │   │   │
│  │  │  │ MemoryRing  │  │  HARExporter        │   │   │   │
│  │  │  │ (环形缓冲)  │  │  (HAR/JSON 导出)    │   │   │   │
│  │  │  └────────────┘  └─────────────────────┘   │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │              mitmproxy (底层引擎)                  │   │
│  │  asyncio master → ProxyServer addon pipeline     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 3. 核心模块设计

### 3.1 ProxyServerTool — Agent 工具接口

继承 `xiaotie.tools.base.Tool`，作为 Agent 调用入口。

```python
class ProxyServerTool(Tool):
    """内置代理服务器工具"""

    @property
    def name(self) -> str:
        return "proxy_server"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "start", "stop", "status",
                        "export", "clear",
                        "filter_miniapp", "list_flows",
                    ],
                },
                "port": {"type": "integer", "default": 8080},
                "output_file": {"type": "string"},
                "format": {
                    "type": "string",
                    "enum": ["har", "json"],
                    "default": "har",
                },
                "filter_domain": {"type": "string"},
                "filter_path": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
                "ssl_insecure": {"type": "boolean", "default": False},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        dispatch = {
            "start":          self._start,
            "stop":           self._stop,
            "status":         self._status,
            "export":         self._export,
            "clear":          self._clear,
            "filter_miniapp": self._filter_miniapp,
            "list_flows":     self._list_flows,
        }
        handler = dispatch.get(action)
        if not handler:
            return ToolResult(success=False, error=f"未知操作: {action}")
        return await handler(kwargs)
```

**与 CharlesProxyTool 的关系:** ProxyServerTool 是 CharlesProxyTool 的内置替代。两者可共存，通过 `ToolsConfig` 选择启用哪个。

### 3.2 ProxyServer — 代理服务器核心

基于 mitmproxy 的 `asyncio` master 运行，作为 addon 管线宿主。

```python
@dataclass
class ProxyServerConfig:
    """代理服务器配置"""
    host: str = "127.0.0.1"
    port: int = 8080
    ssl_insecure: bool = False          # 是否跳过上游证书验证
    ca_dir: Path = Path("~/.xiaotie/certs").expanduser()
    max_flows: int = 5000               # 内存环形缓冲最大条目
    auto_filter_miniapp: bool = True    # 自动标记小程序流量
    upstream_proxy: Optional[str] = None  # 上游代理 (链式代理)

class ProxyServer:
    """内置代理服务器"""

    def __init__(self, config: ProxyServerConfig, event_broker: EventBroker):
        self.config = config
        self.event_broker = event_broker
        self._master: Optional[DumpMaster] = None
        self._task: Optional[asyncio.Task] = None
        self.cert_manager = CertManager(config.ca_dir)
        self.flow_storage = FlowStorage(max_size=config.max_flows)
        self.miniapp_detector = MiniAppDetector()

    async def start(self) -> None:
        """在后台 asyncio.Task 中启动 mitmproxy"""
        self.cert_manager.ensure_ca()
        opts = options.Options(
            listen_host=self.config.host,
            listen_port=self.config.port,
            ssl_insecure=self.config.ssl_insecure,
            confdir=str(self.config.ca_dir),
        )
        if self.config.upstream_proxy:
            opts.update(mode=[f"upstream:{self.config.upstream_proxy}"])

        self._master = DumpMaster(opts)
        self._master.addons.add(
            FlowCaptureAddon(self.flow_storage, self.miniapp_detector, self.event_broker)
        )
        self._task = asyncio.create_task(self._run_master())

    async def _run_master(self):
        try:
            await self._master.run()
        except asyncio.CancelledError:
            self._master.shutdown()

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
            self._master = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()
```

**关键设计决策:**
- mitmproxy 运行在同一个 asyncio 事件循环中，不需要额外线程/进程
- 通过 `asyncio.Task` 管理生命周期，`stop()` 时 cancel 即可
- addon 管线是 mitmproxy 的标准扩展点，零侵入

### 3.3 CertManager — 证书管理

```python
class CertManager:
    """CA 根证书与域名证书管理"""

    DEFAULT_CA_DIR = Path("~/.xiaotie/certs").expanduser()
    CA_CERT_FILE = "mitmproxy-ca-cert.pem"
    CA_KEY_FILE = "mitmproxy-ca.pem"

    def __init__(self, ca_dir: Path = DEFAULT_CA_DIR):
        self.ca_dir = ca_dir

    def ensure_ca(self) -> Path:
        """确保 CA 根证书存在，不存在则自动生成"""
        ca_cert = self.ca_dir / self.CA_CERT_FILE
        if ca_cert.exists():
            return ca_cert
        # mitmproxy 首次启动时自动在 confdir 生成 CA
        # 我们只需确保目录存在
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        return ca_cert

    def get_ca_cert_path(self) -> Path:
        """获取 CA 证书路径（供用户安装到设备）"""
        return self.ca_dir / self.CA_CERT_FILE

    def get_install_instructions(self) -> str:
        """生成证书安装说明"""
        cert_path = self.get_ca_cert_path()
        return (
            f"HTTPS 抓包需要安装 CA 根证书:\n"
            f"证书路径: {cert_path}\n\n"
            f"iOS: 通过 AirDrop/邮件 发送 .pem 文件到设备，"
            f"设置 → 通用 → VPN与设备管理 → 安装，"
            f"然后 设置 → 通用 → 关于本机 → 证书信任设置 → 启用\n\n"
            f"Android: 设置 → 安全 → 加密与凭据 → 安装证书\n\n"
            f"macOS: 双击 .pem 文件添加到钥匙串，标记为始终信任\n\n"
            f"微信开发者工具: 设置 → 代理设置 → 手动设置代理 127.0.0.1:{self.ca_dir.parent}"
        )
```

**证书策略:**
- 复用 mitmproxy 的 CA 生成机制（基于 cryptography 库）
- CA 证书持久化到 `~/.xiaotie/certs/`，跨会话复用
- 域名证书由 mitmproxy 运行时动态签发，无需手动管理
- 提供 `get_install_instructions()` 生成设备安装指引

### 3.4 FlowCaptureAddon — 流量捕获 (mitmproxy addon)

```python
class FlowCaptureAddon:
    """mitmproxy addon: 捕获流量并存入 FlowStorage"""

    def __init__(
        self,
        storage: FlowStorage,
        detector: MiniAppDetector,
        event_broker: EventBroker,
    ):
        self.storage = storage
        self.detector = detector
        self.event_broker = event_broker

    def request(self, flow: http.HTTPFlow) -> None:
        """请求阶段: 标记小程序流量"""
        if self.detector.is_miniapp_flow(flow):
            flow.metadata["miniapp"] = True
            flow.metadata["miniapp_type"] = self.detector.classify(flow)

    def response(self, flow: http.HTTPFlow) -> None:
        """响应阶段: 存储完整流量"""
        entry = FlowEntry.from_mitmproxy_flow(flow)
        self.storage.append(entry)

        # 发布事件到 EventBroker
        self.event_broker.publish_sync(Event(
            type=EventType.TOOL_PROGRESS,
            data={
                "tool": "proxy_server",
                "event": "flow_captured",
                "url": flow.request.pretty_url,
                "method": flow.request.method,
                "status": flow.response.status_code if flow.response else 0,
                "is_miniapp": flow.metadata.get("miniapp", False),
                "miniapp_type": flow.metadata.get("miniapp_type", ""),
                "size": len(flow.response.content) if flow.response else 0,
            },
        ))

    def error(self, flow: http.HTTPFlow) -> None:
        """错误阶段: 记录失败的请求"""
        entry = FlowEntry.from_mitmproxy_flow(flow, error=str(flow.error))
        self.storage.append(entry)
```

### 3.5 FlowStorage — 流量存储

```python
@dataclass
class FlowEntry:
    """单条流量记录"""
    id: str                          # UUID
    timestamp: float                 # Unix timestamp
    method: str                      # HTTP method
    url: str                         # 完整 URL
    host: str                        # 域名
    path: str                        # 路径
    request_headers: dict            # 请求头
    request_body: Optional[bytes]    # 请求体
    status_code: int                 # 响应状态码
    response_headers: dict           # 响应头
    response_body: Optional[bytes]   # 响应体
    response_size: int               # 响应大小
    duration_ms: float               # 耗时 (ms)
    is_miniapp: bool = False         # 是否小程序流量
    miniapp_type: str = ""           # 小程序流量类型
    error: Optional[str] = None      # 错误信息
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_mitmproxy_flow(cls, flow: http.HTTPFlow, error: str = None) -> "FlowEntry":
        """从 mitmproxy flow 对象构建"""
        req = flow.request
        resp = flow.response
        return cls(
            id=flow.id,
            timestamp=flow.timestamp_start or time.time(),
            method=req.method,
            url=req.pretty_url,
            host=req.host,
            path=req.path,
            request_headers=dict(req.headers),
            request_body=req.content,
            status_code=resp.status_code if resp else 0,
            response_headers=dict(resp.headers) if resp else {},
            response_body=resp.content if resp else None,
            response_size=len(resp.content) if resp and resp.content else 0,
            duration_ms=(flow.timestamp_end - flow.timestamp_start) * 1000
                        if flow.timestamp_end and flow.timestamp_start else 0,
            is_miniapp=flow.metadata.get("miniapp", False),
            miniapp_type=flow.metadata.get("miniapp_type", ""),
            error=error,
        )


class FlowStorage:
    """环形缓冲流量存储"""

    def __init__(self, max_size: int = 5000):
        self._buffer: deque[FlowEntry] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._stats = {
            "total_captured": 0,
            "miniapp_count": 0,
            "error_count": 0,
            "total_bytes": 0,
        }

    def append(self, entry: FlowEntry) -> None:
        """追加流量记录（线程安全，deque 自动淘汰旧条目）"""
        self._buffer.append(entry)
        self._stats["total_captured"] += 1
        self._stats["total_bytes"] += entry.response_size
        if entry.is_miniapp:
            self._stats["miniapp_count"] += 1
        if entry.error:
            self._stats["error_count"] += 1

    def query(
        self,
        domain: Optional[str] = None,
        path_prefix: Optional[str] = None,
        miniapp_only: bool = False,
        limit: int = 100,
    ) -> list[FlowEntry]:
        """查询流量记录"""
        results = []
        for entry in reversed(self._buffer):  # 最新的在前
            if domain and domain not in entry.host:
                continue
            if path_prefix and not entry.path.startswith(path_prefix):
                continue
            if miniapp_only and not entry.is_miniapp:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def clear(self) -> int:
        """清空缓冲，返回清除的条目数"""
        count = len(self._buffer)
        self._buffer.clear()
        return count

    def get_stats(self) -> dict:
        return {**self._stats, "buffer_size": len(self._buffer)}

    def export_har(self, entries: Optional[list[FlowEntry]] = None) -> dict:
        """导出为 HAR 1.2 格式"""
        if entries is None:
            entries = list(self._buffer)
        return {
            "log": {
                "version": "1.2",
                "creator": {"name": "xiaotie-proxy", "version": "0.1.0"},
                "entries": [self._entry_to_har(e) for e in entries],
            }
        }

    @staticmethod
    def _entry_to_har(entry: FlowEntry) -> dict:
        """FlowEntry → HAR entry"""
        return {
            "startedDateTime": datetime.fromtimestamp(
                entry.timestamp
            ).isoformat() + "Z",
            "time": entry.duration_ms,
            "request": {
                "method": entry.method,
                "url": entry.url,
                "headers": [
                    {"name": k, "value": v}
                    for k, v in entry.request_headers.items()
                ],
                "bodySize": len(entry.request_body) if entry.request_body else 0,
            },
            "response": {
                "status": entry.status_code,
                "headers": [
                    {"name": k, "value": v}
                    for k, v in entry.response_headers.items()
                ],
                "content": {
                    "size": entry.response_size,
                    "mimeType": entry.response_headers.get(
                        "content-type", "application/octet-stream"
                    ),
                },
                "bodySize": entry.response_size,
            },
            "timings": {"send": 0, "wait": entry.duration_ms, "receive": 0},
            "_miniapp": entry.is_miniapp,
            "_miniapp_type": entry.miniapp_type,
        }
```

### 3.6 MiniAppDetector — 小程序流量识别

```python
class MiniAppDetector:
    """微信小程序流量智能识别"""

    # 域名规则
    WECHAT_DOMAINS = {
        "servicewechat.com",       # 小程序服务域名
        "weixin.qq.com",           # 微信 API
        "wx.qq.com",               # 微信网页版
        "wxaapi.weixin.qq.com",    # 小程序 API
        "weixinbridge.com",        # 微信桥接
        "qlogo.cn",               # 头像 CDN
        "mmbiz.qpic.cn",          # 公众号图片
        "res.wx.qq.com",          # 微信资源
        "mp.weixin.qq.com",       # 公众平台
    }

    # 小程序特征 User-Agent 模式
    MINIAPP_UA_PATTERNS = [
        "MicroMessenger",          # 微信内置浏览器
        "miniProgram",             # 小程序标识
        "wechatdevtools",          # 开发者工具
    ]

    # 小程序特征路径
    MINIAPP_PATH_PATTERNS = [
        "/cgi-bin/",               # 微信 CGI 接口
        "/sns/",                   # 社交接口
        "/wxaapi/",                # 小程序 API
        "/wxa-dev-logic/",         # 开发逻辑
        "/__dev/",                 # 开发调试
        "/appservice/",            # 应用服务
    ]

    # 流量分类
    FLOW_TYPES = {
        "api":      "API 接口调用",
        "static":   "静态资源加载",
        "auth":     "认证授权",
        "payment":  "支付相关",
        "media":    "媒体资源",
        "analytics":"数据上报",
        "unknown":  "未分类",
    }

    def is_miniapp_flow(self, flow: http.HTTPFlow) -> bool:
        """判断是否为小程序相关流量"""
        host = flow.request.host
        # 域名匹配
        if any(d in host for d in self.WECHAT_DOMAINS):
            return True
        # UA 匹配
        ua = flow.request.headers.get("User-Agent", "")
        if any(p in ua for p in self.MINIAPP_UA_PATTERNS):
            return True
        # Referer 匹配
        referer = flow.request.headers.get("Referer", "")
        if "servicewechat.com" in referer:
            return True
        return False

    def classify(self, flow: http.HTTPFlow) -> str:
        """分类小程序流量类型"""
        path = flow.request.path.lower()
        content_type = (
            flow.response.headers.get("content-type", "")
            if flow.response else ""
        )

        if any(p in path for p in ["/cgi-bin/", "/wxaapi/", "/api/"]):
            return "api"
        if any(p in path for p in ["/login", "/auth", "/token", "/oauth"]):
            return "auth"
        if any(p in path for p in ["/pay/", "/wxpay/", "/payment"]):
            return "payment"
        if any(ext in path for ext in [".js", ".css", ".html", ".wasm"]):
            return "static"
        if any(t in content_type for t in ["image/", "video/", "audio/"]):
            return "media"
        if any(p in path for p in ["/report", "/analytics", "/stat", "/log"]):
            return "analytics"
        return "unknown"
```

## 4. 事件集成

代理服务器通过 xiaotie 的 `EventBroker` 发布以下事件:

| 事件 | EventType | data 字段 | 触发时机 |
|------|-----------|-----------|----------|
| 流量捕获 | `TOOL_PROGRESS` | `{tool, event, url, method, status, is_miniapp, ...}` | 每个响应完成 |
| 代理启动 | `TOOL_START` | `{tool, port, host}` | `start` 操作 |
| 代理停止 | `TOOL_COMPLETE` | `{tool, stats}` | `stop` 操作 |
| 代理错误 | `TOOL_ERROR` | `{tool, error}` | 异常发生 |

**TUI 集成示例:**

```python
# 在 TUI 中订阅代理事件，实时显示流量
queue = await event_broker.subscribe([EventType.TOOL_PROGRESS])
while True:
    event = await queue.get()
    if event.data.get("tool") == "proxy_server":
        display_flow(event.data)
```

## 5. 配置设计

### 5.1 ToolsConfig 扩展

```python
@dataclass
class ToolsConfig:
    """工具配置 (扩展)"""
    # ... 现有字段 ...
    enable_charles: bool = False
    enable_proxy_server: bool = False       # 新增: 内置代理
    proxy_server_host: str = "127.0.0.1"
    proxy_server_port: int = 8080
    proxy_server_ssl_insecure: bool = False
    proxy_server_ca_dir: str = "~/.xiaotie/certs"
    proxy_server_max_flows: int = 5000
    proxy_server_auto_miniapp: bool = True
    proxy_server_upstream: Optional[str] = None
```

### 5.2 YAML 配置示例

```yaml
# ~/.xiaotie/config.yaml
tools:
  enable_proxy_server: true
  proxy_server_port: 8080
  proxy_server_ssl_insecure: false
  proxy_server_ca_dir: "~/.xiaotie/certs"
  proxy_server_max_flows: 5000
  proxy_server_auto_miniapp: true
```

### 5.3 pyproject.toml 依赖

```toml
[project.optional-dependencies]
proxy = [
    "mitmproxy>=10.0",
]
all = [
    "xiaotie[tui]",
    "xiaotie[search]",
    "xiaotie[proxy]",   # 新增
    "xiaotie[docs]",
]
```

## 6. 文件结构

```
xiaotie/
├── tools/
│   ├── proxy/                    # 新增: 代理模块
│   │   ├── __init__.py
│   │   ├── server.py             # ProxyServer 核心
│   │   ├── cert_manager.py       # CertManager 证书管理
│   │   ├── flow_capture.py       # FlowCaptureAddon
│   │   ├── flow_storage.py       # FlowStorage + FlowEntry
│   │   ├── miniapp_detector.py   # MiniAppDetector
│   │   ├── har_exporter.py       # HAR 导出逻辑
│   │   └── config.py             # ProxyServerConfig
│   ├── proxy_tool.py             # ProxyServerTool (Agent 接口)
│   ├── charles_tool.py           # 保留，向后兼容
│   └── ...
├── config.py                     # 扩展 ToolsConfig
└── events.py                     # 复用现有事件系统
```

## 7. 与 xiaotie 异步架构的集成

### 7.1 生命周期管理

```
Agent.start()
  └─► ProxyServerTool._start()
        └─► ProxyServer.start()
              ├─► CertManager.ensure_ca()
              ├─► mitmproxy DumpMaster(opts)
              ├─► master.addons.add(FlowCaptureAddon)
              └─► asyncio.create_task(master.run())
                    ↓ (后台运行，不阻塞 Agent 主循环)

Agent 主循环继续处理用户请求...

Agent.stop() / ProxyServerTool._stop()
  └─► ProxyServer.stop()
        ├─► task.cancel()
        └─► master.shutdown()
```

### 7.2 并发安全

- `FlowStorage` 使用 `collections.deque(maxlen=N)`，线程安全的追加/弹出
- `FlowCaptureAddon` 的回调在 mitmproxy 的事件循环中执行，与 xiaotie 共享同一个 asyncio loop
- `EventBroker.publish_sync()` 用于 addon 回调中的同步发布（mitmproxy addon 回调是同步的）
- 查询操作 (`query`, `export_har`) 对 deque 做快照遍历，不需要加锁

### 7.3 资源清理

```python
class ProxyServerTool(Tool):
    async def _start(self, kwargs: dict) -> ToolResult:
        # ...启动逻辑...
        # 注册 atexit 清理，防止进程泄漏
        import atexit
        atexit.register(lambda: asyncio.run(self.server.stop()))
        return ToolResult(success=True, content="...")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        if self.server and self.server.is_running:
            await self.server.stop()
```

## 8. 使用示例

### 8.1 Agent 对话式使用

```python
from xiaotie import create_agent
from xiaotie.tools.proxy_tool import ProxyServerTool

agent = create_agent(
    provider="anthropic",
    tools=[ProxyServerTool()]
)

await agent.run("启动代理服务器，端口 8080")
await agent.run("代理状态如何？")
await agent.run("列出最近捕获的小程序请求")
await agent.run("导出所有流量到 capture.har")
await agent.run("停止代理")
```

### 8.2 编程式使用

```python
from xiaotie.tools.proxy.server import ProxyServer, ProxyServerConfig
from xiaotie.events import get_event_broker

config = ProxyServerConfig(port=8080)
server = ProxyServer(config, get_event_broker())

await server.start()
# ... 等待流量 ...
flows = server.flow_storage.query(miniapp_only=True)
har = server.flow_storage.export_har(flows)
await server.stop()
```

## 9. 迁移路径 (CharlesProxyTool → ProxyServerTool)

| 维度 | CharlesProxyTool | ProxyServerTool |
|------|-----------------|-----------------|
| 外部依赖 | 需要安装 Charles ($50) | 仅需 `pip install xiaotie[proxy]` |
| 启动方式 | subprocess 启动 GUI 应用 | 进程内 asyncio Task |
| 证书管理 | 依赖 Charles GUI | 自动生成，提供安装指引 |
| 数据导出 | AppleScript 模拟操作 | 内存直接导出 HAR/JSON |
| 小程序识别 | 域名匹配 | 域名 + UA + Referer + 路径 多维识别 |
| 平台支持 | macOS 最佳 | 全平台一致 |
| 事件集成 | 无 | 完整 EventBroker 集成 |
| 实时性 | 需要手动导出 | 实时流量推送 |

**兼容策略:** CharlesProxyTool 保留不删除，用户可通过配置选择。新项目推荐使用 ProxyServerTool。

## 10. 安全考虑

1. **CA 证书安全**: CA 私钥存储在 `~/.xiaotie/certs/`，权限设为 `0600`
2. **仅本地监听**: 默认绑定 `127.0.0.1`，不暴露到网络
3. **敏感数据**: 响应体存储在内存中，`stop()` 时自动清空；导出文件由用户自行管理
4. **上游验证**: `ssl_insecure` 默认 `False`，不跳过上游证书验证
5. **环形缓冲**: `max_flows` 限制内存占用，防止 OOM

## 11. 实施计划

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | ProxyServer + CertManager + FlowStorage 核心 | 核心功能 |
| Phase 2 | MiniAppDetector + FlowCaptureAddon | 流量识别 |
| Phase 3 | ProxyServerTool + 配置集成 | Agent 接口 |
| Phase 4 | HAR 导出 + 事件集成 | 数据输出 |
| Phase 5 | 测试 + 文档 | 质量保证 |
