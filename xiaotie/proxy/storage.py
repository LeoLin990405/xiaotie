"""请求数据存储与 HAR 导出

提供请求/响应数据的内存存储、JSON/HAR 格式导出、
按域名/路径/状态码过滤等功能。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class CapturedRequest:
    """捕获的单条请求记录"""

    url: str
    method: str = "GET"
    host: str = ""
    path: str = "/"
    scheme: str = "https"
    port: int = 443

    # 请求
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: bytes = b""
    request_content_type: str = ""

    # 响应
    status_code: int = 0
    reason: str = ""
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""
    response_content_type: str = ""

    # 时间
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    # 大小
    request_size: int = 0
    response_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化的字典（排除 bytes 字段）"""
        d = asdict(self)
        d["request_body"] = self.request_body.decode("utf-8", errors="replace")
        d["response_body"] = self.response_body.decode("utf-8", errors="replace")
        return d


class RequestStorage:
    """请求数据存储

    线程安全的内存存储，支持过滤和导出。

    Args:
        max_entries: 最大存储条目数，0 表示不限制
    """

    def __init__(self, max_entries: int = 10000):
        self._entries: list[CapturedRequest] = []
        self._max_entries = max_entries

    @property
    def count(self) -> int:
        return len(self._entries)

    def add(self, entry: CapturedRequest) -> None:
        """添加一条请求记录"""
        if self._max_entries > 0 and len(self._entries) >= self._max_entries:
            self._entries.pop(0)
        self._entries.append(entry)

    def clear(self) -> None:
        """清空所有记录"""
        self._entries.clear()

    def get_all(self) -> list[CapturedRequest]:
        """获取所有记录"""
        return list(self._entries)

    def filter(
        self,
        *,
        domain: Optional[str] = None,
        path_prefix: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        min_status: Optional[int] = None,
        max_status: Optional[int] = None,
    ) -> list[CapturedRequest]:
        """按条件过滤请求"""
        results = self._entries
        if domain:
            results = [e for e in results if domain in e.host]
        if path_prefix:
            results = [e for e in results if e.path.startswith(path_prefix)]
        if method:
            results = [e for e in results if e.method.upper() == method.upper()]
        if status_code is not None:
            results = [e for e in results if e.status_code == status_code]
        if min_status is not None:
            results = [e for e in results if e.status_code >= min_status]
        if max_status is not None:
            results = [e for e in results if e.status_code <= max_status]
        return list(results)

    # ------------------------------------------------------------------
    # 小程序域名过滤
    # ------------------------------------------------------------------

    MINIAPP_DOMAINS = (
        "servicewechat.com",
        "weixin.qq.com",
        "wx.qq.com",
        "qlogo.cn",
        "weixinbridge.com",
        "wxaapi.weixin.qq.com",
    )

    def filter_miniapp(self) -> list[CapturedRequest]:
        """过滤微信小程序相关请求"""
        return [
            e for e in self._entries
            if any(d in e.host for d in self.MINIAPP_DOMAINS)
        ]

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def export_json(self, path: str | Path) -> Path:
        """导出为 JSON 格式"""
        out = Path(path).resolve()
        data = [e.to_dict() for e in self._entries]
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("已导出 %d 条请求到 %s (JSON)", len(data), out)
        return out

    def export_har(self, path: str | Path) -> Path:
        """导出为 HAR 1.2 格式"""
        out = Path(path).resolve()
        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "xiaotie-proxy", "version": "1.0"},
                "entries": [self._to_har_entry(e) for e in self._entries],
            }
        }
        out.write_text(json.dumps(har, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("已导出 %d 条请求到 %s (HAR)", len(self._entries), out)
        return out

    @staticmethod
    def _to_har_entry(entry: CapturedRequest) -> dict[str, Any]:
        """将 CapturedRequest 转为 HAR entry"""
        started = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc).isoformat()
        req_headers = [{"name": k, "value": v} for k, v in entry.request_headers.items()]
        resp_headers = [{"name": k, "value": v} for k, v in entry.response_headers.items()]

        return {
            "startedDateTime": started,
            "time": entry.duration_ms,
            "request": {
                "method": entry.method,
                "url": entry.url,
                "httpVersion": "HTTP/1.1",
                "headers": req_headers,
                "queryString": [],
                "headersSize": -1,
                "bodySize": entry.request_size,
            },
            "response": {
                "status": entry.status_code,
                "statusText": entry.reason,
                "httpVersion": "HTTP/1.1",
                "headers": resp_headers,
                "content": {
                    "size": entry.response_size,
                    "mimeType": entry.response_content_type or "application/octet-stream",
                    "text": entry.response_body.decode("utf-8", errors="replace"),
                },
                "headersSize": -1,
                "bodySize": entry.response_size,
            },
            "cache": {},
            "timings": {"send": 0, "wait": entry.duration_ms, "receive": 0},
        }

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """生成统计摘要"""
        if not self._entries:
            return {"total": 0}

        from collections import Counter

        domains = Counter(e.host for e in self._entries)
        methods = Counter(e.method for e in self._entries)
        statuses = Counter(str(e.status_code) for e in self._entries)
        total_resp_size = sum(e.response_size for e in self._entries)
        avg_duration = sum(e.duration_ms for e in self._entries) / len(self._entries)

        return {
            "total": len(self._entries),
            "domains": dict(domains.most_common(20)),
            "methods": dict(methods.most_common()),
            "status_codes": dict(statuses.most_common()),
            "total_response_size_kb": round(total_resp_size / 1024, 1),
            "avg_duration_ms": round(avg_duration, 1),
        }


# 向后兼容别名
SessionStorage = RequestStorage
