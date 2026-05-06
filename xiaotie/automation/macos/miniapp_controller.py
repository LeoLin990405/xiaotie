"""macOS微信小程序控制器

基于WeChatController，提供小程序特定的自动化操作。
支持小程序搜索、打开、页面导航、数据提取等。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from .wechat_controller import WeChatConfig, WeChatController

logger = logging.getLogger(__name__)


@dataclass
class MiniAppInfo:
    """小程序信息"""

    name: str
    app_id: Optional[str] = None
    description: str = ""
    category: str = ""


class MiniAppController:
    """macOS微信小程序控制器

    封装小程序的搜索、打开、页面交互等操作。
    依赖WeChatController进行底层窗口控制。

    Example::

        wechat = WeChatController()
        miniapp = MiniAppController(wechat)
        await miniapp.open_by_search("美团外卖")
        await miniapp.wait_for_load()
        await miniapp.screenshot("miniapp.png")
    """

    def __init__(
        self,
        wechat: Optional[WeChatController] = None,
        config: Optional[WeChatConfig] = None,
    ):
        self.wechat = wechat or WeChatController(config)
        self._current_miniapp: Optional[MiniAppInfo] = None
        self._is_open = False

    @property
    def current_miniapp(self) -> Optional[MiniAppInfo]:
        return self._current_miniapp

    @property
    def is_open(self) -> bool:
        return self._is_open

    # ------------------------------------------------------------------
    # 小程序打开
    # ------------------------------------------------------------------

    async def open_by_search(self, name: str, timeout: int = 15) -> bool:
        """通过搜索打开小程序

        Args:
            name: 小程序名称
            timeout: 等待超时秒数
        """
        await self.wechat.activate()

        # macOS微信：Cmd+G 打开小程序面板（或通过搜索）
        await self.wechat.keystroke("f", modifiers=["command"])
        await asyncio.sleep(0.5)

        # 输入小程序名称
        await self.wechat.keystroke(name)
        await asyncio.sleep(2)

        # 按回车选择第一个结果
        await self.wechat.key_code(36)  # Return key
        await asyncio.sleep(1)

        # 等待小程序加载
        loaded = await self._wait_for_miniapp_window(timeout)
        if loaded:
            self._current_miniapp = MiniAppInfo(name=name)
            self._is_open = True
            logger.info("小程序已打开: %s", name)
        else:
            logger.warning("小程序打开超时: %s", name)

        return loaded

    async def open_by_recent(self, name: str) -> bool:
        """从最近使用的小程序中打开

        Args:
            name: 小程序名称
        """
        await self.wechat.activate()

        # 下拉打开小程序列表（macOS微信特定操作）
        # 通过菜单或快捷方式访问
        script = f'''
tell application "System Events"
    tell process "{self.wechat.config.process_name}"
        -- 尝试通过菜单打开小程序面板
        try
            click menu item "小程序" of menu "会话" of menu bar 1
        end try
    end tell
end tell'''
        try:
            await self.wechat._run_applescript(script)
            await asyncio.sleep(2)

            # 搜索目标小程序
            elements = await self.wechat.get_ui_elements()
            for elem in elements:
                if name in elem.get("description", ""):
                    self._current_miniapp = MiniAppInfo(name=name)
                    self._is_open = True
                    return True
        except RuntimeError:
            pass

        return False

    async def close(self) -> bool:
        """关闭当前小程序"""
        if not self._is_open:
            return True

        # ESC 或关闭按钮退出小程序
        await self.wechat.key_code(53)  # ESC key
        await asyncio.sleep(0.5)

        self._is_open = False
        name = self._current_miniapp.name if self._current_miniapp else "unknown"
        self._current_miniapp = None
        logger.info("小程序已关闭: %s", name)
        return True

    # ------------------------------------------------------------------
    # 页面交互
    # ------------------------------------------------------------------

    async def scroll_down(self, amount: int = 5) -> None:
        """向下滚动小程序页面"""
        script = f'''
tell application "System Events"
    tell process "{self.wechat.config.process_name}"
        repeat {amount} times
            key code 125  -- down arrow
            delay 0.1
        end repeat
    end tell
end tell'''
        await self.wechat._run_applescript(script)

    async def scroll_up(self, amount: int = 5) -> None:
        """向上滚动小程序页面"""
        script = f'''
tell application "System Events"
    tell process "{self.wechat.config.process_name}"
        repeat {amount} times
            key code 126  -- up arrow
            delay 0.1
        end repeat
    end tell
end tell'''
        await self.wechat._run_applescript(script)

    async def go_back(self) -> None:
        """小程序页面返回"""
        # Cmd+[ 或点击返回按钮
        await self.wechat.keystroke("[", modifiers=["command"])
        await asyncio.sleep(0.5)

    async def refresh(self) -> None:
        """刷新小程序页面"""
        await self.wechat.keystroke("r", modifiers=["command"])
        await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # 数据提取
    # ------------------------------------------------------------------

    async def get_page_title(self) -> str:
        """获取当前小程序页面标题"""
        script = f'''
tell application "System Events"
    tell process "{self.wechat.config.process_name}"
        try
            return name of window 1
        on error
            return ""
        end try
    end tell
end tell'''
        try:
            return await self.wechat._run_applescript(script)
        except RuntimeError:
            return ""

    async def get_visible_text(self) -> list[str]:
        """获取小程序页面可见文本"""
        script = f'''
tell application "System Events"
    tell process "{self.wechat.config.process_name}"
        tell window 1
            set textItems to value of static texts
            set result to ""
            repeat with t in textItems
                if t is not missing value then
                    set result to result & (t as text) & "\\n"
                end if
            end repeat
            return result
        end tell
    end tell
end tell'''
        try:
            result = await self.wechat._run_applescript(script)
            return [line for line in result.strip().split("\n") if line]
        except RuntimeError:
            return []

    async def screenshot(self, filename: Optional[str] = None) -> str:
        """截取小程序页面截图"""
        if not filename and self._current_miniapp:
            import time

            safe_name = self._current_miniapp.name.replace(" ", "_")
            filename = f"miniapp_{safe_name}_{int(time.time())}.png"
        return await self.wechat.screenshot(filename)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _wait_for_miniapp_window(self, timeout: int = 15) -> bool:
        """等待小程序窗口出现"""
        for _ in range(timeout):
            info = await self.wechat.get_window_info()
            if info:
                # 小程序窗口通常有特定标题
                title = info.get("title", "")
                if title and title != self.wechat.config.process_name:
                    return True
            await asyncio.sleep(1)
        return False

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "MiniAppController":
        await self.wechat.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._is_open:
            await self.close()
        await self.wechat.__aexit__(*exc)
