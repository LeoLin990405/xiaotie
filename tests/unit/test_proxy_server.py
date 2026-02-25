"""代理服务器核心类 - 单元测试

测试覆盖：
- ProxyServer 初始化与默认值
- 启动/停止生命周期（mock mitmproxy）
- 状态查询
- 流量捕获与清空
- 过滤规则设置
- 导出功能
- 系统代理配置
- 上下文管理器
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.proxy.proxy_server import ProxyServer


# ============================================================
# 初始化测试
# ============================================================


class TestProxyServerInit:
    """测试 ProxyServer 初始化"""

    def test_default_init(self):
        server = ProxyServer()
        assert server.port == 8080
        assert server.host == "0.0.0.0"
        assert server.enable_ssl is True
        assert server.is_running is False
        assert server._master is None
        assert server._task is None
        assert server._start_time is None

    def test_custom_port(self):
        server = ProxyServer(port=9090)
        assert server.port == 9090

    def test_custom_host(self):
        server = ProxyServer(host="127.0.0.1")
        assert server.host == "127.0.0.1"

    def test_disable_ssl(self):
        server = ProxyServer(enable_ssl=False)
        assert server.enable_ssl is False

    def test_custom_cert_dir(self, tmp_path):
        cert_dir = tmp_path / "certs"
        server = ProxyServer(cert_dir=str(cert_dir))
        assert server.cert_manager.cert_dir == cert_dir

    def test_domain_filter(self):
        server = ProxyServer(domain_filter="example.com")
        assert server.domain_filter == "example.com"

    def test_miniapp_only(self):
        server = ProxyServer(miniapp_only=True)
        assert server.miniapp_only is True

    def test_capture_body_default(self):
        server = ProxyServer()
        assert server.capture_body is True

    def test_max_entries(self):
        server = ProxyServer(max_entries=500)
        assert server.storage._max_entries == 500

    def test_auto_system_proxy_default(self):
        server = ProxyServer()
        assert server.auto_system_proxy is False

    def test_storage_initialized(self):
        server = ProxyServer()
        assert server.storage is not None
        assert server.storage.count == 0


# ============================================================
# 启动测试
# ============================================================


class TestProxyServerStart:
    """测试代理服务器启动"""

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        server = ProxyServer()
        server.is_running = True
        result = await server.start()
        assert result["status"] == "already_running"
        assert result["port"] == 8080

    @pytest.mark.asyncio
    async def test_start_success(self):
        server = ProxyServer(port=19999)

        mock_master = MagicMock()
        mock_master.addons = MagicMock()
        mock_master.run = AsyncMock()

        with patch("xiaotie.proxy.proxy_server.DumpMaster", return_value=mock_master), \
             patch("xiaotie.proxy.proxy_server.options.Options"), \
             patch.object(server.cert_manager, "ensure_ca"), \
             patch.object(server.cert_manager, "get_confdir", return_value="/tmp/certs"):
            result = await server.start()

        assert result["status"] == "started"
        assert result["port"] == 19999
        assert server.is_running is True
        assert server._start_time is not None


# ============================================================
# 停止测试
# ============================================================


class TestProxyServerStop:
    """测试代理服务器停止"""

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        server = ProxyServer()
        result = await server.stop()
        assert result["status"] == "not_running"

    @pytest.mark.asyncio
    async def test_stop_running(self):
        server = ProxyServer()
        server.is_running = True
        server._start_time = time.time() - 60
        server._master = MagicMock()

        async def _noop():
            pass

        task = asyncio.ensure_future(_noop())
        await task  # let it complete
        server._task = task

        result = await server.stop()

        assert result["status"] == "stopped"
        assert result["uptime_seconds"] >= 59
        assert server.is_running is False
        assert server._master is None
        assert server._task is None

    @pytest.mark.asyncio
    async def test_stop_task_cancelled_error(self):
        server = ProxyServer()
        server.is_running = True
        server._start_time = time.time()
        server._master = MagicMock()

        async def _hang():
            await asyncio.sleep(999)

        task = asyncio.ensure_future(_hang())
        server._task = task

        result = await server.stop()
        assert result["status"] == "stopped"
        assert server.is_running is False


# ============================================================
# 状态查询测试
# ============================================================


class TestProxyServerStatus:
    """测试状态查询"""

    def test_status_not_running(self):
        server = ProxyServer()
        status = server.get_status()
        assert status["running"] is False
        assert status["port"] == 8080
        assert status["ssl_enabled"] is True
        assert status["captured_count"] == 0
        assert "uptime_seconds" not in status

    def test_status_running(self):
        server = ProxyServer(port=9090)
        server.is_running = True
        server._start_time = time.time() - 60

        status = server.get_status()
        assert status["running"] is True
        assert status["port"] == 9090
        assert status["uptime_seconds"] >= 59

    def test_status_with_domain_filter(self):
        server = ProxyServer(domain_filter="example.com")
        status = server.get_status()
        assert status["domain_filter"] == "example.com"

    def test_status_miniapp_only(self):
        server = ProxyServer(miniapp_only=True)
        status = server.get_status()
        assert status["miniapp_only"] is True


# ============================================================
# 流量数据方法测试
# ============================================================


class TestProxyServerFlows:
    """测试流量数据方法"""

    def test_get_captured_flows_empty(self):
        server = ProxyServer()
        flows = server.get_captured_flows()
        assert flows == []

    def test_clear_captured_flows(self):
        server = ProxyServer()
        from xiaotie.proxy.storage import CapturedRequest
        server.storage.add(CapturedRequest(url="https://example.com"))
        assert server.storage.count == 1
        server.clear_captured_flows()
        assert server.storage.count == 0

    def test_set_filter_rules_no_addon(self):
        server = ProxyServer()
        # 没有 addon 时不应报错
        server.set_filter_rules(["test.com"])


# ============================================================
# 导出测试
# ============================================================


class TestProxyServerExport:
    """测试导出功能"""

    def test_export_json(self, tmp_path):
        server = ProxyServer()
        from xiaotie.proxy.storage import CapturedRequest
        server.storage.add(CapturedRequest(
            url="https://example.com/api", host="example.com",
            method="GET", status_code=200,
        ))

        out = tmp_path / "export.json"
        result = server.export(out, fmt="json")
        assert result.exists()

    def test_export_har(self, tmp_path):
        server = ProxyServer()
        from xiaotie.proxy.storage import CapturedRequest
        server.storage.add(CapturedRequest(
            url="https://example.com/api", host="example.com",
            method="GET", status_code=200,
        ))

        out = tmp_path / "export.har"
        result = server.export(out, fmt="har")
        assert result.exists()


# ============================================================
# _run_master 测试
# ============================================================


class TestRunMaster:
    """测试后台运行 master"""

    @pytest.mark.asyncio
    async def test_run_master_cancelled(self):
        server = ProxyServer()
        mock_master = MagicMock()
        mock_master.run = AsyncMock(side_effect=asyncio.CancelledError)
        server._master = mock_master
        await server._run_master()

    @pytest.mark.asyncio
    async def test_run_master_exception(self):
        server = ProxyServer()
        server.is_running = True
        mock_master = MagicMock()
        mock_master.run = AsyncMock(side_effect=RuntimeError("crash"))
        server._master = mock_master
        await server._run_master()
        assert server.is_running is False


# ============================================================
# 系统代理测试
# ============================================================


class TestSystemProxy:
    """测试系统代理配置"""

    @pytest.mark.asyncio
    async def test_configure_system_proxy_darwin(self):
        server = ProxyServer(port=8888)
        with patch("xiaotie.proxy.proxy_server.platform.system", return_value="Darwin"), \
             patch.object(ProxyServer, "_get_network_services",
                         new_callable=AsyncMock, return_value=["Wi-Fi"]), \
             patch("xiaotie.proxy.proxy_server.subprocess.run") as mock_run:
            await server._configure_system_proxy()
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_restore_system_proxy_darwin(self):
        server = ProxyServer()
        with patch("xiaotie.proxy.proxy_server.platform.system", return_value="Darwin"), \
             patch.object(ProxyServer, "_get_network_services",
                         new_callable=AsyncMock, return_value=["Wi-Fi"]), \
             patch("xiaotie.proxy.proxy_server.subprocess.run") as mock_run:
            await server._restore_system_proxy()
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_configure_proxy_linux(self):
        server = ProxyServer(port=9090)
        import os
        old_http = os.environ.get("http_proxy")
        old_https = os.environ.get("https_proxy")
        try:
            with patch("xiaotie.proxy.proxy_server.platform.system", return_value="Linux"):
                await server._configure_system_proxy()
            assert os.environ.get("http_proxy") == "http://127.0.0.1:9090"
            assert os.environ.get("https_proxy") == "http://127.0.0.1:9090"
        finally:
            if old_http is not None:
                os.environ["http_proxy"] = old_http
            else:
                os.environ.pop("http_proxy", None)
            if old_https is not None:
                os.environ["https_proxy"] = old_https
            else:
                os.environ.pop("https_proxy", None)

    @pytest.mark.asyncio
    async def test_get_network_services(self):
        mock_result = MagicMock()
        mock_result.stdout = "An asterisk...\nWi-Fi\n*Bluetooth\nEthernet\n"
        with patch("xiaotie.proxy.proxy_server.subprocess.run", return_value=mock_result):
            services = await ProxyServer._get_network_services()
        assert "Wi-Fi" in services
        assert "Ethernet" in services
        assert "*Bluetooth" not in services
