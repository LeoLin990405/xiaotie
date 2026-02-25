"""
自动化模块

支持通过Appium自动化操作移动端应用，以及macOS原生微信自动化。
"""

from .appium_driver import AppiumDriver
from .miniapp_automation import MiniAppAutomation

__all__ = [
    "AppiumDriver",
    "MiniAppAutomation",
]

# macOS原生自动化（延迟导入）
def get_macos_module():
    """获取macOS自动化模块"""
    from . import macos
    return macos
