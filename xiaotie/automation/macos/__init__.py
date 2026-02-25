"""macOS微信自动化模块

通过AppleScript和Accessibility API实现macOS原生微信自动化。
支持微信窗口控制、小程序操作、代理集成。
"""

from .wechat_controller import WeChatController, WeChatConfig, WeChatState
from .miniapp_controller import MiniAppController, MiniAppInfo
from .proxy_integration import ProxyIntegration, AutomationSession

__all__ = [
    "WeChatController",
    "WeChatConfig",
    "WeChatState",
    "MiniAppController",
    "MiniAppInfo",
    "ProxyIntegration",
    "AutomationSession",
]
