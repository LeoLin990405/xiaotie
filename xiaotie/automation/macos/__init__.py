"""macOS微信自动化模块

通过AppleScript和Accessibility API实现macOS原生微信自动化。
支持微信窗口控制、小程序操作、代理集成。
"""

from .miniapp_controller import MiniAppController, MiniAppInfo
from .proxy_integration import AutomationSession, ProxyIntegration
from .wechat_controller import WeChatConfig, WeChatController, WeChatState

__all__ = [
    "WeChatController",
    "WeChatConfig",
    "WeChatState",
    "MiniAppController",
    "MiniAppInfo",
    "ProxyIntegration",
    "AutomationSession",
]
