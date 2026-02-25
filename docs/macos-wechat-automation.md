# macOS 微信小程序自动化技术方案

> 研究日期: 2026-02-25
> 适用项目: xiaotie (小铁) - AI Agent 框架

## 1. 概述

本文档研究在 macOS 上自动化操作微信桌面版，特别是打开和抓取微信小程序数据的技术方案。
目标是为 xiaotie 项目的 `automation` 模块提供 macOS 原生方案，替代现有的 Appium 移动端方案。

### 1.1 核心挑战

| 挑战 | 说明 |
|------|------|
| 微信无公开 API | 桌面版微信没有自动化 API，只能通过 UI 操作 |
| 小程序运行在 WKWebView | macOS 版小程序使用 WKWebView 渲染，JS 运行在 JavaScriptCore |
| HTTPS 证书校验 | 微信可能使用证书固定 (Certificate Pinning)，增加抓包难度 |
| UI 元素不稳定 | 微信版本更新可能改变 UI 层级结构 |

## 2. 自动化方案对比

### 2.1 方案总览

| 方案 | 可行性 | 稳定性 | 开发难度 | 维护成本 | 推荐度 |
|------|--------|--------|----------|----------|--------|
| AppleScript + System Events | ★★★★ | ★★★ | ★★★★★ | ★★★ | **推荐** |
| macOS Accessibility API (Python) | ★★★★★ | ★★★★ | ★★★ | ★★★ | **首选** |
| PyAutoGUI (图像识别) | ★★★ | ★★ | ★★★★ | ★★ | 备选 |
| Appium (现有方案) | ★★ | ★★★ | ★★ | ★★ | 仅移动端 |

---

## 3. 方案一: AppleScript + System Events (推荐)

### 3.1 原理

通过 macOS System Events 的 GUI Scripting 功能，操控微信桌面版的 UI 元素。

### 3.2 前置条件

- 系统偏好设置 → 隐私与安全性 → 辅助功能 → 允许终端/Python 控制
- 微信桌面版已安装并登录

### 3.3 核心代码示例

#### 打开微信并搜索小程序

```applescript
-- 激活微信
tell application "WeChat" to activate
delay 1

-- 通过 System Events 操作 UI
tell application "System Events" to tell process "WeChat"
    set frontmost to true

    -- 打开搜索 (Cmd+F 或点击搜索框)
    keystroke "f" using command down
    delay 0.5

    -- 输入小程序名称
    keystroke "小程序名称"
    delay 2

    -- 点击搜索结果中的小程序
    -- 需要根据实际 UI 层级定位
end tell
```

#### Python 调用 AppleScript

```python
import subprocess

def run_applescript(script: str) -> str:
    """执行 AppleScript 并返回结果"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def activate_wechat():
    """激活微信窗口"""
    run_applescript('tell application "WeChat" to activate')

def search_in_wechat(keyword: str):
    """在微信中搜索"""
    script = f'''
    tell application "System Events" to tell process "WeChat"
        set frontmost to true
        keystroke "f" using command down
        delay 0.5
        keystroke "{keyword}"
        delay 2
    end tell
    '''
    run_applescript(script)
```

### 3.4 优缺点

| 优点 | 缺点 |
|------|------|
| macOS 原生支持，无需额外依赖 | UI 层级可能随微信版本变化 |
| 可通过 Python subprocess 调用 | 执行速度较慢（需要 delay） |
| 社区有成功案例 (macscripter.net) | 无法直接操作 WKWebView 内部 |
| 可操作菜单、按钮、文本框 | 需要辅助功能权限 |

---

## 4. 方案二: macOS Accessibility API (首选方案)

### 4.1 原理

使用 macOS 的 Accessibility API (AXUIElement) 直接操控微信的 UI 元素树。
这是 WeChat-MCP 项目验证过的方案，已有成熟实现。

### 4.2 技术栈

