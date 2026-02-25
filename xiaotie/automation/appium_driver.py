"""
Appium驱动封装

提供统一的Appium驱动接口，支持Android和iOS。
"""

import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy


@dataclass
class AppiumConfig:
    """Appium配置"""
    platform: str = "Android"  # Android 或 iOS
    device_name: str = "emulator-5554"
    platform_version: str = "11"
    app_package: str = "com.tencent.mm"  # 微信包名
    app_activity: str = ".ui.LauncherUI"  # 微信启动Activity
    automation_name: str = "UiAutomator2"
    appium_server: str = "http://localhost:4723"
    no_reset: bool = True  # 不重置应用状态
    full_reset: bool = False
    new_command_timeout: int = 300


class AppiumDriver:
    """Appium驱动封装"""

    def __init__(self, config: Optional[AppiumConfig] = None):
        self.config = config or AppiumConfig()
        self.driver: Optional[webdriver.Remote] = None

    async def start(self) -> None:
        """启动Appium会话"""
        if self.config.platform == "Android":
            options = UiAutomator2Options()
            options.platform_name = "Android"
            options.device_name = self.config.device_name
            options.platform_version = self.config.platform_version
            options.app_package = self.config.app_package
            options.app_activity = self.config.app_activity
            options.automation_name = self.config.automation_name
            options.no_reset = self.config.no_reset
            options.full_reset = self.config.full_reset
            options.new_command_timeout = self.config.new_command_timeout
        else:  # iOS
            options = XCUITestOptions()
            options.platform_name = "iOS"
            options.device_name = self.config.device_name
            options.platform_version = self.config.platform_version
            options.bundle_id = "com.tencent.xin"  # 微信iOS Bundle ID
            options.automation_name = "XCUITest"
            options.no_reset = self.config.no_reset
            options.full_reset = self.config.full_reset
            options.new_command_timeout = self.config.new_command_timeout

        # 在线程池中启动（Appium是同步的）
        loop = asyncio.get_event_loop()
        self.driver = await loop.run_in_executor(
            None,
            lambda: webdriver.Remote(self.config.appium_server, options=options)
        )

    async def stop(self) -> None:
        """停止Appium会话"""
        if self.driver:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.driver.quit)
            self.driver = None

    async def find_element(self, by: str, value: str, timeout: int = 10):
        """查找元素"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.driver.find_element(by, value)
        )

    async def find_elements(self, by: str, value: str):
        """查找多个元素"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.driver.find_elements(by, value)
        )

    async def click(self, by: str, value: str) -> None:
        """点击元素"""
        element = await self.find_element(by, value)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, element.click)

    async def send_keys(self, by: str, value: str, text: str) -> None:
        """输入文本"""
        element = await self.find_element(by, value)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: element.send_keys(text))

    async def get_text(self, by: str, value: str) -> str:
        """获取元素文本"""
        element = await self.find_element(by, value)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: element.text)

    async def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 500) -> None:
        """滑动屏幕"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.driver.swipe(start_x, start_y, end_x, end_y, duration)
        )

    async def tap(self, x: int, y: int) -> None:
        """点击坐标"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.driver.tap([(x, y)])
        )

    async def get_page_source(self) -> str:
        """获取页面源码"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.driver.page_source)

    async def screenshot(self, filename: str) -> None:
        """截图"""
        if not self.driver:
            raise RuntimeError("Driver not started")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.driver.save_screenshot(filename)
        )

    async def __aenter__(self):
        """上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        await self.stop()
