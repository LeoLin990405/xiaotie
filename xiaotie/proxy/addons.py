"""mitmproxy 插件

RequestCapture: 捕获所有请求/响应并存入 RequestStorage
MiniAppFilter: 仅捕获微信小程序相关域名的请求
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from .storage import CapturedRequest, RequestStorage

logger = logging.getLogger(__name__)

# 延迟导入 mitmproxy 类型，避免未安装时 import 失败
try:
    from mitmproxy import http

    _HAS_MITMPROXY = True
except ImportError:
    _HAS_MITMPROXY = False


def _check_mitmproxy() -> None:
    if not _HAS_MITMPROXY:
        raise ImportError(
            "mitmproxy 未安装。请运行: pip install mitmproxy\n或: pip install xiaotie[proxy]"
        )


# 微信小程序相关域名
MINIAPP_DOMAINS = (
    "servicewechat.com",
    "weixin.qq.com",
    "wx.qq.com",
    "qlogo.cn",
    "weixinbridge.com",
    "wxaapi.weixin.qq.com",
    "mp.weixin.qq.com",
    "api.weixin.qq.com",
)


class RequestCapture:
    """请求捕获插件

    捕获所有经过代理的 HTTP(S) 请求和响应，
    存入 RequestStorage 供后续分析和导出。

    Args:
        storage: 请求存储实例
        domain_filter: 可选的域名过滤器（子串匹配）
        path_filter: 可选的路径前缀过滤器
        on_response: 响应完成回调 (CapturedRequest) -> None
        capture_body: 是否捕获请求/响应体，默认 True
        max_body_size: 最大捕获体大小（字节），默认 1MB
    """

    def __init__(
        self,
        storage: RequestStorage,
        *,
        domain_filter: Optional[str] = None,
        path_filter: Optional[str] = None,
        on_response: Optional[Callable[[CapturedRequest], None]] = None,
        capture_body: bool = True,
        max_body_size: int = 1024 * 1024,
    ):
        _check_mitmproxy()
        self.storage = storage
        self.domain_filter = domain_filter
        self.path_filter = path_filter
        self.on_response_cb = on_response
        self.capture_body = capture_body
        self.max_body_size = max_body_size
        self._flow_start: dict[str, float] = {}
        self._filter_rules: list[str] = []

    def set_filter_rules(self, rules: list[str]) -> None:
        """设置 URL 过滤规则列表（子串匹配）"""
        self._filter_rules = rules

    def request(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 请求钩子 - 记录请求开始时间"""
        self._flow_start[flow.id] = time.time()

    def response(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 响应钩子 - 捕获完整请求/响应"""
        req = flow.request
        resp = flow.response
        if resp is None:
            return

        host = req.pretty_host
        path = req.path
        url = req.pretty_url

        # 域名过滤
        if self.domain_filter and self.domain_filter not in host:
            return
        # 路径过滤
        if self.path_filter and not path.startswith(self.path_filter):
            return
        # URL 规则过滤
        if self._filter_rules:
            if not any(rule in url for rule in self._filter_rules):
                return

        start_time = self._flow_start.pop(flow.id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        # 请求/响应体
        req_body = b""
        resp_body = b""
        if self.capture_body:
            try:
                raw = req.get_content(limit=self.max_body_size)
                req_body = raw if raw else b""
            except Exception:
                pass
            try:
                raw = resp.get_content(limit=self.max_body_size)
                resp_body = raw if raw else b""
            except Exception:
                pass

        entry = CapturedRequest(
            url=url,
            method=req.method,
            host=host,
            path=path,
            scheme=req.scheme,
            port=req.port,
            request_headers=dict(req.headers),
            request_body=req_body,
            request_content_type=req.headers.get("content-type", ""),
            status_code=resp.status_code,
            reason=resp.reason or "",
            response_headers=dict(resp.headers),
            response_body=resp_body,
            response_content_type=resp.headers.get("content-type", ""),
            timestamp=start_time,
            duration_ms=round(duration_ms, 2),
            request_size=len(req_body),
            response_size=len(resp_body),
        )

        self.storage.add(entry)

        if self.on_response_cb:
            try:
                self.on_response_cb(entry)
            except Exception:
                logger.exception("on_response 回调异常")

    def error(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 错误钩子"""
        self._flow_start.pop(flow.id, None)
        if hasattr(flow, "error") and flow.error:
            logger.debug(
                "请求错误: %s %s - %s", flow.request.method, flow.request.pretty_url, flow.error
            )


class MiniAppFilter:
    """微信小程序请求过滤插件

    仅捕获微信小程序相关域名的请求，其他请求直接放行不捕获。

    Args:
        storage: 请求存储实例
        extra_domains: 额外需要捕获的域名列表
        capture_body: 是否捕获请求/响应体
    """

    def __init__(
        self,
        storage: RequestStorage,
        *,
        extra_domains: Optional[list[str]] = None,
        capture_body: bool = True,
    ):
        _check_mitmproxy()
        self.storage = storage
        self.domains = set(MINIAPP_DOMAINS)
        if extra_domains:
            self.domains.update(extra_domains)
        self.capture_body = capture_body
        self._flow_start: dict[str, float] = {}

    def _is_miniapp_domain(self, host: str) -> bool:
        return any(d in host for d in self.domains)

    def request(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 请求钩子"""
        if self._is_miniapp_domain(flow.request.pretty_host):
            self._flow_start[flow.id] = time.time()

    def response(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 响应钩子 - 仅捕获小程序域名"""
        req = flow.request
        resp = flow.response
        if resp is None:
            return

        host = req.pretty_host
        if not self._is_miniapp_domain(host):
            return

        start_time = self._flow_start.pop(flow.id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        req_body = b""
        resp_body = b""
        if self.capture_body:
            try:
                raw = req.get_content(limit=1024 * 1024)
                req_body = raw if raw else b""
            except Exception:
                pass
            try:
                raw = resp.get_content(limit=1024 * 1024)
                resp_body = raw if raw else b""
            except Exception:
                pass

        entry = CapturedRequest(
            url=req.pretty_url,
            method=req.method,
            host=host,
            path=req.path,
            scheme=req.scheme,
            port=req.port,
            request_headers=dict(req.headers),
            request_body=req_body,
            request_content_type=req.headers.get("content-type", ""),
            status_code=resp.status_code,
            reason=resp.reason or "",
            response_headers=dict(resp.headers),
            response_body=resp_body,
            response_content_type=resp.headers.get("content-type", ""),
            timestamp=start_time,
            duration_ms=round(duration_ms, 2),
            request_size=len(req_body),
            response_size=len(resp_body),
        )

        self.storage.add(entry)

    def error(self, flow: "http.HTTPFlow") -> None:
        """mitmproxy 错误钩子"""
        self._flow_start.pop(flow.id, None)
