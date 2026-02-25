# 内置代理服务器使用指南

## 概述

小铁（xiaotie）v1.2.0 新增内置 HTTP/HTTPS 代理服务器，无需安装 Charles 等外部工具即可完成小程序网络请求抓包。基于 Python 异步实现，支持 HTTPS 中间人解密、请求过滤、实时流式输出和自动化分析。

### 与 Charles 方案的区别

| 特性 | 内置代理 (ProxyServerTool) | Charles (CharlesProxyTool) |
|------|--------------------------|---------------------------|
| 安装依赖 | 无，随 xiaotie 安装 | 需单独安装 Charles 应用 |
| 费用 | 免费 | Charles 需付费授权 |
| 自动化程度 | 完全 API 驱动 | 依赖 AppleScript / GUI |
| HTTPS 解密 | 内置 CA 自动生成 | 需手动配置 SSL Proxying |
| 数据格式 | JSON / HAR，实时可用 | 需手动导出 |
| Agent 集成 | 原生工具，零配置 | 需启动外部进程 |
| 平台支持 | macOS / Linux / Windows | 同左 |

## 快速开始

### 安装

内置代理随 xiaotie 一起安装，无需额外依赖：

```bash
pip install -e .
```

### 30 秒上手

```python
import asyncio
from xiaotie.tools import ProxyServerTool

async def main():
    proxy = ProxyServerTool()

    # 启动代理
    result = await proxy.execute(action="start", port=8080)
    print(result.content)

    # 查看状态
    result = await proxy.execute(action="status")
    print(result.content)

    # 导出抓包数据
    result = await proxy.execute(action="export", output_file="capture.json")
    print(result.content)

    # 停止代理
    result = await proxy.execute(action="stop")
    print(result.content)

asyncio.run(main())
```

## 功能详解

### 1. 启动代理

```python
from xiaotie.tools import ProxyServerTool

proxy = ProxyServerTool()

# 基础启动
result = await proxy.execute(action="start", port=8080)

# 指定监听地址（默认 127.0.0.1）
result = await proxy.execute(action="start", port=8080, host="0.0.0.0")

# 启用 HTTPS 解密
result = await proxy.execute(action="start", port=8080, ssl_decrypt=True)
```

启动后，代理服务器在指定端口监听 HTTP/HTTPS 请求。系统代理会自动配置（macOS 通过 `networksetup`，Linux 通过环境变量）。

### 2. 配置设备代理

启动代理后，需要在目标设备上配置代理指向小铁所在机器：

**iOS 设备：**
1. 设置 -> Wi-Fi -> 点击已连接的网络
2. 配置代理 -> 手动
3. 服务器：电脑 IP（如 192.168.1.100）
4. 端口：8080

**Android 设备：**
1. 设置 -> WLAN -> 长按已连接的网络
2. 修改网络 -> 高级选项 -> 代理：手动
3. 主机名：电脑 IP
4. 端口：8080

**微信开发者工具：**
1. 设置 -> 代理设置 -> 手动设置代理
2. 代理服务器：`127.0.0.1:8080`

### 3. HTTPS 证书安装

启用 HTTPS 解密时，需要在设备上安装并信任内置 CA 证书：

```python
# 导出 CA 证书
result = await proxy.execute(action="export_cert", output_file="xiaotie-ca.pem")
```

**iOS 安装证书：**
1. 通过 AirDrop 或邮件将 `xiaotie-ca.pem` 发送到设备
2. 设置 -> 通用 -> VPN 与设备管理 -> 安装证书
3. 设置 -> 通用 -> 关于本机 -> 证书信任设置 -> 启用 xiaotie CA

**Android 安装证书：**
1. 将 `xiaotie-ca.pem` 复制到设备
2. 设置 -> 安全 -> 加密与凭据 -> 安装证书

**macOS / Windows：**
```bash
# macOS：添加到系统钥匙串
security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain xiaotie-ca.pem

# Windows：双击 .pem 文件 -> 安装证书 -> 受信任的根证书颁发机构
```