| 组件 | 用途 |
|------|------|
| `pyobjc-framework-ApplicationServices` | Python 绑定 macOS Accessibility API |
| `pyobjc-framework-Quartz` | 屏幕截图、坐标操作 |
| `ApplicationServices.AXUIElement` | 核心 API，操控 UI 元素 |

### 4.3 核心实现

```python
import AppKit
import ApplicationServices as AS
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
)

class WeChatAccessibility:
    """通过 Accessibility API 操控微信"""

    def __init__(self):
        self.app_ref = None
        self._find_wechat()

    def _find_wechat(self):
        """查找微信进程并获取 AXUIElement 引用"""
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        apps = workspace.runningApplications()
        for app in apps:
            if app.bundleIdentifier() == "com.tencent.xinWeChat":
                pid = app.processIdentifier()
                self.app_ref = AS.AXUIElementCreateApplication(pid)
                break

    def get_windows(self) -> list:
        """获取微信所有窗口"""
        err, windows = AS.AXUIElementCopyAttributeValue(
            self.app_ref, "AXWindows", None
        )
        return list(windows) if windows else []

    def get_element_tree(self, element, depth=0, max_depth=5):
        """递归获取 UI 元素树"""
        if depth >= max_depth:
            return None

        err, role = AS.AXUIElementCopyAttributeValue(
            element, "AXRole", None
        )
        err, title = AS.AXUIElementCopyAttributeValue(
            element, "AXTitle", None
        )
        err, children = AS.AXUIElementCopyAttributeValue(
            element, "AXChildren", None
        )

        node = {
            "role": str(role) if role else "",
            "title": str(title) if title else "",
            "children": []
        }

        if children:
            for child in children:
                child_node = self.get_element_tree(
                    child, depth + 1, max_depth
                )
                if child_node:
                    node["children"].append(child_node)

        return node

    def click_element(self, element):
        """点击指定 UI 元素"""
        AS.AXUIElementPerformAction(element, "AXPress")

    def set_value(self, element, value: str):
        """设置元素值（如文本框）"""
        AS.AXUIElementSetAttributeValue(
            element, "AXValue", value
        )
```

### 4.4 参考项目: WeChat-MCP

[WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP) 是一个已验证的方案：
- 使用 macOS Accessibility API + 屏幕截图
- 支持消息读取、发送、联系人管理
- Python 3.12+，MCP 协议
- 70+ GitHub Stars，活跃维护

### 4.5 优缺点

| 优点 | 缺点 |
|------|------|
| 精确控制 UI 元素 | 需要 pyobjc 依赖 |
| 可获取完整 UI 元素树 | 需要辅助功能权限 |
| 已有成熟开源实现 (WeChat-MCP) | 无法操作 WKWebView 内部内容 |
| 比 AppleScript 更灵活 | macOS 版本升级可能影响 API |
| 可编程性强，易于集成 | 学习曲线较陡 |

---

## 5. 方案三: PyAutoGUI (图像识别备选)

### 5.1 原理

通过屏幕截图 + 图像匹配定位 UI 元素，模拟鼠标键盘操作。

### 5.2 核心代码

```python
import pyautogui
import time

def open_miniapp_by_image(miniapp_icon_path: str):
    """通过图像识别打开小程序"""
    # 截图查找小程序图标
    location = pyautogui.locateOnScreen(
        miniapp_icon_path, confidence=0.8
    )
    if location:
        center = pyautogui.center(location)
        pyautogui.click(center)
    else:
        raise RuntimeError("未找到小程序图标")

def search_and_open(keyword: str):
    """搜索并打开小程序"""
    # 点击搜索框（需要预先截图搜索图标）
    pyautogui.hotkey("command", "f")
    time.sleep(0.5)
    pyautogui.typewrite(keyword, interval=0.05)
    time.sleep(2)
    # 需要图像识别找到搜索结果并点击
```

### 5.3 优缺点

