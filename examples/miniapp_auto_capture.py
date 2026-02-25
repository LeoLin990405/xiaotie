#!/usr/bin/env python3
"""小程序自动化抓取 - 完整示例

演示如何使用 xiaotie 的 MiniAppCaptureWorkflow 自动抓取
微信小程序的网络请求数据。

使用方式:
    # 手动模式（不使用自动化，手动操作小程序）
    python miniapp_auto_capture.py --name 美团 --duration 30

    # 批量抓取
    python miniapp_auto_capture.py --name 美团 饿了么 京东 --duration 20

    # 使用 Appium 自动化
    python miniapp_auto_capture.py --name 美团 --engine appium

    # 使用 macOS 原生自动化
    python miniapp_auto_capture.py --name 美团 --engine macos

    # 导出为 HAR 格式
    python miniapp_auto_capture.py --name 美团 --format har

    # 自定义代理端口和输出目录
    python miniapp_auto_capture.py --name 美团 --port 9090 --output ./my_data

前置条件:
    1. 安装 mitmproxy: pip install 'xiaotie[proxy]'
    2. 如使用 Appium: 安装并启动 Appium Server
    3. 如使用 macOS 自动化: 授予终端辅助功能权限
    4. 目标设备/模拟器已配置代理指向本机
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from xiaotie.workflows.miniapp_capture import (
    AutomationEngine,
    CaptureConfig,
    ExportFormat,
    MiniAppCaptureWorkflow,
    MiniAppTarget,
    PageAction,
)


def progress_callback(msg: str) -> None:
    """进度回调 - 打印到控制台"""
    print(f"[xiaotie] {msg}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="小程序自动化抓取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  %(prog)s --name 美团
  %(prog)s --name 美团 饿了么 --duration 20
  %(prog)s --name 美团 --engine appium --format har
  %(prog)s --name 美团 --port 9090 --output ./data
""",
    )
    parser.add_argument(
        "--name", "-n",
        nargs="+",
        required=True,
        help="小程序名称（支持多个，空格分隔）",
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=30.0,
        help="每个小程序的抓取持续时间（秒，默认 30）",
    )
    parser.add_argument(
        "--engine", "-e",
        choices=["none", "macos", "appium"],
        default="none",
        help="自动化引擎（默认 none = 手动模式）",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="代理服务器端口（默认 8080）",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "har"],
        default="json",
        help="导出格式（默认 json）",
    )
    parser.add_argument(
        "--output", "-o",
        default="./capture_output",
        help="输出目录（默认 ./capture_output）",
    )
    parser.add_argument(
        "--scroll-count",
        type=int,
        default=5,
        help="自动滚动次数（默认 5）",
    )
    parser.add_argument(
        "--no-https",
        action="store_true",
        help="禁用 HTTPS 拦截",
    )
    parser.add_argument(
        "--system-proxy",
        action="store_true",
        help="自动配置系统代理",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志输出",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # 配置日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 构建配置
    config = CaptureConfig(
        proxy_port=args.port,
        enable_https=not args.no_https,
        auto_system_proxy=args.system_proxy,
        engine=AutomationEngine(args.engine),
        output_dir=args.output,
        export_format=ExportFormat(args.format),
        scroll_count=args.scroll_count,
        default_capture_duration=args.duration,
    )

    # 构建抓取目标
    targets = [
        MiniAppTarget(
            name=name,
            capture_duration=args.duration,
            export_format=ExportFormat(args.format),
        )
        for name in args.name
    ]

    # 执行工作流
    async with MiniAppCaptureWorkflow(config, on_progress=progress_callback) as workflow:
        if len(targets) == 1:
            result = await workflow.capture_one(targets[0])
            if result.success:
                print(f"\n抓取成功: {result.miniapp_requests} 条小程序请求")
                if result.export_path:
                    print(f"导出文件: {result.export_path}")
            else:
                print(f"\n抓取失败: {result.error}", file=sys.stderr)
                sys.exit(1)
        else:
            results = await workflow.capture_batch(targets)
            failed = [r for r in results if not r.success]
            if failed:
                print(
                    f"\n{len(failed)} 个小程序抓取失败:",
                    file=sys.stderr,
                )
                for r in failed:
                    print(f"  - {r.miniapp_name}: {r.error}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
