"""
自动化模块

支持通过Appium自动化操作移动端应用，以及macOS原生微信自动化。
"""

__all__ = [
    "AppiumDriver",
    "MiniAppAutomation",
]

# 延迟导入，避免appium硬依赖阻塞整个模块
def get_appium_driver():
    """获取Appium驱动（延迟导入）"""
    from .appium_driver import AppiumDriver
    return AppiumDriver

def get_miniapp_automation():
    """获取小程序自动化（延迟导入）"""
    from .miniapp_automation import MiniAppAutomation
    return MiniAppAutomation

# macOS原生自动化（延迟导入）
def get_macos_module():
    """获取macOS自动化模块"""
    from . import macos
    return macos

# 为了向后兼容，提供懒加载属性
def __getattr__(name):
    if name == "AppiumDriver":
        return get_appium_driver()
    elif name == "MiniAppAutomation":
        return get_miniapp_automation()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