| 优点 | 缺点 |
|------|------|
| 不依赖 UI 层级结构 | 分辨率/缩放变化会失效 |
| 可操作任何可见元素 | 速度慢，需要截图匹配 |
| 简单直观 | 需要维护参考图片库 |
| 跨应用通用 | macOS 需要屏幕录制权限 |

---

## 6. 微信小程序打开方式

### 6.1 方式对比

| 方式 | 可行性 | 说明 |
|------|--------|------|
| 搜索打开 | ★★★★★ | 通过微信搜索框搜索小程序名称 |
| URL Scheme | ★★★★ | `weixin://dl/business/?appid=APPID&path=PATH` |
| 最近使用 | ★★★ | 从最近使用的小程序列表打开 |
| 下拉面板 | ★★★ | 微信主界面下拉显示最近小程序 |
| 二维码 | ★★ | 识别小程序码打开 |

### 6.2 URL Scheme 详解

微信小程序支持两种 URL Scheme：

#### 明文 URL Scheme（推荐）

```
weixin://dl/business/?appid=APPID&path=PATH&query=QUERY&env_version=release
```

参数说明：
- `appid`: 小程序 AppID（必填）
- `path`: 页面路径（必填，已发布的页面）
- `query`: 查询参数（可选，最大 512 字符，需 URL 编码）
- `env_version`: 版本（release/trial/develop）

#### 加密 URL Scheme

```
weixin://dl/business/?t=TICKET
```

- 通过微信服务端 API 生成
- 每日限额 50 万次生成
- 每日限额 300 万次打开

#### macOS 上使用 URL Scheme

```python
import subprocess

def open_miniapp_by_scheme(appid: str, path: str = "", query: str = ""):
    """通过 URL Scheme 打开小程序"""
    url = f"weixin://dl/business/?appid={appid}&path={path}"
    if query:
        url += f"&query={query}"
    url += "&env_version=release"

    # macOS 使用 open 命令打开 URL Scheme
    subprocess.run(["open", url], check=True)
```

### 6.3 搜索打开（最通用）

```python
import subprocess
import time

def open_miniapp_by_search(name: str):
    """通过搜索打开小程序"""
    # 1. 激活微信
    subprocess.run(["osascript", "-e",
        'tell application "WeChat" to activate'])
    time.sleep(1)

    # 2. 打开搜索
    script = '''
    tell application "System Events" to tell process "WeChat"
        set frontmost to true
        keystroke "f" using command down
        delay 0.5
        keystroke "%s"
        delay 2
    end tell
    ''' % name
    subprocess.run(["osascript", "-e", script])

    # 3. 等待搜索结果，点击小程序标签
    # 需要配合 Accessibility API 或图像识别
```

---

## 7. 代理抓包方案

### 7.1 架构

```
微信小程序 (WKWebView)
    ↓ HTTPS 请求
macOS 系统代理
    ↓
mitmproxy (xiaotie 内置)
    ↓ 解密 + 捕获
目标服务器
```

### 7.2 xiaotie 内置代理集成

xiaotie 已有完整的 mitmproxy 代理模块 (`xiaotie/proxy/`)，支持：
- HTTP/HTTPS 流量捕获
- 小程序域名过滤 (`MiniAppFilter`)
- 自动配置 macOS 系统代理
- HAR/JSON 导出

#### 已支持的小程序域名

```python
MINIAPP_DOMAINS = (
    "servicewechat.com",
    "weixin.qq.com",
    "wx.qq.com",
    "qlogo.cn",
    "weixinbridge.com",
    "wxaapi.weixin.qq.com",
    "mp.weixin.qq.com",
    "api.weixin.qq.com",
)
```

### 7.3 证书信任配置

mitmproxy HTTPS 抓包需要信任 CA 证书：

