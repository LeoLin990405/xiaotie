"""代理服务器集成测试

测试覆盖：
- ProxyServer + RequestStorage 联合工作
- 完整生命周期（启动 -> 捕获 -> 导出 -> 停止）
- HAR 导出格式验证
- 过滤规则端到端测试
- 模块导入与注册
- CertManager 集成
- 边界条件
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.proxy.storage import CapturedRequest, RequestStorage
from xiaotie.proxy.cert_manager import CertManager


# ============================================================
# CertManager 测试
# ============================================================


class TestCertManager:
    """测试证书管理器"""

    def test_init_default(self):
        cm = CertManager()
        assert cm.cert_dir == Path.home() / ".xiaotie" / "certs"

    def test_init_custom_dir(self, tmp_path):
        cert_dir = tmp_path / "my_certs"
        cm = CertManager(cert_dir)
        assert cm.cert_dir == cert_dir
        assert cert_dir.exists()

    def test_ca_cert_paths(self, tmp_path):
        cm = CertManager(tmp_path / "certs")
        assert cm.ca_cert_path.name == "mitmproxy-ca-cert.pem"
        assert cm.ca_key_path.name == "mitmproxy-ca.pem"
        assert cm.ca_cert_p12.name == "mitmproxy-ca-cert.p12"
        assert cm.ca_cert_cer.name == "mitmproxy-ca-cert.cer"

    def test_has_ca_false(self, tmp_path):
        cm = CertManager(tmp_path / "empty_certs")
        assert cm.has_ca() is False

    def test_has_ca_true(self, tmp_path):
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        (cert_dir / "mitmproxy-ca-cert.pem").write_text("cert")
        (cert_dir / "mitmproxy-ca.pem").write_text("key")
        cm = CertManager(cert_dir)
        assert cm.has_ca() is True

    def test_ensure_ca_already_exists(self, tmp_path):
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        (cert_dir / "mitmproxy-ca-cert.pem").write_text("cert")
        (cert_dir / "mitmproxy-ca.pem").write_text("key")
        cm = CertManager(cert_dir)
        assert cm.ensure_ca() is True

    def test_ensure_ca_no_certs(self, tmp_path):
        cm = CertManager(tmp_path / "empty")
        # 没有 ~/.mitmproxy 也没有已有证书
        with patch("xiaotie.proxy.cert_manager.Path.home", return_value=tmp_path):
            result = cm.ensure_ca()
        # 返回 False 表示将在首次启动时生成
        assert result is False

    def test_get_confdir(self, tmp_path):
        cm = CertManager(tmp_path / "certs")
        assert cm.get_confdir() == str(tmp_path / "certs")

    def test_get_install_instructions(self, tmp_path):
        cm = CertManager(tmp_path / "certs")
        instructions = cm.get_install_instructions("127.0.0.1", 8080)
        assert "SSL" in instructions or "证书" in instructions
        assert "127.0.0.1" in instructions
        assert "8080" in instructions

    def test_export_cert_invalid_format(self, tmp_path):
        cm = CertManager(tmp_path / "certs")
        with pytest.raises(ValueError, match="不支持的格式"):
            cm.export_cert(tmp_path / "out.xyz", fmt="xyz")

    def test_export_cert_not_found(self, tmp_path):
        cm = CertManager(tmp_path / "certs")
        with pytest.raises(FileNotFoundError):
            cm.export_cert(tmp_path / "out.pem", fmt="pem")

    def test_export_cert_success(self, tmp_path):
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        (cert_dir / "mitmproxy-ca-cert.pem").write_text("cert-content")
        cm = CertManager(cert_dir)

        dest = tmp_path / "exported.pem"
        result = cm.export_cert(dest, fmt="pem")
        assert result == dest.resolve()
        assert dest.read_text() == "cert-content"


# ============================================================
# RequestStorage 端到端测试
# ============================================================


class TestStorageEndToEnd:
    """测试 RequestStorage 端到端流程"""

    def test_add_filter_export_cycle(self, tmp_path):
        storage = RequestStorage()

        storage.add(CapturedRequest(
            url="https://api.example.com/v1/users", method="GET",
            host="api.example.com", path="/v1/users", status_code=200,
            response_size=1024, duration_ms=50.0,
        ))
        storage.add(CapturedRequest(
            url="https://servicewechat.com/wx123/data", method="POST",
            host="servicewechat.com", path="/wx123/data", status_code=200,
        ))
        storage.add(CapturedRequest(
            url="https://weixin.qq.com/cgi-bin/token", method="GET",
            host="weixin.qq.com", path="/cgi-bin/token", status_code=200,
        ))

        # 过滤小程序
        miniapp = storage.filter_miniapp()
        assert len(miniapp) == 2

        # 导出 JSON
        json_path = tmp_path / "all.json"
        storage.export_json(json_path)
        data = json.loads(json_path.read_text())
        assert len(data) == 3

        # 导出 HAR
        har_path = tmp_path / "all.har"
        storage.export_har(har_path)
        har = json.loads(har_path.read_text())
        assert len(har["log"]["entries"]) == 3

        # 统计
        stats = storage.get_stats()
        assert stats["total"] == 3

    def test_har_export_valid_format(self, tmp_path):
        storage = RequestStorage()
        storage.add(CapturedRequest(
            url="https://api.example.com/test", method="POST",
            host="api.example.com", path="/test", status_code=201,
            request_headers={"Content-Type": "application/json"},
            response_headers={"X-Request-Id": "abc123"},
            request_body=b'{"key": "value"}', response_body=b'{"id": 1}',
            request_size=16, response_size=8, duration_ms=75.5,
            timestamp=1700000000.0,
        ))

        out = tmp_path / "valid.har"
        storage.export_har(out)
        har = json.loads(out.read_text())

        log = har["log"]
        assert log["version"] == "1.2"
        assert log["creator"]["name"] == "xiaotie-proxy"

        entry = log["entries"][0]
        assert entry["time"] == 75.5
        assert entry["request"]["method"] == "POST"
        assert entry["response"]["status"] == 201


# ============================================================
# ProxyServer 生命周期集成测试
# ============================================================


class TestProxyServerLifecycle:
    """测试 ProxyServer 完整生命周期"""

    @pytest.mark.asyncio
    async def test_start_capture_stop(self):
        from xiaotie.proxy.proxy_server import ProxyServer
        server = ProxyServer(port=18080)

        # 模拟启动状态
        server.is_running = True
        server._start_time = time.time()

        # 手动添加数据到 storage
        server.storage.add(CapturedRequest(
            url="https://test.com/api", host="test.com",
            method="GET", status_code=200,
        ))

        status = server.get_status()
        assert status["running"] is True
        assert status["captured_count"] == 1

        # 停止
        server._master = None
        server._task = None
        result = await server.stop()
        assert result["status"] == "stopped"
        assert server.is_running is False

    @pytest.mark.asyncio
    async def test_double_stop_safe(self):
        from xiaotie.proxy.proxy_server import ProxyServer
        server = ProxyServer()
        await server.stop()
        await server.stop()
        assert server.is_running is False


# ============================================================
# 模块导入集成测试
# ============================================================


class TestModuleImports:
    """测试模块导入和注册"""

    def test_proxy_package_exports(self):
        from xiaotie.proxy import CapturedRequest, RequestStorage, CertManager
        assert CapturedRequest is not None
        assert RequestStorage is not None
        assert CertManager is not None

    def test_session_storage_alias(self):
        from xiaotie.proxy import SessionStorage
        assert SessionStorage is RequestStorage

    def test_storage_importable(self):
        from xiaotie.proxy.storage import CapturedRequest, RequestStorage
        assert CapturedRequest is not None

    def test_cert_manager_importable(self):
        from xiaotie.proxy.cert_manager import CertManager
        assert CertManager is not None

    def test_proxy_tool_importable(self):
        from xiaotie.tools.proxy_tool import ProxyServerTool
        assert ProxyServerTool is not None

    def test_cross_module_miniapp_domains(self):
        from xiaotie.proxy.addons import MINIAPP_DOMAINS as addon_domains
        from xiaotie.proxy.storage import RequestStorage
        # addons 可能有更多域名，但 storage 的域名应是 addons 的子集
        for domain in RequestStorage.MINIAPP_DOMAINS:
            assert domain in addon_domains


# ============================================================
# 边界条件测试
# ============================================================


class TestEdgeCases:

    def test_large_number_of_entries(self):
        storage = RequestStorage(max_entries=10000)
        for i in range(1000):
            storage.add(CapturedRequest(
                url=f"https://example.com/{i}", host="example.com",
                method="GET", status_code=200,
            ))
        assert storage.count == 1000

    def test_unicode_in_urls(self):
        storage = RequestStorage()
        storage.add(CapturedRequest(url="https://example.com/api?q=你好", host="example.com"))
        assert "你好" in storage.get_all()[0].url

    def test_empty_response_body_export(self, tmp_path):
        storage = RequestStorage()
        storage.add(CapturedRequest(
            url="https://example.com/empty", host="example.com",
            status_code=204, response_body=b"",
        ))
        out = tmp_path / "empty_body.json"
        storage.export_json(out)
        data = json.loads(out.read_text())
        assert data[0]["response_body"] == ""
