"""macOS 自动化工具

集成 macOS 微信/小程序自动化到 xiaotie Agent 框架。
支持 AppleScript、Accessibility API、屏幕截图等原生 macOS 自动化方式。

功能概述:
    - start: 启动自动化会话（初始化 macOS 自动化引擎）
    - stop: 停止自动化会话
    - status: 查看自动化状态
    - launch_app: 启动/激活 macOS 应用
    - send_message: 通过微信发送消息
    - screenshot: 截取屏幕或窗口截图
    - execute: 执行自定义 AppleScript 或自动化脚本
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Optional

from ..schema import ToolResult
from .base import Tool

logger = logging.getLogger(__name__)


class AutomationTool(Tool):
    """macOS 自动化工具

    通过 AppleScript 和 macOS 原生 API 实现应用自动化。
    主要用于微信消息发送、小程序操作等场景。

    Actions:
        - start: 启动自动化会话
        - stop: 停止自动化会话
        - status: 查看运行状态
        - launch_app: 启动/激活应用
        - send_message: 发送微信消息
        - screenshot: 截取截图
        - execute: 执行自定义 AppleScript
    """

    def __init__(
        self,
        wechat_bundle_id: str = "com.tencent.xinWeChat",
        screenshot_dir: Optional[str] = None,
        applescript_timeout: int = 30,
    ):
        super().__init__()
        self._wechat_bundle_id = wechat_bundle_id
        self._screenshot_dir = screenshot_dir or str(Path.home() / ".xiaotie" / "screenshots")
        self._applescript_timeout = applescript_timeout
        self._running = False
        self._start_time: Optional[float] = None
        self._action_count = 0

    @property
    def name(self) -> str:
        return "automation"

    @property
    def description(self) -> str:
        return (
            "macOS 自动化工具，支持通过 AppleScript 控制应用。"
            "可启动应用、发送微信消息、截取屏幕截图、执行自定义脚本。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "start",
                        "stop",
                        "status",
                        "launch_app",
                        "send_message",
                        "screenshot",
                        "execute",
                    ],
                    "description": (
                        "操作类型：start-启动会话，stop-停止会话，"
                        "status-查看状态，launch_app-启动应用，"
                        "send_message-发送微信消息，screenshot-截图，"
                        "execute-执行 AppleScript"
                    ),
                },
                "app_name": {
                    "type": "string",
                    "description": "应用名称（launch_app 时使用，如 '微信'）",
                },
                "contact": {
                    "type": "string",
                    "description": "联系人名称（send_message 时使用）",
                },
                "message": {
                    "type": "string",
                    "description": "消息内容（send_message 时使用）",
                },
                "script": {
                    "type": "string",
                    "description": "AppleScript 脚本内容（execute 时使用）",
                },
                "window_name": {
                    "type": "string",
                    "description": "窗口名称（screenshot 时可选，不指定则截全屏）",
                },
                "output_file": {
                    "type": "string",
                    "description": "输出文件路径（screenshot 时可选）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """执行自动化操作"""
        action = kwargs.get("action")
        dispatch = {
            "start": self._action_start,
            "stop": self._action_stop,
            "status": self._action_status,
            "launch_app": self._action_launch_app,
            "send_message": self._action_send_message,
            "screenshot": self._action_screenshot,
            "execute": self._action_execute,
        }
        handler = dispatch.get(action)
        if handler is None:
            return ToolResult(success=False, error=f"未知操作: {action}")
        try:
            return await handler(kwargs)
        except Exception as e:
            logger.exception("自动化操作 '%s' 异常", action)
            return ToolResult(success=False, error=f"操作 {action} 异常: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_applescript(self, script: str) -> tuple[bool, str]:
        """执行 AppleScript 并返回 (success, output)"""
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._applescript_timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return False, "AppleScript 执行超时"

        if proc.returncode == 0:
            return True, stdout.decode("utf-8", errors="replace").strip()
        return False, stderr.decode("utf-8", errors="replace").strip()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _action_start(self, _kwargs: dict) -> ToolResult:
        """启动自动化会话"""
        if self._running:
            return ToolResult(
                success=True,
                content="自动化会话已在运行中",
            )

        # 确保截图目录存在
        Path(self._screenshot_dir).mkdir(parents=True, exist_ok=True)

        # 检查 macOS 辅助功能权限
        ok, output = await self._run_applescript(
            'tell application "System Events" to return name of first process'
        )
        if not ok:
            return ToolResult(
                success=False,
                error=(
                    "无法访问 macOS 辅助功能 API，请在"
                    " 系统设置 > 隐私与安全性 > 辅助功能 中授权终端应用。\n"
                    f"详细错误: {output}"
                ),
            )

        self._running = True
        self._start_time = time.time()
        self._action_count = 0

        return ToolResult(
            success=True,
            content=(
                "自动化会话已启动\n"
                f"- 截图目录: {self._screenshot_dir}\n"
                f"- 微信 Bundle ID: {self._wechat_bundle_id}\n"
                "- macOS 辅助功能: 已授权"
            ),
        )

    async def _action_stop(self, _kwargs: dict) -> ToolResult:
        """停止自动化会话"""
        if not self._running:
            return ToolResult(success=True, content="自动化会话未运行")

        uptime = int(time.time() - self._start_time) if self._start_time else 0
        count = self._action_count
        self._running = False
        self._start_time = None
        self._action_count = 0

        return ToolResult(
            success=True,
            content=f"自动化会话已停止（运行 {uptime} 秒，执行 {count} 次操作）",
        )

    async def _action_status(self, _kwargs: dict) -> ToolResult:
        """查看自动化状态"""
        lines = ["macOS 自动化状态:"]
        lines.append(f"- 运行状态: {'运行中' if self._running else '未运行'}")

        if self._running and self._start_time:
            uptime = int(time.time() - self._start_time)
            mins, secs = divmod(uptime, 60)
            lines.append(f"- 运行时间: {mins}分{secs}秒")
            lines.append(f"- 已执行操作: {self._action_count} 次")

        lines.append(f"- 截图目录: {self._screenshot_dir}")
        lines.append(f"- 微信 Bundle ID: {self._wechat_bundle_id}")

        # 检查微信是否在运行
        ok, output = await self._run_applescript(
            'tell application "System Events" to return (name of processes) contains "WeChat"'
        )
        if ok:
            wechat_running = output.strip().lower() == "true"
            lines.append(f"- 微信运行状态: {'运行中' if wechat_running else '未运行'}")

        return ToolResult(success=True, content="\n".join(lines))

    async def _action_launch_app(self, kwargs: dict) -> ToolResult:
        """启动/激活应用"""
        app_name = kwargs.get("app_name")
        if not app_name:
            return ToolResult(success=False, error="请指定 app_name 参数")

        ok, output = await self._run_applescript(f'tell application "{app_name}" to activate')
        if not ok:
            return ToolResult(success=False, error=f"启动应用失败: {output}")

        self._action_count += 1
        return ToolResult(
            success=True,
            content=f"已激活应用: {app_name}",
        )

    async def _action_send_message(self, kwargs: dict) -> ToolResult:
        """通过微信发送消息"""
        contact = kwargs.get("contact")
        message = kwargs.get("message")

        if not contact:
            return ToolResult(success=False, error="请指定 contact（联系人）参数")
        if not message:
            return ToolResult(success=False, error="请指定 message（消息内容）参数")

        # 使用 AppleScript 控制微信发送消息
        # 步骤: 激活微信 → 搜索联系人 → 发送消息
        script = f'''
tell application "WeChat" to activate
delay 1
tell application "System Events"
    tell process "WeChat"
        -- 使用 Cmd+F 打开搜索
        keystroke "f" using command down
        delay 0.5
        -- 输入联系人名称
        keystroke "{contact}"
        delay 1
        -- 按回车选择第一个结果
        key code 36
        delay 0.5
        -- 输入消息
        keystroke "{message}"
        delay 0.3
        -- 按回车发送
        key code 36
    end tell
end tell
'''
        ok, output = await self._run_applescript(script)
        if not ok:
            return ToolResult(
                success=False,
                error=f"发送消息失败: {output}",
            )

        self._action_count += 1
        return ToolResult(
            success=True,
            content=f"已向 [{contact}] 发送消息: {message}",
        )

    async def _action_screenshot(self, kwargs: dict) -> ToolResult:
        """截取截图"""
        window_name = kwargs.get("window_name")
        output_file = kwargs.get("output_file")

        if not output_file:
            ts = int(time.time())
            output_file = str(Path(self._screenshot_dir) / f"screenshot_{ts}.png")

        output_path = Path(output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if window_name:
            # 截取指定窗口
            cmd = ["screencapture", "-l", "", str(output_path)]
            # 先获取窗口 ID
            ok, wid = await self._run_applescript(
                f'tell application "System Events" to return id of '
                f'first window of process "{window_name}"'
            )
            if ok and wid:
                cmd = ["screencapture", "-l", wid, str(output_path)]
            else:
                # 回退到全屏截图
                cmd = ["screencapture", "-x", str(output_path)]
        else:
            cmd = ["screencapture", "-x", str(output_path)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if proc.returncode != 0 or not output_path.exists():
            return ToolResult(success=False, error="截图失败")

        self._action_count += 1
        size_kb = output_path.stat().st_size // 1024
        target = f"窗口 [{window_name}]" if window_name else "全屏"
        return ToolResult(
            success=True,
            content=f"截图完成 ({target}, {size_kb} KB)\n- 文件: {output_path}",
        )

    async def _action_execute(self, kwargs: dict) -> ToolResult:
        """执行自定义 AppleScript"""
        script = kwargs.get("script")
        if not script:
            return ToolResult(success=False, error="请指定 script 参数")

        ok, output = await self._run_applescript(script)
        self._action_count += 1

        if not ok:
            return ToolResult(success=False, error=f"脚本执行失败: {output}")

        return ToolResult(
            success=True,
            content=f"脚本执行成功\n输出: {output}" if output else "脚本执行成功（无输出）",
        )
