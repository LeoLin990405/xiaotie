"""mitmproxy 插件 - 单元测试

测试覆盖：
- RequestCapture addon
  - 初始化与参数
  - 请求/响应捕获
  - 域名/路径/URL 过滤
  - 请求体捕获控制
  - 回调函数
  - 错误处理
- MiniAppFilter addon
  - 小程序域名过滤
  - 额外域名支持
  - 非小程序请求忽略
- MINIAPP_DOMAINS 常量
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from xiaotie.proxy.addons import (
    MINIAPP_DOMAINS,
    MiniAppFilter,
    RequestCapture,
)
from xiaotie.proxy.storage import CapturedRequest, RequestStorage


def _make_flow(
    url: str = "https://example.com/api",
    method: str = "GET",
    host: str = "example.com",
    path: str = "/api",
    scheme: str = "https",
    port: int = 443,
    status_code: int = 200,
    request_content: bytes = b"",
    response_content: bytes = b"response",
    request_headers: dict | None = None,
    response_headers: dict | None = None,
    flow_id: str = "flow-1",
) -> MagicMock:
    """创建模拟的 mitmproxy HTTPFlow"""
    flow = MagicMock()
    flow.id = flow_id

    req = flow.request
    req.pretty_url = url
    req.pretty_host = host
    req.method = method
    req.host = host
    req.path = path
    req.scheme = scheme
    req.port = port
    req.headers = request_headers or {"Content-Type": "application/json"}
    req.get_content = MagicMock(return_value=request_content)
    req.timestamp_start = time.time()

    resp = flow.response
    resp.status_code = status_code
    resp.reason = "OK"
    resp.headers = response_headers or {"Content-Type": "application/json"}
    resp.get_content = MagicMock(return_value=response_content)

    return flow


# ============================================================
# RequestCapture 测试
# ============================================================


class TestRequestCapture:
    """测试 RequestCapture addon"""

    def test_init(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)
        assert addon.storage is storage
        assert addon.domain_filter is None
        assert addon.path_filter is None
        assert addon.capture_body is True
        assert addon._filter_rules == []

    def test_init_with_filters(self):
        storage = RequestStorage()
        addon = RequestCapture(
            storage,
            domain_filter="example.com",
            path_filter="/api/",
            capture_body=False,
        )
        assert addon.domain_filter == "example.com"
        assert addon.path_filter == "/api/"
        assert addon.capture_body is False

    def test_capture_basic_request(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        flow = _make_flow()
        addon.request(flow)
        addon.response(flow)

        assert storage.count == 1
        entry = storage.get_all()[0]
        assert entry.url == "https://example.com/api"
        assert entry.method == "GET"
        assert entry.host == "example.com"
        assert entry.status_code == 200

    def test_capture_post_request(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        flow = _make_flow(method="POST", request_content=b'{"key": "val"}', status_code=201)
        addon.request(flow)
        addon.response(flow)

        assert storage.count == 1
        entry = storage.get_all()[0]
        assert entry.method == "POST"
        assert entry.status_code == 201
        assert entry.request_body == b'{"key": "val"}'

    def test_capture_multiple(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        for i in range(5):
            flow = _make_flow(url=f"https://example.com/{i}", flow_id=f"flow-{i}")
            addon.request(flow)
            addon.response(flow)

        assert storage.count == 5

    def test_set_filter_rules(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)
        addon.set_filter_rules(["example.com", "test.com"])
        assert addon._filter_rules == ["example.com", "test.com"]

    def test_domain_filter_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, domain_filter="example.com")

        flow = _make_flow(host="example.com")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_domain_filter_no_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, domain_filter="example.com")

        flow = _make_flow(host="other.com", url="https://other.com/api")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_path_filter_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, path_filter="/api/")

        flow = _make_flow(path="/api/users")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_path_filter_no_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, path_filter="/api/")

        flow = _make_flow(path="/other/path")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_url_filter_rules_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)
        addon.set_filter_rules(["example.com"])

        flow = _make_flow(url="https://example.com/api")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_url_filter_rules_no_match(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)
        addon.set_filter_rules(["example.com"])

        flow = _make_flow(url="https://other.com/api", host="other.com")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_empty_filter_rules_captures_all(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)
        addon.set_filter_rules([])

        flow = _make_flow()
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_capture_body_disabled(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, capture_body=False)

        flow = _make_flow(request_content=b"body", response_content=b"resp")
        addon.request(flow)
        addon.response(flow)

        assert storage.count == 1
        entry = storage.get_all()[0]
        assert entry.request_body == b""
        assert entry.response_body == b""

    def test_on_response_callback(self):
        storage = RequestStorage()
        callback_entries = []
        addon = RequestCapture(storage, on_response=lambda e: callback_entries.append(e))

        flow = _make_flow()
        addon.request(flow)
        addon.response(flow)

        assert len(callback_entries) == 1
        assert callback_entries[0].url == "https://example.com/api"

    def test_on_response_callback_exception(self):
        storage = RequestStorage()
        addon = RequestCapture(storage, on_response=lambda e: 1 / 0)

        flow = _make_flow()
        addon.request(flow)
        # 回调异常不应影响捕获
        addon.response(flow)
        assert storage.count == 1

    def test_null_response_ignored(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        flow = _make_flow()
        flow.response = None
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_error_hook(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        flow = _make_flow()
        addon.request(flow)
        # 模拟错误
        flow.error = MagicMock()
        addon.error(flow)
        # flow_start 应被清理
        assert flow.id not in addon._flow_start

    def test_duration_tracking(self):
        storage = RequestStorage()
        addon = RequestCapture(storage)

        flow = _make_flow()
        addon.request(flow)
        # 模拟一些延迟
        addon._flow_start[flow.id] = time.time() - 0.1
        addon.response(flow)

        entry = storage.get_all()[0]
        assert entry.duration_ms >= 90  # 至少 90ms


# ============================================================
# MiniAppFilter 测试
# ============================================================


class TestMiniAppFilter:
    """测试 MiniAppFilter addon"""

    def test_init(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)
        assert addon.storage is storage
        assert addon.capture_body is True

    def test_captures_servicewechat(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        flow = _make_flow(host="servicewechat.com", url="https://servicewechat.com/api")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_captures_weixin_qq(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        flow = _make_flow(host="weixin.qq.com", url="https://weixin.qq.com/api")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_ignores_non_miniapp(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        flow = _make_flow(host="google.com", url="https://google.com/search")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_captures_all_miniapp_domains(self):
        for domain in MINIAPP_DOMAINS:
            storage = RequestStorage()
            addon = MiniAppFilter(storage)

            flow = _make_flow(host=domain, url=f"https://{domain}/api", flow_id=f"flow-{domain}")
            addon.request(flow)
            addon.response(flow)
            assert storage.count == 1, f"域名 {domain} 未被捕获"

    def test_extra_domains(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage, extra_domains=["custom.example.com"])

        flow = _make_flow(host="custom.example.com", url="https://custom.example.com/api")
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 1

    def test_mixed_traffic(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        # 小程序
        f1 = _make_flow(host="servicewechat.com", url="https://servicewechat.com/api", flow_id="f1")
        addon.request(f1)
        addon.response(f1)
        # 非小程序
        f2 = _make_flow(host="google.com", url="https://google.com/search", flow_id="f2")
        addon.request(f2)
        addon.response(f2)
        # 小程序
        f3 = _make_flow(host="wx.qq.com", url="https://wx.qq.com/api", flow_id="f3")
        addon.request(f3)
        addon.response(f3)

        assert storage.count == 2

    def test_null_response_ignored(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        flow = _make_flow(host="servicewechat.com")
        flow.response = None
        addon.request(flow)
        addon.response(flow)
        assert storage.count == 0

    def test_error_hook(self):
        storage = RequestStorage()
        addon = MiniAppFilter(storage)

        flow = _make_flow(host="servicewechat.com")
        addon.request(flow)
        addon.error(flow)
        assert flow.id not in addon._flow_start


# ============================================================
# MINIAPP_DOMAINS 常量测试
# ============================================================


class TestMiniAppDomains:
    """测试小程序域名常量"""

    def test_is_tuple(self):
        assert isinstance(MINIAPP_DOMAINS, tuple)

    def test_contains_key_domains(self):
        assert "servicewechat.com" in MINIAPP_DOMAINS
        assert "weixin.qq.com" in MINIAPP_DOMAINS
        assert "wx.qq.com" in MINIAPP_DOMAINS

    def test_not_empty(self):
        assert len(MINIAPP_DOMAINS) > 0