### 4. 小程序抓包

配置完成后，在小程序中操作即可自动抓取请求：

```python
# 启动代理并过滤微信小程序域名
result = await proxy.execute(
    action="start",
    port=8080,
    ssl_decrypt=True,
    filter_domain="servicewechat.com"
)

# 等待用户操作小程序...

# 查看实时捕获的请求
result = await proxy.execute(action="list_requests")
print(result.content)
```

### 5. 导出数据

```python
# 导出为 JSON
result = await proxy.execute(
    action="export",
    output_file="miniapp_capture.json",
    format="json"
)

# 导出为 HAR（兼容 Chrome DevTools）
result = await proxy.execute(
    action="export",
    output_file="miniapp_capture.har",
    format="har"
)

# 仅导出特定域名的请求
result = await proxy.execute(
    action="export",
    output_file="wechat_api.json",
    filter_domain="api.weixin.qq.com"
)
```

### 6. 分析数据

```python
# 分析捕获的请求，生成统计报告
result = await proxy.execute(action="analyze")
print(result.content)
# 输出：域名分布、HTTP 方法统计、状态码分布、API 端点列表

# 过滤小程序请求
result = await proxy.execute(action="filter_miniapp")
print(result.content)
# 输出：按域名分组的微信小程序相关请求
```

### 7. 停止代理

```python
result = await proxy.execute(action="stop")
# 自动恢复系统代理设置，清理资源
```

## Agent 集成

### 通过 Agent 自然语言控制

```python
from xiaotie import create_agent
from xiaotie.tools import ProxyServerTool

agent = create_agent(
    provider="anthropic",
    tools=[ProxyServerTool()]
)

# 自然语言控制代理
await agent.run("启动内置代理，端口 8080，开启 HTTPS 解密")
await agent.run("查看当前抓包状态")
await agent.run("导出小程序相关的请求到 wechat.json")
await agent.run("分析抓到的 API 接口")
await agent.run("停止代理")
```

### 在工作流中组合使用

```python
from xiaotie import create_agent
from xiaotie.tools import ProxyServerTool, BashTool, WriteTool

agent = create_agent(
    provider="anthropic",
    tools=[ProxyServerTool(), BashTool(), WriteTool()]
)

# Agent 自动完成：启动抓包 -> 等待 -> 导出 -> 分析 -> 生成报告
await agent.run(
    "启动代理抓包 30 秒，然后导出数据，"
    "分析小程序 API 接口并生成 Markdown 报告"
)
```

### AgentBuilder 方式

```python
from xiaotie import AgentBuilder
from xiaotie.tools import ProxyServerTool

agent = (
    AgentBuilder("proxy-analyzer")
    .with_llm("claude-sonnet-4")
    .with_tools([ProxyServerTool()])
    .build()
)

result = await agent.run("抓取小程序请求并分析 API 结构")
```

## API 参考

### ProxyServerTool

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称，固定为 `"proxy_server"` |
| `description` | `str` | 工具描述 |
| `parameters` | `dict` | JSON Schema 参数定义 |

### execute() 方法

```python
async def execute(
    action: str,              # 必填，操作类型
    port: int = 8080,         # 代理端口
    host: str = "127.0.0.1",  # 监听地址
    ssl_decrypt: bool = False, # 是否启用 HTTPS 解密
    filter_domain: str = None, # 过滤域名
    filter_path: str = None,   # 过滤路径前缀
    output_file: str = None,   # 导出文件路径
    format: str = "json",      # 导出格式：json / har
) -> ToolResult
```

**action 取值：**

