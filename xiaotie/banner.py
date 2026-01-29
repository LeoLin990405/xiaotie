"""启动动画模块"""

from __future__ import annotations

import sys
import time
from typing import List, Optional

# 版本号
VERSION = "0.4.2"

# 小铁 Logo - 8球风格像素图案
LOGO_FRAMES = [
    # Frame 1 - 小点
    [
        "   ·    ",
        "  ·⚙·   ",
        "   ·    ",
    ],
    # Frame 2 - 展开
    [
        "  ▄█▄   ",
        " ▐█⚙█▌  ",
        "  ▀█▀   ",
    ],
    # Frame 3 - 最终
    [
        " ▄███▄  ",
        " █ ⚙ █  ",
        " ▀███▀  ",
    ],
]

# 最终静态 Logo - 8球风格 (像台球一样圆润)
STATIC_LOGO = [
    " ▄███▄  ",
    " █ ⚙ █  ",
    " ▀███▀  ",
]

# ANSI 颜色代码
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # 前景色
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    @classmethod
    def supports_color(cls) -> bool:
        """检查终端是否支持颜色"""
        if not hasattr(sys.stdout, "isatty"):
            return False
        if not sys.stdout.isatty():
            return False
        return True


def clear_lines(n: int) -> None:
    """清除 n 行"""
    for _ in range(n):
        sys.stdout.write("\033[A")  # 上移一行
        sys.stdout.write("\033[K")  # 清除该行


def print_banner(
    model: str = "claude-sonnet-4-20250514",
    provider: str = "anthropic",
    workspace: str = ".",
    animate: bool = True,
) -> None:
    """打印启动 banner

    Args:
        model: 模型名称
        provider: 提供商
        workspace: 工作目录
        animate: 是否显示动画
    """
    use_color = Colors.supports_color()

    # 颜色函数
    def cyan(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}" if use_color else text

    def yellow(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}" if use_color else text

    def dim(text: str) -> str:
        return f"{Colors.DIM}{text}{Colors.RESET}" if use_color else text

    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}" if use_color else text

    # 简化模型名称显示
    model_short = model.split("-")[0].title() if "-" in model else model

    # 构建信息行
    info_line1 = f"小铁 XiaoTie v{VERSION}"
    info_line2 = f"{model_short} · {provider.title()}"
    info_line3 = workspace

    if animate and use_color:
        # 动画效果
        for i, frame in enumerate(LOGO_FRAMES):
            # 打印当前帧
            for line in frame:
                print(cyan(line))

            sys.stdout.flush()
            time.sleep(0.15)

            # 清除当前帧（除了最后一帧）
            if i < len(LOGO_FRAMES) - 1:
                clear_lines(len(frame))

        # 清除最后一帧，打印最终版本
        clear_lines(len(LOGO_FRAMES[-1]))

    # 打印最终 Logo 和信息
    print(cyan(STATIC_LOGO[0]) + "   " + bold(info_line1))
    print(cyan(STATIC_LOGO[1]) + "  " + dim(info_line2))
    print(cyan(STATIC_LOGO[2]) + "   " + dim(info_line3))
    print()


def print_status(message: str, status: str = "ok") -> None:
    """打印状态信息

    Args:
        message: 消息内容
        status: 状态类型 (ok, error, warn, info)
    """
    use_color = Colors.supports_color()

    symbols = {
        "ok": ("✓", Colors.GREEN),
        "error": ("✗", "\033[31m"),
        "warn": ("!", Colors.YELLOW),
        "info": ("·", Colors.CYAN),
    }

    symbol, color = symbols.get(status, ("·", Colors.WHITE))

    if use_color:
        print(f"  {color}{symbol}{Colors.RESET} {message}")
    else:
        print(f"  {symbol} {message}")


def print_ready() -> None:
    """打印就绪信息"""
    use_color = Colors.supports_color()

    if use_color:
        print(f"\n{Colors.GREEN}●{Colors.RESET} 小铁已就绪")
    else:
        print("\n● 小铁已就绪")

    print()
