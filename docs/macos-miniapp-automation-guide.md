# macOS 微信小程序自动化指南

小铁（xiaotie）提供 macOS 原生微信小程序自动化能力，支持通过 AppleScript、Accessibility API 和屏幕截图等方式控制微信及小程序，并可结合内置代理抓包分析网络请求。

## 目录

- [环境准备](#环境准备)
- [快速开始](#快速开始)
- [架构概览](#架构概览)
- [配置说明](#配置说明)
- [使用示例](#使用示例)
- [AutomationTool 参考](#automationtool-参考)
- [故障排查](#故障排查)

---

## 环境准备

### 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | macOS 13 (Ventura) 及以上 |
| Python | 3.10+ |
| 微信 | macOS 版微信已安装并登录 |
| 权限 | 辅助功能权限（Accessibility） |

### 安装依赖

```bash
# 基础安装
cd xiaotie
pip install -e .

# 如需 Appium 移动端自动化（可选）
pip install Appium-Python-Client
```

### 授予辅助功能权限

自动化依赖 macOS Accessibility API，需要在系统设置中授权：

1. 打开 **系统设置 > 隐私与安全性 > 辅助功能**
2. 点击 **+** 添加你的终端应用（如 Terminal.app、iTerm2、WezTerm）
3. 如果通过 Python 直接运行，还需添加 Python 解释器路径

> 未授权时 AppleScript 的 `System Events` 调用会失败，表现为 "Not authorized to send Apple events" 错误。

### 验证环境

```bash
# 确认微信已安装
ls /Applications/WeChat.app

# 确认 AppleScript 可用
osascript -e 'tell application "System Events" to get name of every process'

# 确认 xiaotie 安装正常
python -c "from xiaotie.tools.automation_tool import AutomationTool; print('OK')"
```

---

## 快速开始

### 最简示例：启动微信并截图

```python
import asyncio
from xiaotie.tools.automation_tool import AutomationTool

async def main():
    tool = AutomationTool()

    # 启动自动化会话
    result = await tool.execute(action="start")
    print(result.content)

    # 启动微信
    result = await tool.execute(action="launch_app", app_name="WeChat")
    print(result.content)

    # 截取微信窗口截图
    result = await tool.execute(action="screenshot", window_name="WeChat")
    print(result.content)

    # 停止会话
    await tool.execute(action="stop")

asyncio.run(main())
```

### 通过 Agent 自然语言调用

```python
from xiaotie import Agent
from xiaotie.llm import LLMClient
from xiaotie.tools import ReadTool, WriteTool, BashTool
from xiaotie.tools.automation_tool import AutomationTool

async def main():
    llm = LLMClient(
        api_key="your-api-key",
        model="claude-sonnet-4-20250514",
        provider="anthropic",
    )

    tools = [
        ReadTool(workspace_dir="."),
        WriteTool(workspace_dir="."),
        BashTool(),
        AutomationTool(),  # 添加自动化工具
    ]

    agent = Agent(
        llm_client=llm,
        system_prompt="你是小铁，支持 macOS 自动化操作。",
        tools=tools,
    )

    # Agent 会自动调用 AutomationTool
    await agent.run("帮我打开微信，截个图保存到桌面")
```

---

## 架构概览

```
xiaotie/
├── tools/
│   └── automation_tool.py      # AutomationTool - Agent 工具接口
└── automation/
    ├── __init__.py
    ├── appium_driver.py         # Appium 驱动封装（移动端）
    ├── miniapp_automation.py    # 小程序自动化（Appium 方式）
    └── macos/
        ├── __init__.py
        ├── wechat_controller.py # macOS 微信控制器（AppleScript）
        ├── miniapp_controller.py # 小程序页面控制
        └── proxy_integration.py  # 代理抓包集成
```

### 两种自动化方式

| 方式 | 模块 | 适用场景 |
|------|------|----------|
| macOS 原生 | `automation.macos` | macOS 桌面版微信，通过 AppleScript 控制 |
| Appium 移动端 | `automation.appium_driver` | iOS/Android 模拟器中的微信 |

`AutomationTool` 是统一的 Agent 工具入口，封装了 macOS 原生自动化能力。

---

## 配置说明

### WeChatConfig（微信控制器配置）

```python
from xiaotie.automation.macos import WeChatConfig

config = WeChatConfig(
    bundle_id="com.tencent.xinWeChat",  # 微信 Bundle ID
    process_name="WeChat",               # 进程名
    launch_timeout=10,                    # 启动超时（秒）
    action_delay=0.5,                     # 操作间隔（秒）
    screenshot_dir="/tmp/xiaotie_screenshots",  # 截图保存目录
)
```

### MiniAppConfig（小程序配置）

```python
from xiaotie.automation.miniapp_automation import MiniAppConfig

config = MiniAppConfig(
    miniapp_name="目标小程序",    # 小程序名称
    miniapp_id=None,              # 小程序 AppID（可选）
    wait_timeout=30,              # 等待超时（秒）
    proxy_host="127.0.0.1",      # 代理地址
    proxy_port=8888,              # 代理端口
)
```

### Appium 配置（移动端，可选）

```python
from xiaotie.automation.appium_driver import AppiumConfig

# iOS 模拟器
ios_config = AppiumConfig(
    platform="iOS",
    device_name="iPhone 15",
    platform_version="17.0",
    app_package="com.tencent.xin",
    automation_name="XCUITest",
    appium_server="http://localhost:4723",
)

# Android 模拟器
android_config = AppiumConfig(
    platform="Android",
    device_name="emulator-5554",
    platform_version="11",
    app_package="com.tencent.mm",
    app_activity=".ui.LauncherUI",
    automation_name="UiAutomator2",
    appium_server="http://localhost:4723",
)
```

---

## 使用示例

### 示例 1：微信消息发送

```python
from xiaotie.tools.automation_tool import AutomationTool

tool = AutomationTool()

await tool.execute(action="start")
await tool.execute(action="launch_app", app_name="WeChat")
await tool.execute(action="send_message", contact="文件传输助手", message="测试消息")
await tool.execute(action="stop")
```

### 示例 2：执行自定义 AppleScript

```python
# 获取微信窗口位置
result = await tool.execute(
    action="execute",
    script='''
    tell application "System Events"
        tell process "WeChat"
            get position of window 1
        end tell
    end tell
    '''
)
print(result.content)
```

### 示例 3：结合代理抓包分析小程序请求

```python
from xiaotie.tools.automation_tool import AutomationTool
from xiaotie.tools.proxy_tool import ProxyServerTool

proxy = ProxyServerTool()
auto = AutomationTool()

# 1. 启动代理
await proxy.execute(action="start", port=8080, ssl_decrypt=True)

# 2. 启动自动化，打开微信
await auto.execute(action="start")
await auto.execute(action="launch_app", app_name="WeChat")

# 3. 操作小程序（手动或自动化导航到目标小程序）
# ...

# 4. 分析捕获的小程序请求
result = await proxy.execute(action="filter_miniapp")
print(result.content)

# 5. 导出数据
await proxy.execute(action="export", output_file="miniapp_requests.json")

# 6. 清理
await auto.execute(action="stop")
await proxy.execute(action="stop")
```

### 示例 4：Appium 移动端小程序自动化

```python
from xiaotie.automation import MiniAppAutomation
from xiaotie.automation.miniapp_automation import MiniAppConfig
from xiaotie.automation.appium_driver import AppiumConfig

# 使用 Android 模拟器
appium_config = AppiumConfig(
    platform="Android",
    device_name="emulator-5554",
)
miniapp_config = MiniAppConfig(miniapp_name="目标小程序")

async with MiniAppAutomation(appium_config, miniapp_config) as auto:
    # 打开微信并搜索小程序
    await auto.open_miniapp_by_name("目标小程序")

    # 截图
    await auto.screenshot("miniapp_screenshot.png")

    # 提取页面数据
    data = await auto.extract_data({
        "title": "//android.widget.TextView[@resource-id='title']",
        "price": "//android.widget.TextView[@resource-id='price']",
    })
    print(data)
```

---

## AutomationTool 参考

### 基本信息

- 工具名称: `automation`
- 模块路径: `xiaotie.tools.automation_tool`
- 依赖: 无外部依赖（使用 macOS 原生 AppleScript）

### 支持的操作

| action | 说明 | 关键参数 |
|--------|------|----------|
| `start` | 启动自动化会话 | - |
| `stop` | 停止自动化会话 | - |
| `status` | 查看自动化状态 | - |
| `launch_app` | 启动/激活 macOS 应用 | `app_name` |
| `send_message` | 通过微信发送消息 | `contact`, `message` |
| `screenshot` | 截取屏幕或窗口截图 | `window_name`, `output_path` |
| `execute` | 执行自定义 AppleScript | `script` |

### 参数 Schema

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["start", "stop", "status", "launch_app", "send_message", "screenshot", "execute"],
      "description": "操作类型"
    },
    "app_name": {
      "type": "string",
      "description": "应用名称（launch_app 时使用）"
    },
    "contact": {
      "type": "string",
      "description": "联系人名称（send_message 时使用）"
    },
    "message": {
      "type": "string",
      "description": "消息内容（send_message 时使用）"
    },
    "window_name": {
      "type": "string",
      "description": "窗口名称（screenshot 时使用，不指定则截全屏）"
    },
    "output_path": {
      "type": "string",
      "description": "截图保存路径"
    },
    "script": {
      "type": "string",
      "description": "AppleScript 脚本内容（execute 时使用）"
    }
  },
  "required": ["action"]
}
```

---

## 故障排查

### 常见问题

#### 1. "Not authorized to send Apple events"

原因: 终端应用未获得辅助功能权限。

解决:
1. 打开 **系统设置 > 隐私与安全性 > 辅助功能**
2. 添加你的终端应用
3. 重启终端

#### 2. 微信未响应 AppleScript 命令

原因: 微信未运行或未登录。

解决:
```bash
# 检查微信是否运行
pgrep -x WeChat

# 手动启动微信
open -a WeChat
```

#### 3. 截图保存失败

原因: 截图目录不存在或无写入权限。

解决:
```bash
# 创建截图目录
mkdir -p /tmp/xiaotie_screenshots

# 或指定自定义路径
await tool.execute(action="screenshot", output_path="~/Desktop/screenshot.png")
```

#### 4. Appium 连接失败（移动端）

原因: Appium Server 未启动或端口不匹配。

解决:
```bash
# 安装 Appium
npm install -g appium

# 启动 Appium Server
appium --port 4723

# 验证连接
curl http://localhost:4723/status
```

#### 5. 屏幕录制权限缺失

macOS 截图功能需要屏幕录制权限：

1. 打开 **系统设置 > 隐私与安全性 > 屏幕录制**
2. 添加终端应用
3. 重启终端

### 调试技巧

```python
import logging

# 开启详细日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("xiaotie.automation")
logger.setLevel(logging.DEBUG)
```

### 相关文档

- [工具系统文档](./tools.md) - 所有工具的完整参考
- [内置代理使用指南](./builtin-proxy-guide.md) - 代理抓包详细说明
- [代理架构设计](./proxy-architecture.md) - 代理模块技术细节
