"""代理服务器核心类

基于 mitmproxy 实现的代理服务器，支持 HTTP/HTTPS 流量捕获。
提供异步接口，管理 mitmproxy 实例的完整生命周期。
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .cert_manager import CertManager
from .storage import CapturedRequest, RequestStorage

logger = logging.getLogger(__name__)

# 延迟导入检查
try:
    from mitmproxy import options
    from mitmproxy.tools.dump import DumpMaster

    _HAS_MITMPROXY = True
except ImportError:
    _HAS_MITMPROXY = False


class ProxyServer:
    """mitmproxy 代理服务器封装

    管理 mitmproxy 实例的生命周期，提供异步接口。
    支持请求捕获、小程序过滤、HAR/JSON 导出。

    Args:
        port: 代理监听端口，默认 8080
        host: 监听地址，默认 0.0.0.0
        enable_ssl: 是否启用 SSL 拦截，默认 True
        cert_dir: CA 证书存储目录
        domain_filter: 域名过滤（子串匹配）
        miniapp_only: 仅捕获小程序请求
        capture_body: 是否捕获请求/响应体
        max_body_size: 最大捕获体大小（字节）
        max_entries: 最大存储条目数
        on_response: 响应完成回调
        auto_system_proxy: 是否自动配置系统代理

    Example::

        server = ProxyServer(port=8080)
        await server.start()
        # ... 抓包 ...
        stats = server.storage.get_stats()
        server.storage.export_har("capture.har")
        await server.stop()
    """

    def __init__(
        self,
        port: int = 8080,
        host: str = "0.0.0.0",
        enable_ssl: bool = True,
        cert_dir: Optional[str | Path] = None,
        domain_filter: Optional[str] = None,
        miniapp_only: bool = False,
        capture_body: bool = True,
        max_body_size: int = 1024 * 1024,
        max_entries: int = 10000,
        on_response: Optional[Callable[[CapturedRequest], None]] = None,
        auto_system_proxy: bool = False,
    ):
        if not _HAS_MITMPROXY:
            raise ImportError(
                "mitmproxy 未安装。请运行: pip install mitmproxy\n"
                "或: pip install xiaotie[proxy]"
            )

        self.port = port
        self.host = host
        self.enable_ssl = enable_ssl
        self.domain_filter = domain_filter
        self.miniapp_only = miniapp_only
        self.capture_body = capture_body
        self.max_body_size = max_body_size
        self.on_response = on_response
        self.auto_system_proxy = auto_system_proxy

        # 组件
        self.cert_manager = CertManager(cert_dir)
        self.storage = RequestStorage(max_entries=max_entries)

        # 内部状态
        self.is_running = False
        self._master: Optional[DumpMaster] = None
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[float] = None
        self._addon = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> dict[str, Any]:
        """启动代理服务器

        Returns:
            包含 port, host, ssl, cert_dir 等信息的字典
        """
        if self.is_running:
            return {"status": "already_running", "port": self.port}

        # 确保证书目录
        self.cert_manager.ensure_ca()

        # 构建 mitmproxy 选项
        opts = options.Options(
            listen_host=self.host,
            listen_port=self.port,
            confdir=self.cert_manager.get_confdir(),
        )
        if self.enable_ssl:
            opts.update(ssl_insecure=True)

        self._master = DumpMaster(opts)

        # 添加捕获插件
        from .addons import RequestCapture, MiniAppFilter

        if self.miniapp_only:
            self._addon = MiniAppFilter(
                self.storage,
                capture_body=self.capture_body,
            )
        else:
            self._addon = RequestCapture(
                self.storage,
                domain_filter=self.domain_filter,
                on_response=self.on_response,
                capture_body=self.capture_body,
                max_body_size=self.max_body_size,
            )

        self._master.addons.add(self._addon)

        # 后台运行
        self._task = asyncio.create_task(self._run_master())
        self.is_running = True
        self._start_time = time.time()

        # 自动配置系统代理
        if self.auto_system_proxy:
            await self._configure_system_proxy()

        info = {
            "status": "started",
            "host": self.host,
            "port": self.port,
            "ssl": self.enable_ssl,
            "cert_dir": str(self.cert_manager.cert_dir),
            "miniapp_only": self.miniapp_only,
        }
        logger.info("代理服务器已启动: %s:%d (SSL=%s)", self.host, self.port, self.enable_ssl)
        return info

    async def stop(self) -> dict[str, Any]:
        """停止代理服务器

        Returns:
            包含 captured_count, uptime 等信息的字典
        """
        if not self.is_running:
            return {"status": "not_running"}

        captured_count = self.storage.count
        uptime = int(time.time() - self._start_time) if self._start_time else 0

        # 恢复系统代理
        if self.auto_system_proxy:
            await self._restore_system_proxy()

        # 关闭 mitmproxy
        if self._master:
            self._master.shutdown()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.is_running = False
        self._master = None
        self._task = None
        self._start_time = None

        info = {
            "status": "stopped",
            "captured_count": captured_count,
            "uptime_seconds": uptime,
        }
        logger.info("代理服务器已停止 (捕获 %d 条, 运行 %ds)", captured_count, uptime)
        return info

    async def _run_master(self) -> None:
        """在后台运行 mitmproxy master"""
        try:
            await self._master.run()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("代理服务器运行异常: %s", e)
            self.is_running = False

    # ------------------------------------------------------------------
    # 状态与数据
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """获取代理服务器状态"""
        status = {
            "running": self.is_running,
            "host": self.host,
            "port": self.port,
            "ssl_enabled": self.enable_ssl,
            "miniapp_only": self.miniapp_only,
            "captured_count": self.storage.count,
        }
        if self._start_time:
            status["uptime_seconds"] = int(time.time() - self._start_time)
        if self.domain_filter:
            status["domain_filter"] = self.domain_filter
        return status

    def get_captured_flows(self) -> list[dict[str, Any]]:
        """获取捕获的流量数据（字典列表）"""
        return [e.to_dict() for e in self.storage.get_all()]

    def clear_captured_flows(self) -> None:
        """清空捕获的流量数据"""
        self.storage.clear()

    def set_filter_rules(self, rules: list[str]) -> None:
        """设置 URL 过滤规则"""
        if self._addon and hasattr(self._addon, "set_filter_rules"):
            self._addon.set_filter_rules(rules)

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export(self, path: str | Path, fmt: str = "json") -> Path:
        """导出捕获数据

        Args:
            path: 输出文件路径
            fmt: 格式 - json 或 har

        Returns:
            导出的文件路径
        """
        if fmt == "har":
            return self.storage.export_har(path)
        return self.storage.export_json(path)

    # ------------------------------------------------------------------
    # 系统代理配置
    # ------------------------------------------------------------------

    async def _configure_system_proxy(self) -> None:
        """配置系统代理"""
        system = platform.system()
        try:
            if system == "Darwin":
                services = await self._get_network_services()
                for svc in services:
                    subprocess.run(
                        ["networksetup", "-setwebproxy", svc, "127.0.0.1", str(self.port)],
                        check=False, capture_output=True,
                    )
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxy", svc, "127.0.0.1", str(self.port)],
                        check=False, capture_output=True,
                    )
            elif system == "Linux":
                os.environ["http_proxy"] = f"http://127.0.0.1:{self.port}"
                os.environ["https_proxy"] = f"http://127.0.0.1:{self.port}"
            logger.info("系统代理已配置: 127.0.0.1:%d", self.port)
        except Exception as e:
            logger.warning("配置系统代理失败: %s", e)

    async def _restore_system_proxy(self) -> None:
        """恢复系统代理"""
        system = platform.system()
        try:
            if system == "Darwin":
                services = await self._get_network_services()
                for svc in services:
                    subprocess.run(
                        ["networksetup", "-setwebproxystate", svc, "off"],
                        check=False, capture_output=True,
                    )
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxystate", svc, "off"],
                        check=False, capture_output=True,
                    )
            elif system == "Linux":
                os.environ.pop("http_proxy", None)
                os.environ.pop("https_proxy", None)
            logger.info("系统代理已恢复")
        except Exception as e:
            logger.warning("恢复系统代理失败: %s", e)

    @staticmethod
    async def _get_network_services() -> list[str]:
        """获取 macOS 网络服务列表"""
        result = subprocess.run(
            ["networksetup", "-listallnetworkservices"],
            capture_output=True, text=True,
        )
        return [
            s for s in result.stdout.split("\n")[1:]
            if s and not s.startswith("*")
        ]

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ProxyServer":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()
