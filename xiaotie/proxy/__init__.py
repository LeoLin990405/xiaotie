"""内置代理服务器模块

基于 mitmproxy 的轻量级代理服务器，用于抓取和分析小程序网络请求。
无需安装 Charles 等外部工具，开箱即用。

主要组件:
    - ProxyServer: 代理服务器核心，管理生命周期
    - RequestCapture: 请求捕获插件
    - MiniAppFilter: 小程序请求过滤插件
    - CertManager: SSL 证书管理
    - RequestStorage: 请求数据存储与 HAR 导出
    - CapturedRequest: 单条请求数据模型
"""

from .storage import CapturedRequest, RequestStorage
from .cert_manager import CertManager

# 向后兼容
SessionStorage = RequestStorage

# ProxyServer 和 addons 需要 mitmproxy，延迟导入
try:
    from .proxy_server import ProxyServer
    from .addons import RequestCapture, MiniAppFilter
except ImportError:
    ProxyServer = None  # type: ignore[assignment,misc]
    RequestCapture = None  # type: ignore[assignment,misc]
    MiniAppFilter = None  # type: ignore[assignment,misc]

__all__ = [
    "ProxyServer",
    "RequestCapture",
    "MiniAppFilter",
    "CertManager",
    "RequestStorage",
    "CapturedRequest",
    "SessionStorage",
]