```bash
# 1. 启动 mitmproxy 生成 CA 证书
# 证书位置: ~/.mitmproxy/mitmproxy-ca-cert.pem

# 2. 安装到 macOS 钥匙串
sudo security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain \
    ~/.mitmproxy/mitmproxy-ca-cert.pem

# 3. 或通过 Keychain Access GUI 手动信任
open ~/.mitmproxy/mitmproxy-ca-cert.pem
# 在钥匙串中找到证书 → 始终信任
```

### 7.4 微信 HTTPS 抓包注意事项

| 问题 | 解决方案 |
|------|----------|
| 微信可能使用证书固定 | 部分 API 域名可能无法抓包 |
| WKWebView 遵循系统代理 | 配置系统代理即可拦截小程序请求 |
| 小程序业务 API 通常不固定证书 | 业务数据请求一般可以抓取 |
| 微信核心 API 可能固定证书 | 登录、支付等核心接口可能无法拦截 |

### 7.5 代理 + 自动化联合方案

```python
import asyncio
from xiaotie.proxy import ProxyServer

async def capture_miniapp_data(miniapp_name: str):
    """自动化打开小程序并抓取数据"""

    # 1. 启动代理服务器
    proxy = ProxyServer(
        port=8080,
        miniapp_only=True,        # 仅捕获小程序请求
        auto_system_proxy=True,   # 自动配置系统代理
        capture_body=True,        # 捕获请求/响应体
    )
    await proxy.start()

    # 2. 自动化打开小程序
    # (使用 AppleScript 或 Accessibility API)
    open_miniapp_by_search(miniapp_name)

    # 3. 等待数据加载
    await asyncio.sleep(10)

    # 4. 获取捕获的数据
    flows = proxy.get_captured_flows()

    # 5. 过滤 API 响应
    api_data = [
        f for f in flows
        if f.get("response_content_type", "").startswith("application/json")
    ]

    # 6. 导出
    proxy.export("miniapp_capture.json", fmt="json")
    proxy.export("miniapp_capture.har", fmt="har")

    # 7. 停止代理
    await proxy.stop()

    return api_data
```

---

## 8. 小程序数据提取方案

### 8.1 方案对比

| 方案 | 数据类型 | 可行性 | 说明 |
|------|----------|--------|------|
| 代理抓包 (API 响应) | JSON/API 数据 | ★★★★★ | 最可靠，获取结构化数据 |
| Accessibility API (UI 文本) | 可见文本 | ★★★ | 仅能获取 UI 层可见文本 |
| 屏幕截图 + OCR | 图像中的文本 | ★★ | 精度有限，速度慢 |
| WKWebView 调试 | DOM/JS 数据 | ★ | 微信禁用了 WebView 调试 |

### 8.2 推荐方案: 代理抓包 + UI 自动化

最佳实践是组合使用：

1. **代理抓包**获取 API 返回的结构化数据（JSON）
2. **UI 自动化**触发页面操作（滚动、点击、翻页）
3. **两者配合**实现完整的数据采集流程

### 8.3 数据提取流程

```
┌─────────────────────────────────────────────┐
│  1. 启动 mitmproxy 代理                      │
│  2. 配置系统代理                              │
│  3. 通过 Accessibility API 打开微信           │
│  4. 搜索并打开目标小程序                      │
│  5. 代理捕获小程序初始 API 请求               │
│  6. UI 自动化: 滚动页面触发更多数据加载        │
│  7. 代理捕获分页/增量 API 请求                │
│  8. 重复 6-7 直到数据采集完成                 │
│  9. 导出捕获数据 (JSON/HAR)                   │
│  10. 关闭小程序，恢复系统代理                  │
└─────────────────────────────────────────────┘
```

---

## 9. 推荐技术架构

### 9.1 模块设计

```
xiaotie/automation/
├── __init__.py
├── appium_driver.py          # 现有: 移动端 Appium 驱动
├── miniapp_automation.py     # 现有: 移动端小程序自动化
├── macos_wechat.py          # 新增: macOS 微信自动化核心
├── accessibility.py          # 新增: macOS Accessibility API 封装
├── applescript.py           # 新增: AppleScript 工具函数
└── miniapp_workflow.py      # 新增: 小程序数据采集工作流
```