| 值 | 说明 | 关键参数 |
|----|------|----------|
| `"start"` | 启动代理服务器 | `port`, `host`, `ssl_decrypt` |
| `"stop"` | 停止代理服务器 | 无 |
| `"status"` | 查看运行状态 | 无 |
| `"export"` | 导出抓包数据 | `output_file`, `format`, `filter_domain` |
| `"export_cert"` | 导出 CA 证书 | `output_file` |
| `"analyze"` | 分析捕获的请求 | 无 |
| `"filter_miniapp"` | 过滤小程序请求 | `output_file`（可选） |
| `"list_requests"` | 列出已捕获的请求 | `filter_domain`（可选） |
| `"clear"` | 清空已捕获的请求 | 无 |

### ToolResult 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 操作是否成功 |
| `content` | `str` | 操作结果描述 |
| `error` | `str \| None` | 错误信息（失败时） |

### 配置选项

在 `config/config.yaml` 中可以设置代理默认参数：

```yaml
proxy:
  default_port: 8080
  default_host: "127.0.0.1"
  ssl_decrypt: false
  auto_configure_system_proxy: true
  ca_cert_path: "~/.xiaotie/proxy/ca.pem"
  ca_key_path: "~/.xiaotie/proxy/ca.key"
  max_request_body_size: 10485760  # 10MB
  request_timeout: 30
```

## 故障排查

### 问题：代理启动失败，端口被占用

**解决方案：**
```bash
# 查看端口占用
lsof -i :8080

# 使用其他端口
result = await proxy.execute(action="start", port=9090)
```

### 问题：HTTPS 请求无法解密

**可能原因：**
- 未启用 `ssl_decrypt=True`
- 设备未安装 CA 证书
- 证书未被信任

**解决方案：**
1. 确认启动时开启了 SSL 解密：`ssl_decrypt=True`
2. 导出并安装 CA 证书（见上方"HTTPS 证书安装"章节）
3. 确认证书已在设备上被信任

### 问题：设备无法连接代理

**解决方案：**
1. 确认设备和电脑在同一局域网
2. 使用 `host="0.0.0.0"` 监听所有网络接口
3. 检查防火墙是否放行了代理端口
4. 查看本机 IP：`ifconfig | grep "inet "`

### 问题：停止代理后网络异常

**解决方案：**

macOS:
```bash
networksetup -setwebproxystate Wi-Fi off
networksetup -setsecurewebproxystate Wi-Fi off
```

Linux:
```bash
unset http_proxy https_proxy
```

### 问题：抓包数据为空

**可能原因：**
- 设备代理未正确配置
- `filter_domain` 过滤条件过严

**解决方案：**
1. 先不设置 `filter_domain`，确认能抓到请求
2. 使用 `status` 查看代理是否正常运行
3. 在浏览器中配置代理测试连通性

## 最佳实践

### 1. 使用 try/finally 确保清理

```python
proxy = ProxyServerTool()
try:
    await proxy.execute(action="start", port=8080, ssl_decrypt=True)
    # ... 抓包操作 ...
finally:
    await proxy.execute(action="stop")
```

### 2. 按需开启 HTTPS 解密

HTTPS 解密会增加延迟和 CPU 开销。如果只需要分析 HTTP 请求或只关注请求 URL（不需要看请求体），可以不开启 `ssl_decrypt`。

### 3. 使用域名过滤减少噪音

```python
# 只抓取目标 API
await proxy.execute(
    action="start",
    port=8080,
    filter_domain="api.example.com"
)
```

### 4. 及时导出和清理

长时间运行会积累大量请求数据，占用内存。建议定期导出并清理：

```python
await proxy.execute(action="export", output_file="batch_1.json")
await proxy.execute(action="clear")
```

### 5. 生产环境注意事项

- 不要在生产服务器上运行抓包代理
- 抓包数据可能包含敏感信息（token、密码等），注意数据安全
- 导出文件不要提交到版本控制

## 相关文档

- [Charles 代理工具指南](./charles-proxy-guide.md) - 使用外部 Charles 的方案
- [内置代理 vs Charles 对比](./proxy-vs-charles.md) - 详细功能对比
- [工具系统文档](./tools.md) - 所有工具的 API 参考
