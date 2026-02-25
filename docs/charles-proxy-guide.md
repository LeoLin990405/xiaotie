# Charles 代理抓包工具使用指南

## 功能说明

Charles 代理抓包工具已集成到小铁（xiaotie）agent 中，可以用于自动抓取小程序的网络请求。
支持启动/停止 Charles 代理、配置代理端口、导出抓包数据、过滤特定域名请求等功能。

## 快速开始

### 安装前提

- 已安装 [Charles Proxy](https://www.charlesproxy.com/)（自动检测安装路径）
- Python 3.10+
- xiaotie 已安装：`pip install -e .`
- 平台支持：
  - macOS: 完整支持（系统代理自动配置 + AppleScript 自动导出）
  - Linux: 支持启动/停止，自动设置环境变量代理
  - Windows: 支持启动/停止，Charles 自行管理代理注册

### 30 秒上手

```python
import asyncio
from xiaotie.tools import CharlesProxyTool

async def main():
    tool = CharlesProxyTool()
    # 启动代理
    result = await tool.execute(action="start", port=8888)
    print(result.content)
    # 查看状态
    result = await tool.execute(action="status")
    print(result.content)
    # 停止代理
    result = await tool.execute(action="stop")
    print(result.content)

asyncio.run(main())
```

## 使用方法

### 1. 启动 Charles 代理

```python
from xiaotie import create_agent
from xiaotie.tools import CharlesProxyTool

# 方式一：通过 Agent 使用
agent = create_agent(
    provider="anthropic",
    tools=[CharlesProxyTool()]
)
result = await agent.run("启动 Charles 代理，端口 8888")

# 方式二：直接使用工具
tool = CharlesProxyTool()
result = await tool.execute(action="start", port=8888)
print(result.content)
```

### 2. 配置小程序设备代理

启动 Charles 后，需要在小程序设备（手机/模拟器）上配置代理：

**iOS 设备：**
1. 设置 -> Wi-Fi -> 点击已连接的网络
2. 配置代理 -> 手动
3. 服务器：你的电脑 IP（如 192.168.1.100）
4. 端口：8888

**Android 设备：**
1. 设置 -> WLAN -> 长按已连接的网络
2. 修改网络 -> 高级选项
3. 代理：手动
4. 主机名：你的电脑 IP
5. 端口：8888

**微信开发者工具：**
1. 设置 -> 代理设置
2. 手动设置代理
3. 代理服务器：127.0.0.1:8888

### 3. 安装 Charles 证书（HTTPS 抓包）

为了抓取 HTTPS 请求，需要安装 Charles 的 SSL 证书：

1. 在 Charles 中：Help -> SSL Proxying -> Install Charles Root Certificate on a Mobile Device
2. 按照提示在设备上访问 chls.pro/ssl 下载证书
3. 安装证书并信任

### 4. 开始抓包

配置完成后，在小程序中进行操作，Charles 会自动抓取所有网络请求。

### 5. 查看状态

```python
result = await tool.execute(action="status")
print(result.content)
# 输出示例：
# Charles 代理状态:
# - 运行状态: 运行中
# - 代理端口: 8888
# - 进程 ID: 12345
```

### 6. 导出抓包数据

```python
result = await tool.execute(
    action="export",
    output_file="miniapp_requests.json"
)
print(result.content)
```

### 7. 停止代理

```python
result = await tool.execute(action="stop")
print(result.content)
```

## 实际使用场景

### 场景一：小程序 API 接口分析

抓取小程序的 API 请求，分析接口结构和数据格式：

```python
import asyncio
import json
from xiaotie.tools import CharlesProxyTool

async def analyze_miniapp_api():
    tool = CharlesProxyTool()

    # 启动代理，过滤目标域名
    await tool.execute(
        action="start",
        port=8888,
        filter_domain="api.example.com"
    )

    print("请在小程序中操作，完成后按回车...")
    input()

    # 导出数据用于分析
    await tool.execute(
        action="export",
        output_file="api_analysis.json"
    )

    # 停止代理
    await tool.execute(action="stop")

asyncio.run(analyze_miniapp_api())
```

### 场景二：性能监控

监控小程序网络请求的响应时间，发现慢接口：

```python
async def monitor_performance():
    tool = CharlesProxyTool()
    await tool.execute(action="start", port=8888)

    # 持续监控
    print("性能监控已启动，按 Ctrl+C 停止...")
    try:
        while True:
            status = await tool.execute(action="status")
            print(status.content)
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        await tool.execute(action="stop")
        print("监控已停止")
```

### 场景三：与 Agent 对话式使用

```python
from xiaotie import create_agent
from xiaotie.tools import CharlesProxyTool

agent = create_agent(
    provider="anthropic",
    tools=[CharlesProxyTool()]
)

# 自然语言控制
await agent.run("帮我启动 Charles 代理，用 8888 端口")
await agent.run("Charles 现在运行状态如何？")
await agent.run("把抓到的数据导出到 wechat_miniapp.json")
await agent.run("停止 Charles 代理")
```

### 场景四：批量抓包与自动化

```python
async def batch_capture(domains: list[str]):
    """批量抓取多个域名的请求"""
    tool = CharlesProxyTool()

    for domain in domains:
        print(f"\n--- 抓取 {domain} ---")
        await tool.execute(
            action="start",
            port=8888,
            filter_domain=domain
        )

        # 等待抓取
        await asyncio.sleep(30)

        # 导出
        await tool.execute(
            action="export",
            output_file=f"capture_{domain.replace('.', '_')}.json"
        )

        await tool.execute(action="stop")
        await asyncio.sleep(2)  # 等待端口释放

# 使用
asyncio.run(batch_capture([
    "api.weixin.qq.com",
    "api.example.com",
    "cdn.example.com"
]))
```

## 高级用法

### 过滤特定域名

```python
result = await tool.execute(
    action="start",
    port=8888,
    filter_domain="api.weixin.qq.com"
)
```

### 自定义端口

```python
# 使用非默认端口，避免与其他代理冲突
result = await tool.execute(action="start", port=9090)
```

### 在 Agent 工作流中集成

```python
from xiaotie import create_agent
from xiaotie.tools import CharlesProxyTool, BashTool, WriteTool

# 组合多个工具
agent = create_agent(
    provider="anthropic",
    tools=[
        CharlesProxyTool(),
        BashTool(),
        WriteTool()
    ]
)

# Agent 可以自动完成：启动抓包 -> 分析数据 -> 生成报告
await agent.run(
    "启动 Charles 抓包，等待 30 秒后导出数据，"
    "然后分析 API 接口并生成报告"
)
```

## API 参考

### CharlesProxyTool

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称，固定为 `"charles_proxy"` |
| `description` | `str` | 工具描述 |
| `parameters` | `dict` | JSON Schema 参数定义 |

### execute() 方法

```python
async def execute(
    action: str,           # 必填，操作类型
    port: int = 8888,      # 代理端口
    filter_domain: str = None,  # 过滤域名
    output_file: str = None     # 导出文件路径
) -> ToolResult
```

**action 取值：**

| 值 | 说明 | 必要参数 |
|----|------|----------|
| `"start"` | 启动 Charles 代理 | `port`（可选） |
| `"stop"` | 停止 Charles 代理 | 无 |
| `"export"` | 导出抓包数据 | `output_file`（可选） |
| `"status"` | 查看运行状态 | 无 |

### ToolResult 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 操作是否成功 |
| `content` | `str` | 操作结果描述 |
| `error` | `str \| None` | 错误信息（失败时） |
| `data` | `dict \| None` | 结构化数据（status 操作返回） |

## 常见问题解答（FAQ）

### Q: Charles 需要单独安装吗？

A: 是的。CharlesProxyTool 是 Charles Proxy 的自动化封装，需要先安装 Charles 应用。
下载地址：https://www.charlesproxy.com/download/

### Q: 支持 Windows/Linux 吗？

A: 支持。工具会自动检测平台并适配：
- macOS: 通过 `networksetup` 自动配置系统代理
- Linux: 自动设置 `http_proxy`/`https_proxy` 环境变量
- Windows: Charles 自行管理代理注册，无需额外配置

Charles 可执行文件路径也会自动检测，或通过构造函数手动指定：
```python
tool = CharlesProxyTool(charles_path="/custom/path/to/charles")
```

### Q: 可以同时运行多个 Charles 实例吗？

A: 不建议。每个 CharlesProxyTool 实例管理一个 Charles 进程，
多实例可能导致端口冲突。如需多端口，请使用不同端口号依次启动。

### Q: 抓包数据保存在哪里？

A: 导出操作会提示你在 Charles GUI 中手动导出，或使用 Charles CLI。
默认文件名格式为 `charles_session_{timestamp}.json`。

### Q: 如何抓取 HTTPS 请求？

A: 需要在设备上安装并信任 Charles 的 SSL 根证书。
详见上方"安装 Charles 证书"章节。

### Q: 代理启动后小程序无法联网怎么办？

A: 请检查：
1. 设备和电脑是否在同一局域网
2. 代理 IP 和端口是否配置正确
3. Charles 是否正常运行（查看 status）
4. 防火墙是否放行了代理端口

### Q: 如何只抓取特定接口的请求？

A: 使用 `filter_domain` 参数：
```python
await tool.execute(action="start", port=8888, filter_domain="api.example.com")
```

## 故障排除

### 问题：Charles 启动失败

**可能原因：**
- Charles 未安装或路径不正确
- 端口被占用

**解决方案：**
1. 确认 Charles 已安装在 `/Applications/Charles.app`
2. 检查端口占用：`lsof -i :8888`
3. 如端口被占用，使用其他端口：`await tool.execute(action="start", port=9090)`

### 问题：设备无法连接代理

**可能原因：**
- 设备和电脑不在同一网络
- 防火墙阻止了连接
- 代理配置错误

**解决方案：**
1. 确认设备和电脑连接同一 Wi-Fi
2. 检查 macOS 防火墙设置：系统偏好设置 -> 安全性与隐私 -> 防火墙
3. 确认代理 IP 使用电脑的局域网 IP（非 127.0.0.1）
4. 在终端运行 `ifconfig | grep "inet "` 查看本机 IP

### 问题：无法抓取 HTTPS 请求

**可能原因：**
- 未安装 Charles SSL 证书
- 证书未被信任
- SSL Proxying 未启用

**解决方案：**
1. Charles 菜单：Help -> SSL Proxying -> Install Charles Root Certificate on a Mobile Device
2. 设备访问 `chls.pro/ssl` 安装证书
3. iOS：设置 -> 通用 -> 关于本机 -> 证书信任设置 -> 启用 Charles 证书
4. Charles 菜单：Proxy -> SSL Proxying Settings -> 添加目标域名

### 问题：停止代理后网络异常

**可能原因：**
- 系统代理未正确恢复

**解决方案：**

macOS:
1. 手动关闭系统代理：系统偏好设置 -> 网络 -> 高级 -> 代理 -> 取消所有勾选
2. 或在终端执行：
```bash
networksetup -setwebproxystate Wi-Fi off
networksetup -setsecurewebproxystate Wi-Fi off
```

Linux:
```bash
unset http_proxy https_proxy
```

### 问题：Charles 进程残留

**可能原因：**
- 异常退出导致进程未清理

**解决方案：**
```bash
# 查找 Charles 进程
ps aux | grep Charles
# 强制终止
killall Charles
```

## 最佳实践

### 1. 始终使用 try/finally 确保清理

```python
async def safe_capture():
    tool = CharlesProxyTool()
    try:
        await tool.execute(action="start", port=8888)
        # ... 抓包操作 ...
    finally:
        await tool.execute(action="stop")
```

### 2. 抓包前先检查状态

```python
status = await tool.execute(action="status")
if "运行中" in status.content:
    print("Charles 已在运行，先停止...")
    await tool.execute(action="stop")
await tool.execute(action="start", port=8888)
```

### 3. 使用有意义的导出文件名

```python
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"capture_{timestamp}_wechat.json"
await tool.execute(action="export", output_file=filename)
```

### 4. 避免长时间运行代理

长时间运行代理会影响系统网络性能。建议：
- 明确抓包目标，完成后立即停止
- 使用 `filter_domain` 减少无关流量
- 设置超时自动停止

### 5. 生产环境注意事项

- 不要在生产服务器上运行抓包工具
- 抓包数据可能包含敏感信息，注意数据安全
- 导出的 JSON 文件应妥善保管，不要提交到版本控制

## 相关资源

- [Charles 官方文档](https://www.charlesproxy.com/documentation/)
- [Charles SSL 证书安装指南](https://www.charlesproxy.com/documentation/using-charles/ssl-certificates/)
- [微信小程序抓包教程](https://developers.weixin.qq.com/miniprogram/dev/devtools/debug.html)
- [xiaotie 工具系统文档](./api/skills.md)