### 9.2 依赖

```toml
# pyproject.toml 新增可选依赖
[project.optional-dependencies]
macos = [
    "pyobjc-framework-ApplicationServices>=10.0",
    "pyobjc-framework-Quartz>=10.0",
    "pyobjc-framework-Cocoa>=10.0",
]
automation = [
    "pyautogui>=0.9.54",
    "Pillow>=10.0",
]
```

### 9.3 核心类设计

```python
class MacOSWeChatAutomation:
    """macOS 微信自动化控制器"""

    async def launch_wechat(self) -> bool
    async def open_miniapp(self, name: str = None,
                           appid: str = None,
                           url_scheme: str = None) -> bool
    async def close_miniapp(self) -> bool
    async def scroll_miniapp(self, direction: str,
                             distance: int) -> bool
    async def click_element(self, role: str,
                            title: str) -> bool
    async def get_visible_text(self) -> list[str]
    async def screenshot(self, path: str) -> str

class MiniAppDataCollector:
    """小程序数据采集器 (代理 + 自动化)"""

    async def start_capture(self, miniapp_name: str) -> None
    async def trigger_load_more(self) -> None
    async def get_api_responses(self) -> list[dict]
    async def export_data(self, path: str,
                          fmt: str = "json") -> str
    async def stop_capture(self) -> dict
```

---

## 10. 可行性评估总结

### 10.1 推荐方案

**首选: Accessibility API + mitmproxy 代理**

理由：
1. Accessibility API 已被 WeChat-MCP 项目验证可行
2. xiaotie 已有完整的 mitmproxy 代理模块
3. 两者组合可实现 UI 操作 + 数据抓取的完整流程
4. Python 生态成熟，pyobjc 提供完整的 macOS API 绑定

### 10.2 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 微信更新导致 UI 变化 | 高 | 中 | 使用角色+标题匹配而非固定路径 |
| 证书固定阻止抓包 | 中 | 高 | 仅抓取业务 API，核心 API 跳过 |
| macOS 权限限制 | 低 | 高 | 提供清晰的权限配置指南 |
| pyobjc 兼容性问题 | 低 | 中 | 锁定版本，提供 AppleScript 降级方案 |

### 10.3 实施优先级

1. **P0**: 实现 `accessibility.py` - macOS Accessibility API 封装
2. **P0**: 实现 `macos_wechat.py` - 微信自动化核心（打开/搜索/操作）
3. **P1**: 实现 `miniapp_workflow.py` - 代理 + 自动化联合工作流
4. **P1**: 集成到 xiaotie Tool 系统
5. **P2**: 实现 `applescript.py` - AppleScript 降级方案
6. **P2**: PyAutoGUI 图像识别备选方案

---

## 11. 参考资源

- [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP) - macOS 微信 Accessibility API 自动化
- [微信小程序 URL Scheme 文档](https://developers.weixin.qq.com/miniprogram/en/dev/framework/open-ability/url-scheme.html)
- [微信小程序运行环境](https://developers.weixin.qq.com/miniprogram/dev/framework/runtime/env)
- [macOS Accessibility API](https://developer.apple.com/documentation/accessibility/accessibility-api)
- [pyobjc-framework-Accessibility](https://pypi.org/project/pyobjc-framework-Accessibility/)
- [pyax - Python macOS Accessibility](https://github.com/eeejay/pyax)
- [AppleScript GUI Scripting WeChat](https://www.macscripter.net/t/gui-scripting-of-wechat/72591)
- [mitmproxy 证书配置](https://docs.mitmproxy.org/stable/concepts/certificates/)
- [spy-debugger WebView 调试](https://github.com/wuchangming/spy-debugger)
