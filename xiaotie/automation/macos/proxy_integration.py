"""代理集成模块

将macOS微信自动化与代理服务器集成，实现自动化操作+网络抓包的完整工作流。
支持自动配置系统代理、捕获小程序网络请求、数据导出。
"""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .wechat_controller import WeChatController, WeChatConfig
from .miniapp_controller import MiniAppController, MiniAppInfo

logger = logging.getLogger(__name__)


# 延迟导入代理模块（可能未安装mitmproxy）
def _get_proxy_server():
    try:
        from xiaotie.proxy import ProxyServer
        return ProxyServer
    except ImportError:
        return None


def _get_request_storage():
    from xiaotie.proxy.storage import RequestStorage, CapturedRequest
    return RequestStorage, CapturedRequest


class ProxyIntegration:
    """代理集成管理器

    管理macOS系统代理配置，与ProxyServer协同工作。
    支持自动配置Wi-Fi代理、证书信任等。

    Example::

        integration = ProxyIntegration(proxy_port=8080)
        await integration.configure_system_proxy()
        # ... 执行自动化操作 ...
        await integration.restore_system_proxy()
    """

    def __init__(
        self,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 8080,
        network_service: Optional[str] = None,
    ):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self._network_service = network_service
        self._original_proxy_state: Optional[dict[str, Any]] = None

    async def get_network_service(self) -> str:
        """获取当前活跃的网络服务名称"""
        if self._network_service:
            return self._network_service

        proc = await asyncio.create_subprocess_exec(
            "networksetup", "-listallnetworkservices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        services = [
            s for s in stdout.decode().split("\n")[1:]
            if s and not s.startswith("*")
        ]
        # 优先选择Wi-Fi
        for svc in services:
            if "Wi-Fi" in svc or "wi-fi" in svc.lower():
                self._network_service = svc
                return svc
        # 回退到第一个可用服务
        if services:
            self._network_service = services[0]
            return services[0]
        raise RuntimeError("未找到可用的网络服务")

    async def get_current_proxy_state(self) -> dict[str, Any]:
        """获取当前系统代理状态"""
        svc = await self.get_network_service()
        state = {}

        for proxy_type, cmd in [
            ("http", "-getwebproxy"),
            ("https", "-getsecurewebproxy"),
        ]:
            proc = await asyncio.create_subprocess_exec(
                "networksetup", cmd, svc,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            info = {}
            for line in output.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip().lower()] = v.strip()
            state[proxy_type] = info

        return state

    async def configure_system_proxy(self) -> bool:
        """配置macOS系统代理指向本地代理服务器"""
        if platform.system() != "Darwin":
            logger.warning("系统代理配置仅支持macOS")
            return False

        svc = await self.get_network_service()

        # 保存当前状态以便恢复
        self._original_proxy_state = await self.get_current_proxy_state()

        for cmd in [
            ["networksetup", "-setwebproxy", svc, self.proxy_host, str(self.proxy_port)],
            ["networksetup", "-setsecurewebproxy", svc, self.proxy_host, str(self.proxy_port)],
            ["networksetup", "-setwebproxystate", svc, "on"],
            ["networksetup", "-setsecurewebproxystate", svc, "on"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        logger.info("系统代理已配置: %s:%d (服务: %s)", self.proxy_host, self.proxy_port, svc)
        return True

    async def restore_system_proxy(self) -> bool:
        """恢复系统代理到原始状态"""
        if platform.system() != "Darwin":
            return False

        svc = await self.get_network_service()

        for cmd in [
            ["networksetup", "-setwebproxystate", svc, "off"],
            ["networksetup", "-setsecurewebproxystate", svc, "off"],
        ]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        logger.info("系统代理已恢复 (服务: %s)", svc)
        self._original_proxy_state = None
        return True


class AutomationSession:
    """自动化会话 - 整合微信控制、小程序操作和代理抓包

    提供一站式的自动化工作流：
    1. 启动代理服务器
    2. 配置系统代理
    3. 启动微信并打开小程序
    4. 执行自动化操作（同时捕获网络请求）
    5. 导出数据并清理

    Example::

        async with AutomationSession(miniapp_name="美团外卖") as session:
            await session.miniapp.scroll_down()
            await session.miniapp.screenshot()
            flows = session.get_captured_flows()
            session.export("output.har", fmt="har")
    """

    def __init__(
        self,
        miniapp_name: Optional[str] = None,
        proxy_port: int = 8080,
        wechat_config: Optional[WeChatConfig] = None,
        enable_proxy: bool = True,
        miniapp_only: bool = True,
        on_response: Optional[Callable] = None,
    ):
        self.miniapp_name = miniapp_name
        self.enable_proxy = enable_proxy

        # 组件
        self.wechat = WeChatController(wechat_config)
        self.miniapp = MiniAppController(self.wechat)
        self.proxy_integration = ProxyIntegration(proxy_port=proxy_port)

        # 代理服务器（延迟初始化）
        self._proxy_server = None
        self._proxy_port = proxy_port
        self._miniapp_only = miniapp_only
        self._on_response = on_response
        self._is_started = False

    async def start(self) -> dict[str, Any]:
        """启动完整的自动化会话"""
        result: dict[str, Any] = {"status": "starting"}

        # 1. 启动代理服务器（如果启用）
        if self.enable_proxy:
            ProxyServerClass = _get_proxy_server()
            if ProxyServerClass:
                self._proxy_server = ProxyServerClass(
                    port=self._proxy_port,
                    miniapp_only=self._miniapp_only,
                    on_response=self._on_response,
                )
                proxy_info = await self._proxy_server.start()
                result["proxy"] = proxy_info

                # 配置系统代理
                await self.proxy_integration.configure_system_proxy()
                result["system_proxy"] = "configured"
            else:
                logger.warning("mitmproxy未安装，跳过代理服务器")
                result["proxy"] = "skipped (mitmproxy not installed)"

        # 2. 启动微信
        launched = await self.wechat.launch()
        result["wechat"] = "launched" if launched else "failed"

        # 3. 打开小程序（如果指定）
        if self.miniapp_name and launched:
            opened = await self.miniapp.open_by_search(self.miniapp_name)
            result["miniapp"] = self.miniapp_name if opened else "failed"

        self._is_started = True
        result["status"] = "started"
        logger.info("自动化会话已启动: %s", result)
        return result

    async def stop(self) -> dict[str, Any]:
        """停止自动化会话并清理"""
        result: dict[str, Any] = {"status": "stopping"}

        # 1. 关闭小程序
        if self.miniapp.is_open:
            await self.miniapp.close()
            result["miniapp"] = "closed"

        # 2. 恢复系统代理
        if self.enable_proxy:
            await self.proxy_integration.restore_system_proxy()
            result["system_proxy"] = "restored"

        # 3. 停止代理服务器
        if self._proxy_server:
            proxy_info = await self._proxy_server.stop()
            result["proxy"] = proxy_info
            self._proxy_server = None

        self._is_started = False
        result["status"] = "stopped"
        logger.info("自动化会话已停止: %s", result)
        return result

    # ------------------------------------------------------------------
    # 数据访问
    # ------------------------------------------------------------------

    def get_captured_flows(self) -> list[dict[str, Any]]:
        """获取捕获的网络请求"""
        if self._proxy_server:
            return self._proxy_server.get_captured_flows()
        return []

    def get_proxy_stats(self) -> dict[str, Any]:
        """获取代理统计信息"""
        if self._proxy_server:
            return self._proxy_server.storage.get_stats()
        return {"total": 0}

    def export(self, path: str, fmt: str = "json") -> Optional[Path]:
        """导出捕获的数据"""
        if self._proxy_server:
            return self._proxy_server.export(path, fmt=fmt)
        logger.warning("代理服务器未运行，无法导出")
        return None

    def get_status(self) -> dict[str, Any]:
        """获取会话状态"""
        status: dict[str, Any] = {
            "started": self._is_started,
            "miniapp": None,
            "proxy": None,
        }
        if self.miniapp.current_miniapp:
            status["miniapp"] = {
                "name": self.miniapp.current_miniapp.name,
                "is_open": self.miniapp.is_open,
            }
        if self._proxy_server:
            status["proxy"] = self._proxy_server.get_status()
        return status

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AutomationSession":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()
