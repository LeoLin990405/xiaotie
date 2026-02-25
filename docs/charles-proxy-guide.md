# Charles 代理抓包工具使用指南

## 功能说明

Charles 代理抓包工具已集成到小铁（xiaotie）agent 中，可以用于自动抓取小程序的网络请求。

## 使用方法

### 1. 启动 Charles 代理

```python
from xiaotie import create_agent
from xiaotie.tools import CharlesProxyTool

# 创建 agent
agent = create_agent(
    provider="anthropic",
    tools=[CharlesProxyTool()]
)

# 启动 Charles 代理
result = await agent.run("启动 Charles 代理，端口 8888")
```

或者直接使用工具：

```python
from xiaotie.tools import CharlesProxyTool

tool = CharlesProxyTool()

# 启动代理
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
# 查看 Charles 状态
result = await tool.execute(action="status")
print(result.content)
```

### 6. 导出抓包数据

```python
# 导出会话数据
result = await tool.execute(
    action="export",
    output_file="miniapp_requests.json"
)
print(result.content)
```

### 7. 停止代理

```python
# 停止 Charles 代理
result = await tool.execute(action="stop")
print(result.content)
```

## 完整示例

```python
import asyncio
from xiaotie import create_agent
from xiaotie.tools import CharlesProxyTool

async def capture_miniapp():
    """抓取小程序网络请求"""

    # 创建 agent
    agent = create_agent(
        provider="anthropic",
        tools=[CharlesProxyTool()]
    )

    # 1. 启动 Charles 代理
    print("启动 Charles 代理...")
    result = await agent.run("启动 Charles 代理")
    print(result)

    # 2. 等待用户配置设备代理并操作小程序
    print("\n请在小程序设备上配置代理：127.0.0.1:8888")
    print("配置完成后，在小程序中进行操作...")
    input("按回车键继续...")

    # 3. 查看状态
    result = await agent.run("查看 Charles 代理状态")
    print(result)

    # 4. 导出数据
    print("\n导出抓包数据...")
    result = await agent.run("导出 Charles 会话数据到 miniapp_capture.json")
    print(result)

    # 5. 停止代理
    print("\n停止 Charles 代理...")
    result = await agent.run("停止 Charles 代理")
    print(result)

if __name__ == "__main__":
    asyncio.run(capture_miniapp())
```

## 高级用法

### 过滤特定域名

```python
# 只抓取特定域名的请求
result = await tool.execute(
    action="start",
    port=8888,
    filter_domain="api.weixin.qq.com"
)
```

### 与 Agent 对话式使用

```python
# 使用自然语言控制
agent = create_agent(
    provider="anthropic",
    tools=[CharlesProxyTool()]
)

# 启动
await agent.run("帮我启动 Charles 代理，用 8888 端口")

# 查询
await agent.run("Charles 现在运行状态如何？")

# 导出
await agent.run("把抓到的数据导出到 wechat_miniapp.json")

# 停止
await agent.run("停止 Charles 代理")
```

## 注意事项

1. **权限要求**：
   - macOS 上配置系统代理需要管理员权限
   - 首次运行可能需要输入密码

2. **证书信任**：
   - HTTPS 抓包需要安装并信任 Charles 证书
   - iOS 设备需要在"设置 -> 通用 -> 关于本机 -> 证书信任设置"中启用证书

3. **网络连接**：
   - 确保设备和电脑在同一网络
   - 防火墙可能需要允许 Charles 端口

4. **数据导出**：
   - Charles 需要手动导出会话数据
   - 或者使用 Charles CLI（如果可用）

## 故障排除

### 问题：设备无法连接代理

**解决方案**：
1. 检查电脑和设备是否在同一网络
2. 检查防火墙设置
3. 确认代理端口正确（默认 8888）

### 问题：无法抓取 HTTPS 请求

**解决方案**：
1. 确认已安装 Charles 证书
2. 确认证书已信任
3. 在 Charles 中启用 SSL Proxying

### 问题：小程序无网络

**解决方案**：
1. 检查代理配置是否正确
2. 尝试关闭代理后重新配置
3. 检查 Charles 是否正常运行

## 相关资源

- [Charles 官方文档](https://www.charlesproxy.com/documentation/)
- [Charles SSL 证书安装指南](https://www.charlesproxy.com/documentation/using-charles/ssl-certificates/)
- [微信小程序抓包教程](https://developers.weixin.qq.com/miniprogram/dev/devtools/debug.html)
