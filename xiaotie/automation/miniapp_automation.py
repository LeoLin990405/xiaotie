"""
微信小程序自动化模块

支持在macOS上通过iOS模拟器或Android模拟器自动化操作微信小程序。
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from appium.webdriver.common.appiumby import AppiumBy

from .appium_driver import AppiumConfig, AppiumDriver


@dataclass
class MiniAppConfig:
    """小程序配置"""

    miniapp_name: str  # 小程序名称
    miniapp_id: Optional[str] = None  # 小程序AppID（可选）
    wait_timeout: int = 30  # 等待超时（秒）
    proxy_host: str = "127.0.0.1"  # 代理服务器地址
    proxy_port: int = 8888  # 代理服务器端口


class MiniAppAutomation:
    """微信小程序自动化"""

    def __init__(
        self,
        appium_config: Optional[AppiumConfig] = None,
        miniapp_config: Optional[MiniAppConfig] = None,
    ):
        self.appium_config = appium_config or AppiumConfig()
        self.miniapp_config = miniapp_config or MiniAppConfig(miniapp_name="示例小程序")
        self.driver = AppiumDriver(self.appium_config)

    async def start(self) -> None:
        """启动自动化会话"""
        await self.driver.start()

    async def stop(self) -> None:
        """停止自动化会话"""
        await self.driver.stop()

    async def open_wechat(self) -> None:
        """打开微信"""
        # 微信应用已在AppiumConfig中配置，启动driver时会自动打开
        await asyncio.sleep(3)  # 等待微信启动

    async def search_miniapp(self, miniapp_name: str) -> None:
        """搜索小程序"""
        # 点击搜索按钮
        await self.driver.click(AppiumBy.ID, "com.tencent.mm:id/f8y")
        await asyncio.sleep(1)

        # 输入小程序名称
        await self.driver.send_keys(AppiumBy.ID, "com.tencent.mm:id/cd7", miniapp_name)
        await asyncio.sleep(2)

        # 点击小程序搜索结果
        await self.driver.click(
            AppiumBy.XPATH, f"//android.widget.TextView[@text='{miniapp_name}']"
        )
        await asyncio.sleep(3)

    async def open_miniapp_by_name(self, miniapp_name: str) -> None:
        """通过名称打开小程序"""
        await self.open_wechat()
        await self.search_miniapp(miniapp_name)

    async def open_miniapp_by_deeplink(self, deeplink: str) -> None:
        """通过深链接打开小程序

        Args:
            deeplink: 小程序深链接，格式如：
                weixin://dl/business/?t=xxx
        """
        if not self.driver.driver:
            raise RuntimeError("Driver not started")

        # 使用ADB打开深链接（Android）
        if self.appium_config.platform == "Android":
            import subprocess

            subprocess.run(
                ["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", deeplink]
            )
        else:
            # iOS使用xcrun simctl
            import subprocess

            subprocess.run(["xcrun", "simctl", "openurl", "booted", deeplink])

        await asyncio.sleep(5)  # 等待小程序加载

    async def wait_for_element(self, by: str, value: str, timeout: int = 30) -> bool:
        """等待元素出现"""
        for _ in range(timeout):
            try:
                await self.driver.find_element(by, value)
                return True
            except Exception:
                await asyncio.sleep(1)
        return False

    async def scroll_down(self, distance: int = 500) -> None:
        """向下滚动"""
        # 获取屏幕尺寸
        if not self.driver.driver:
            raise RuntimeError("Driver not started")

        size = self.driver.driver.get_window_size()
        start_x = size["width"] // 2
        start_y = size["height"] * 3 // 4
        end_y = start_y - distance

        await self.driver.swipe(start_x, start_y, start_x, end_y)
        await asyncio.sleep(1)

    async def scroll_to_bottom(self, max_scrolls: int = 10) -> None:
        """滚动到底部"""
        for _ in range(max_scrolls):
            await self.scroll_down()

    async def get_page_elements(self, xpath: str) -> List[Any]:
        """获取页面元素列表"""
        return await self.driver.find_elements(AppiumBy.XPATH, xpath)

    async def extract_data(self, selectors: Dict[str, str]) -> List[Dict[str, str]]:
        """提取页面数据

        Args:
            selectors: 选择器字典，格式如：
                {
                    "title": "//android.widget.TextView[@resource-id='title']",
                    "price": "//android.widget.TextView[@resource-id='price']"
                }

        Returns:
            提取的数据列表
        """
        data = []

        # 获取第一个选择器的所有元素（作为基准）
        first_key = list(selectors.keys())[0]
        elements = await self.get_page_elements(selectors[first_key])

        for i in range(len(elements)):
            item = {}
            for key, selector in selectors.items():
                try:
                    elements = await self.get_page_elements(selector)
                    if i < len(elements):
                        item[key] = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: elements[i].text
                        )
                except Exception:
                    item[key] = None
            data.append(item)

        return data

    async def screenshot(self, filename: str) -> None:
        """截图"""
        await self.driver.screenshot(filename)

    async def get_network_logs(self) -> List[Dict[str, Any]]:
        """获取网络日志（需要配合代理服务器）"""
        # 这个方法需要配合ProxyServerTool使用
        # 代理服务器会捕获所有网络请求
        pass

    async def __aenter__(self):
        """上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        await self.stop()


# macOS专用：iOS模拟器配置
def create_ios_simulator_config(
    simulator_name: str = "iPhone 15", ios_version: str = "17.0"
) -> AppiumConfig:
    """创建iOS模拟器配置"""
    return AppiumConfig(
        platform="iOS",
        device_name=simulator_name,
        platform_version=ios_version,
        app_package="com.tencent.xin",  # 微信Bundle ID
        automation_name="XCUITest",
        appium_server="http://localhost:4723",
    )


# macOS专用：Android模拟器配置
def create_android_emulator_config(emulator_name: str = "Pixel_5_API_31") -> AppiumConfig:
    """创建Android模拟器配置"""
    return AppiumConfig(
        platform="Android",
        device_name=emulator_name,
        platform_version="11",
        app_package="com.tencent.mm",
        app_activity=".ui.LauncherUI",
        automation_name="UiAutomator2",
        appium_server="http://localhost:4723",
    )
