#!/usr/bin/env python3
"""Charles 小程序抓包完整示例

演示如何使用 CharlesProxyTool 进行小程序网络请求抓包、
数据分析和自动化脚本编写。

使用方法：
    # 完整交互式抓包流程
    python examples/charles_miniapp_capture.py

    # 快速启动代理
    python examples/charles_miniapp_capture.py --quick

    # 自动化抓包（指定时长）
    python examples/charles_miniapp_capture.py --auto --duration 60

    # 过滤特定域名
    python examples/charles_miniapp_capture.py --domain api.weixin.qq.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xiaotie.tools.charles_tool import CharlesProxyTool


# ---------------------------------------------------------------------------
# 示例 1：完整的交互式抓包流程
# ---------------------------------------------------------------------------

async def interactive_capture(port: int = 8888, domain: str | None = None):
    """交互式抓包流程

    引导用户完成：启动代理 -> 配置设备 -> 抓包 -> 导出 -> 停止

    Args:
        port: 代理端口，默认 8888
        domain: 过滤域名，None 表示抓取所有请求
    """
    tool = CharlesProxyTool()

    print("=" * 60)
    print("  Charles 小程序抓包工具")
    print("=" * 60)

    # 步骤 1：检查当前状态
    print("\n[1/6] 检查 Charles 状态...")
    status = await tool.execute(action="status")
    print(f"  {status.content.strip()}")

    # 步骤 2：启动代理
    print("\n[2/6] 启动 Charles 代理...")
    kwargs = {"action": "start", "port": port}
    if domain:
        kwargs["filter_domain"] = domain
    result = await tool.execute(**kwargs)
    if not result.success:
        print(f"  启动失败: {result.error}")
        return
    print(f"  {result.content}")

    # 步骤 3：等待用户配置设备
    print("\n[3/6] 请配置小程序设备代理")
    print("  - iOS: 设置 -> Wi-Fi -> 代理 -> 手动")
    print("  - Android: 设置 -> WLAN -> 代理 -> 手动")
    print(f"  - 代理地址: 127.0.0.1:{port}")
    print("\n  配置完成后按回车继续...")
    input()

    # 步骤 4：抓包中
    print("[4/6] 抓包进行中...")
    print("  请在小程序中进行操作")
    print("  完成操作后按回车继续...")
    input()

    # 步骤 5：导出数据
    print("[5/6] 导出抓包数据...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"miniapp_capture_{timestamp}.json"
    result = await tool.execute(action="export", output_file=filename)
    print(f"  {result.content.strip()}")

    # 步骤 6：停止代理
    print("\n[6/6] 停止 Charles 代理...")
    result = await tool.execute(action="stop")
    print(f"  {result.content}")

    print("\n" + "=" * 60)
    print("  抓包完成！")
    print("=" * 60)


# ---------------------------------------------------------------------------
# 示例 2：自动化定时抓包
# ---------------------------------------------------------------------------

async def auto_capture(port: int = 8888, duration: int = 60,
                       domain: str | None = None):
    """自动化定时抓包

    启动代理后自动等待指定时长，然后导出并停止。

    Args:
        port: 代理端口
        duration: 抓包时长（秒）
        domain: 过滤域名
    """
    tool = CharlesProxyTool()

    print(f"自动抓包模式：端口 {port}，时长 {duration} 秒")
    if domain:
        print(f"过滤域名：{domain}")

    # 启动
    kwargs = {"action": "start", "port": port}
    if domain:
        kwargs["filter_domain"] = domain
    result = await tool.execute(**kwargs)
    if not result.success:
        print(f"启动失败: {result.error}")
        return

    print(f"代理已启动，开始抓包...")

    # 等待指定时长
    try:
        for remaining in range(duration, 0, -1):
            print(f"\r  剩余时间: {remaining} 秒  ", end="", flush=True)
            await asyncio.sleep(1)
        print()
    except KeyboardInterrupt:
        print("\n  用户中断")

    # 导出
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"auto_capture_{timestamp}.json"
    await tool.execute(action="export", output_file=filename)
    print(f"数据导出: {filename}")

    # 停止
    await tool.execute(action="stop")
    print("代理已停止")


# ---------------------------------------------------------------------------
# 示例 3：快速启动（持续运行直到 Ctrl+C）
# ---------------------------------------------------------------------------

async def quick_start(port: int = 8888):
    """快速启动 Charles 代理

    启动后持续运行，按 Ctrl+C 停止。

    Args:
        port: 代理端口
    """
    tool = CharlesProxyTool()

    result = await tool.execute(action="start", port=port)
    if not result.success:
        print(f"启动失败: {result.error}")
        return

    print(f"Charles 代理已启动（端口 {port}）")
    print("按 Ctrl+C 停止...\n")

    try:
        while True:
            await asyncio.sleep(10)
            status = await tool.execute(action="status")
            # 仅在运行中时打印心跳
            if status.success and "运行中" in status.content:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\n\n停止代理...")
        await tool.execute(action="stop")
        print("已停止")


# ---------------------------------------------------------------------------
# 示例 4：数据分析辅助函数
# ---------------------------------------------------------------------------

def analyze_capture_file(filepath: str):
    """分析 Charles 导出的 JSON 抓包数据

    读取 Charles 导出的 JSON 文件，统计请求信息。

    Args:
        filepath: Charles 导出的 JSON 文件路径
    """
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在: {filepath}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Charles JSON 导出格式通常是请求列表
    requests = data if isinstance(data, list) else data.get("log", {}).get("entries", [])

    print(f"\n抓包数据分析: {filepath}")
    print(f"{'=' * 50}")
    print(f"总请求数: {len(requests)}")

    if not requests:
        print("无请求数据")
        return

    # 按域名统计
    domains: dict[str, int] = {}
    methods: dict[str, int] = {}
    status_codes: dict[str, int] = {}

    for req in requests:
        # 兼容不同的 Charles 导出格式
        host = req.get("host", req.get("request", {}).get("host", "unknown"))
        method = req.get("method", req.get("request", {}).get("method", "unknown"))
        status = str(req.get("status", req.get("response", {}).get("status", "unknown")))

        domains[host] = domains.get(host, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        status_codes[status] = status_codes.get(status, 0) + 1

    print(f"\n域名分布:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count} 次")

    print(f"\n请求方法:")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count} 次")

    print(f"\n状态码分布:")
    for code, count in sorted(status_codes.items()):
        print(f"  {code}: {count} 次")


# ---------------------------------------------------------------------------
# 示例 5：在 Agent 中集成使用
# ---------------------------------------------------------------------------

async def agent_integration_example():
    """展示如何在 xiaotie Agent 中集成 CharlesProxyTool

    注意：此示例需要配置 LLM provider（如 Anthropic API key）。
    """
    try:
        from xiaotie import create_agent
    except ImportError:
        print("需要完整安装 xiaotie: pip install -e .")
        return

    from xiaotie.tools import CharlesProxyTool

    # 创建带有 Charles 工具的 Agent
    agent = create_agent(
        provider="anthropic",
        tools=[CharlesProxyTool()]
    )

    # Agent 可以通过自然语言控制 Charles
    print("Agent 集成示例（需要 LLM API key）：")
    print('  await agent.run("启动 Charles 代理，端口 8888")')
    print('  await agent.run("查看 Charles 状态")')
    print('  await agent.run("导出抓包数据到 result.json")')
    print('  await agent.run("停止 Charles 代理")')


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Charles 小程序抓包示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 交互式抓包
  %(prog)s --quick                  # 快速启动代理
  %(prog)s --auto --duration 60     # 自动抓包 60 秒
  %(prog)s --domain api.example.com # 过滤特定域名
  %(prog)s --analyze capture.json   # 分析抓包数据
        """
    )
    parser.add_argument("--quick", action="store_true",
                        help="快速启动模式")
    parser.add_argument("--auto", action="store_true",
                        help="自动化抓包模式")
    parser.add_argument("--duration", type=int, default=60,
                        help="自动抓包时长（秒，默认 60）")
    parser.add_argument("--port", type=int, default=8888,
                        help="代理端口（默认 8888）")
    parser.add_argument("--domain", type=str, default=None,
                        help="过滤域名")
    parser.add_argument("--analyze", type=str, default=None,
                        metavar="FILE",
                        help="分析 Charles 导出的 JSON 文件")
    parser.add_argument("--agent", action="store_true",
                        help="展示 Agent 集成示例")

    args = parser.parse_args()

    if args.analyze:
        analyze_capture_file(args.analyze)
    elif args.agent:
        asyncio.run(agent_integration_example())
    elif args.quick:
        asyncio.run(quick_start(port=args.port))
    elif args.auto:
        asyncio.run(auto_capture(
            port=args.port,
            duration=args.duration,
            domain=args.domain
        ))
    else:
        asyncio.run(interactive_capture(
            port=args.port,
            domain=args.domain
        ))


if __name__ == "__main__":
    main()
