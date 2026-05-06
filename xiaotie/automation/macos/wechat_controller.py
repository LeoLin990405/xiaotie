"""macOS微信控制器

通过AppleScript和Accessibility API控制macOS版微信。
支持窗口管理、消息发送、小程序入口导航等操作。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"
WECHAT_PROCESS_NAME = "WeChat"


class WeChatState(Enum):
    """微信运行状态"""

    NOT_RUNNING = "not_running"
    RUNNING = "running"
    LOGGED_IN = "logged_in"
    UNKNOWN = "unknown"


@dataclass
class WeChatConfig:
    """微信控制器配置"""

    bundle_id: str = WECHAT_BUNDLE_ID
    process_name: str = WECHAT_PROCESS_NAME
    launch_timeout: int = 10
    action_delay: float = 0.5
    screenshot_dir: str = "/tmp/xiaotie_screenshots"


class WeChatController:
    """macOS微信控制器

    通过AppleScript控制微信窗口和基本操作。
    支持启动/激活微信、窗口管理、搜索导航等。

    Example::

        async with WeChatController() as wechat:
            state = await wechat.get_state()
            if state != WeChatState.RUNNING:
                await wechat.launch()
            await wechat.activate()
            await wechat.search("小程序名称")
    """

    def __init__(self, config: Optional[WeChatConfig] = None):
        self.config = config or WeChatConfig()
        self._state = WeChatState.UNKNOWN

    # ------------------------------------------------------------------
    # AppleScript 执行
    # ------------------------------------------------------------------

    async def _run_applescript(self, script: str) -> str:
        """异步执行AppleScript并返回输出"""
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.warning("AppleScript执行失败: %s", err_msg)
            raise RuntimeError(f"AppleScript error: {err_msg}")
        return stdout.decode("utf-8", errors="replace").strip()

    async def _run_shell(self, *args: str) -> str:
        """异步执行shell命令"""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode("utf-8", errors="replace").strip()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def get_state(self) -> WeChatState:
        """检测微信运行状态"""
        script = (
            f'tell application "System Events" to '
            f'(name of processes) contains "{self.config.process_name}"'
        )
        try:
            result = await self._run_applescript(script)
            if result == "true":
                self._state = WeChatState.RUNNING
            else:
                self._state = WeChatState.NOT_RUNNING
        except RuntimeError:
            self._state = WeChatState.UNKNOWN
        return self._state

    async def launch(self) -> bool:
        """启动微信应用"""
        script = f'tell application id "{self.config.bundle_id}" to activate'
        try:
            await self._run_applescript(script)
            # 等待启动
            for _ in range(self.config.launch_timeout):
                state = await self.get_state()
                if state == WeChatState.RUNNING:
                    logger.info("微信已启动")
                    return True
                await asyncio.sleep(1)
            logger.warning("微信启动超时")
            return False
        except RuntimeError as e:
            logger.error("启动微信失败: %s", e)
            return False

    async def quit(self) -> bool:
        """退出微信"""
        script = f'tell application id "{self.config.bundle_id}" to quit'
        try:
            await self._run_applescript(script)
            self._state = WeChatState.NOT_RUNNING
            logger.info("微信已退出")
            return True
        except RuntimeError:
            return False

    async def activate(self) -> bool:
        """激活微信窗口（置于前台）"""
        script = f'tell application id "{self.config.bundle_id}" to activate'
        try:
            await self._run_applescript(script)
            await asyncio.sleep(self.config.action_delay)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # 窗口管理
    # ------------------------------------------------------------------

    async def get_window_info(self) -> dict[str, Any]:
        """获取微信主窗口信息"""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        set winList to windows
        if (count of winList) > 0 then
            set w to item 1 of winList
            set winPos to position of w
            set winSize to size of w
            set winTitle to name of w
            return winTitle & "|" & (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "|" & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
        end if
    end tell
end tell'''
        try:
            result = await self._run_applescript(script)
            parts = result.split("|")
            if len(parts) == 3:
                pos = parts[1].split(",")
                size = parts[2].split(",")
                return {
                    "title": parts[0],
                    "x": int(pos[0]),
                    "y": int(pos[1]),
                    "width": int(size[0]),
                    "height": int(size[1]),
                }
        except (RuntimeError, ValueError, IndexError):
            pass
        return {}

    async def resize_window(self, width: int, height: int) -> bool:
        """调整微信窗口大小"""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        set size of window 1 to {{{width}, {height}}}
    end tell
end tell'''
        try:
            await self._run_applescript(script)
            return True
        except RuntimeError:
            return False

    async def move_window(self, x: int, y: int) -> bool:
        """移动微信窗口位置"""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        set position of window 1 to {{{x}, {y}}}
    end tell
end tell'''
        try:
            await self._run_applescript(script)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # 键盘与搜索
    # ------------------------------------------------------------------

    async def keystroke(self, key: str, modifiers: Optional[list[str]] = None) -> None:
        """发送键盘事件

        Args:
            key: 按键字符
            modifiers: 修饰键列表，如 ["command", "shift"]
        """
        if modifiers:
            mod_str = ", ".join(f"{m} down" for m in modifiers)
            script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        keystroke "{key}" using {{{mod_str}}}
    end tell
end tell'''
        else:
            script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        keystroke "{key}"
    end tell
end tell'''
        await self._run_applescript(script)
        await asyncio.sleep(self.config.action_delay)

    async def key_code(self, code: int, modifiers: Optional[list[str]] = None) -> None:
        """发送键码事件（用于特殊键如回车、ESC等）"""
        if modifiers:
            mod_str = ", ".join(f"{m} down" for m in modifiers)
            script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        key code {code} using {{{mod_str}}}
    end tell
end tell'''
        else:
            script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        key code {code}
    end tell
end tell'''
        await self._run_applescript(script)
        await asyncio.sleep(self.config.action_delay)

    async def search(self, keyword: str) -> bool:
        """在微信中搜索（Cmd+F 打开搜索框并输入）

        Args:
            keyword: 搜索关键词
        """
        await self.activate()
        # Cmd+F 打开搜索
        await self.keystroke("f", modifiers=["command"])
        await asyncio.sleep(0.3)
        # 输入关键词
        await self.keystroke(keyword)
        await asyncio.sleep(1)
        return True

    # ------------------------------------------------------------------
    # 点击操作
    # ------------------------------------------------------------------

    async def click_at(self, x: int, y: int) -> None:
        """点击屏幕坐标"""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        click at {{{x}, {y}}}
    end tell
end tell'''
        try:
            await self._run_applescript(script)
        except RuntimeError:
            # 回退到cliclick（如果可用）
            await self._run_shell("cliclick", f"c:{x},{y}")
        await asyncio.sleep(self.config.action_delay)

    async def click_menu(self, menu_name: str, item_name: str) -> bool:
        """点击菜单项"""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        click menu item "{item_name}" of menu "{menu_name}" of menu bar 1
    end tell
end tell'''
        try:
            await self._run_applescript(script)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # 截图
    # ------------------------------------------------------------------

    async def screenshot(self, filename: Optional[str] = None) -> str:
        """截取微信窗口截图

        Returns:
            截图文件路径
        """
        import os

        os.makedirs(self.config.screenshot_dir, exist_ok=True)

        if not filename:
            import time

            filename = f"wechat_{int(time.time())}.png"

        filepath = os.path.join(self.config.screenshot_dir, filename)

        # 获取窗口ID
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        set wid to id of window 1
    end tell
end tell'''
        try:
            window_id = await self._run_applescript(script)
            await self._run_shell("screencapture", "-l", window_id, filepath)
        except RuntimeError:
            # 回退到全屏截图
            await self._run_shell("screencapture", "-x", filepath)

        logger.info("截图已保存: %s", filepath)
        return filepath

    # ------------------------------------------------------------------
    # UI元素查询（Accessibility API）
    # ------------------------------------------------------------------

    async def get_ui_elements(self, role: Optional[str] = None) -> list[dict[str, Any]]:
        """获取微信窗口的UI元素列表

        Args:
            role: 过滤角色类型，如 "AXButton", "AXTextField"
        """
        role_filter = f'whose role is "{role}"' if role else ""
        script = f'''
tell application "System Events"
    tell process "{self.config.process_name}"
        tell window 1
            set elems to UI elements {role_filter}
            set result to ""
            repeat with e in elems
                set result to result & (role of e as text) & "|" & (description of e as text) & "\\n"
            end repeat
            return result
        end tell
    end tell
end tell'''
        try:
            result = await self._run_applescript(script)
            elements = []
            for line in result.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 1)
                    elements.append(
                        {
                            "role": parts[0],
                            "description": parts[1] if len(parts) > 1 else "",
                        }
                    )
            return elements
        except RuntimeError:
            return []

    async def find_element_by_description(self, description: str) -> Optional[dict[str, Any]]:
        """通过描述查找UI元素"""
        elements = await self.get_ui_elements()
        for elem in elements:
            if description.lower() in elem.get("description", "").lower():
                return elem
        return None

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "WeChatController":
        state = await self.get_state()
        if state == WeChatState.NOT_RUNNING:
            await self.launch()
        return self

    async def __aexit__(self, *exc) -> None:
        pass  # 不自动退出微信
