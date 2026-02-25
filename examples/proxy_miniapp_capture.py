#!/usr/bin/env python3
"""内置代理小程序抓包完整示例

演示如何使用 ProxyServerTool 进行小程序网络请求抓包、
数据分析和自动化脚本编写。无需安装 Charles 等外部工具。

使用方法：
    # 完整交互式抓包流程
    python examples/proxy_miniapp_capture.py

    # 快速启动代理
    python examples/proxy_miniapp_capture.py --quick

    # 自动化抓包（指定时长）
    python examples/proxy_miniapp_capture.py --auto --duration 60

    # 过滤特定域名 + HTTPS 解密
    python examples/proxy_miniapp_capture.py --domain api.weixin.qq.com --ssl

    # 分析已有的抓包数据
    python examples/proxy_miniapp_capture.py --analyze capture.json
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

from xiaotie.tools.proxy_tool import ProxyServerTool


# ---------------------------------------------------------------------------
# 示例 1：完整的交互式抓包流程
# ---------------------------------------------------------------------------

async def interactive_capture(
    port: int = 8080,
    domain: str | None = None,
    ssl_decrypt: bool = False,
):
    """交互式抓包流程

    引导用户完成：启动代理 -> 配置设备 -> 抓包 -> 导出 -> 分析 -> 停止
    """
    proxy = ProxyServerTool()
    separator = "=" * 60

    print(separator)
    print("  小铁内置代理 - 小程序抓包工具")
    print(separator)

    print("\n[1/7] 检查代理状态...")
    status = await proxy.execute(action="status")
    print(f"  {status.content.strip()}")

    print("\n[2/7] 启动内置代理...")
    start_kw: dict = {"action": "start", "port": port, "ssl_decrypt": ssl_decrypt}
    if domain:
        start_kw["filter_domain"] = domain
    result = await proxy.execute(**start_kw)
    if not result.success:
        print(f"  启动失败: {result.error}")
        return
    print(f"  {result.content}")

    if ssl_decrypt:
        print("\n[3/7] 导出 CA 证书...")
        cert_result = await proxy.execute(action="export_cert", output_file="xiaotie-ca.pem")
        print(f"  {cert_result.content}")
        print("  请在设备上安装并信任此证书（详见文档）")
    else:
        print("\n[3/7] 跳过证书导出（未启用 HTTPS 解密）")

    print(f"\n[4/7] 请配置小程序设备代理")
    print(f"  - 代理地址: <本机IP>:{port}")
    print("  - iOS: 设置 -> Wi-Fi -> 代理 -> 手动")
    print("  - Android: 设置 -> WLAN -> 代理 -> 手动")
    print("  - 微信开发者工具: 设置 -> 代理设置 -> 手动")
    print("\n  配置完成后按回车继续...")
    input()

    print("[5/7] 抓包进行中...")
    print("  请在小程序中进行操作")
    print("  完成操作后按回车继续...")
    input()

    print("[6/7] 导出并分析抓包数据...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"miniapp_capture_{timestamp}.json"
    export_result = await proxy.execute(action="export", output_file=filename)
    print(f"  {export_result.content.strip()}")

    analyze_result = await proxy.execute(action="analyze")
    print(f"\n{analyze_result.content}")

    miniapp_result = await proxy.execute(
        action="filter_miniapp",
        output_file=f"miniapp_filtered_{timestamp}.json",
    )
    print(f"\n{miniapp_result.content}")

    print("\n[7/7] 停止代理...")
    result = await proxy.execute(action="stop")
    print(f"  {result.content}")

    print(f"\n{separator}")
    print(f"  抓包完成！数据已保存到 {filename}")
    print(separator)


# ---------------------------------------------------------------------------
# 示例 2：自动化定时抓包
# ---------------------------------------------------------------------------

async def auto_capture(
    port: int = 8080,
    duration: int = 60,
    domain: str | None = None,
    ssl_decrypt: bool = False,
):
    """自动化定时抓包：启动代理 -> 等待指定时长 -> 导出分析 -> 停止"""
    proxy = ProxyServerTool()

    print(f"自动抓包模式：端口 {port}，时长 {duration} 秒")
    if domain:
        print(f"过滤域名：{domain}")

    start_kw: dict = {"action": "start", "port": port, "ssl_decrypt": ssl_decrypt}
    if domain:
        start_kw["filter_domain"] = domain
    result = await proxy.execute(**start_kw)
    if not result.success:
        print(f"启动失败: {result.error}")
        return

    print("代理已启动，开始抓包...")
    try:
        for remaining in range(duration, 0, -1):
            print(f"\r  剩余时间: {remaining} 秒  ", end="", flush=True)
            await asyncio.sleep(1)
        print()
    except KeyboardInterrupt:
        print("\n  用户中断")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"auto_capture_{timestamp}.json"
    await proxy.execute(action="export", output_file=filename)
    print(f"数据导出: {filename}")

    analyze_result = await proxy.execute(action="analyze")
    print(f"\n{analyze_result.content}")

    await proxy.execute(action="stop")
    print("代理已停止")


# ---------------------------------------------------------------------------
# 示例 3：快速启动（持续运行直到 Ctrl+C）
# ---------------------------------------------------------------------------

async def quick_start(port: int = 8080, ssl_decrypt: bool = False):
    """快速启动代理，按 Ctrl+C 自动导出数据并停止"""
    proxy = ProxyServerTool()

    result = await proxy.execute(action="start", port=port, ssl_decrypt=ssl_decrypt)
    if not result.success:
        print(f"启动失败: {result.error}")
        return

    print(f"内置代理已启动（端口 {port}）")
    if ssl_decrypt:
        print("HTTPS 解密已启用")
    print("按 Ctrl+C 停止并导出数据...\n")

    try:
        while True:
            await asyncio.sleep(10)
            status = await proxy.execute(action="status")
            if status.success and "运行中" in status.content:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\n\n导出数据...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        await proxy.execute(action="export", output_file=f"quick_capture_{timestamp}.json")
        print("停止代理...")
        await proxy.execute(action="stop")
        print("已停止")


# ---------------------------------------------------------------------------
# 示例 4：数据分析辅助函数
# ---------------------------------------------------------------------------

def analyze_capture_file(filepath: str):
    """分析抓包导出的 JSON 数据"""
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在: {filepath}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict) and "log" in data:
        entries = data["log"].get("entries", [])
    else:
        entries = data.get("entries", [data] if isinstance(data, dict) else [])

    print(f"\n抓包数据分析: {filepath}")
    print("-" * 50)
    print(f"总请求数: {len(entries)}")

    if not entries:
        print("无请求数据")
        return

    domains: dict[str, int] = {}
    methods: dict[str, int] = {}
    status_codes: dict[str, int] = {}

    for req in entries:
        host = req.get("host", req.get("request", {}).get("host", "unknown"))
        method = req.get("method", req.get("request", {}).get("method", "unknown"))
        status = str(req.get("status", req.get("response", {}).get("status", "unknown")))
        domains[host] = domains.get(host, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        status_codes[status] = status_codes.get(status, 0) + 1

    print("\n域名分布:")
    for d, c in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {d}: {c} 次")
    print("\n请求方法:")
    for m, c in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {m}: {c} 次")
    print("\n状态码分布:")
    for s, c in sorted(status_codes.items()):
        print(f"  {s}: {c} 次")


# ---------------------------------------------------------------------------
# 示例 5：Agent 集成使用
# ---------------------------------------------------------------------------

async def agent_integration_example():
    """展示如何在 xiaotie Agent 中集成 ProxyServerTool"""
    try:
        from xiaotie import create_agent
    except ImportError:
        print("需要完整安装 xiaotie: pip install -e .")
        return

    from xiaotie.tools import ProxyServerTool as PST

    agent = create_agent(provider="anthropic", tools=[PST()])

    print("Agent 集成示例（需要 LLM API key）：")
    print('  await agent.run("启动内置代理，端口 8080，开启 HTTPS 解密")')
    print('  await agent.run("查看代理状态和已捕获的请求")')
    print('  await agent.run("导出小程序请求到 wechat.json 并分析")')
    print('  await agent.run("停止代理")')


# ---------------------------------------------------------------------------
# 示例 6：批量多域名抓包
# ---------------------------------------------------------------------------

async def batch_capture(domains: list[str], port: int = 8080):
    """批量抓取多个域名的请求，每个域名抓取 30 秒"""
    proxy = ProxyServerTool()

    for domain in domains:
        print(f"\n--- 抓取 {domain} ---")
        await proxy.execute(action="start", port=port, filter_domain=domain, ssl_decrypt=True)
        await asyncio.sleep(30)
        safe_name = domain.replace(".", "_")
        await proxy.execute(action="export", output_file=f"capture_{safe_name}.json")
        await proxy.execute(action="stop")
        await asyncio.sleep(1)

    print("\n批量抓包完成！")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="小铁内置代理 - 小程序抓包示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                              # 交互式抓包
  %(prog)s --quick                      # 快速启动代理
  %(prog)s --quick --ssl                # 快速启动 + HTTPS 解密
  %(prog)s --auto --duration 60         # 自动抓包 60 秒
  %(prog)s --domain api.weixin.qq.com   # 过滤特定域名
  %(prog)s --analyze capture.json       # 分析抓包数据
  %(prog)s --batch "a.com,b.com,c.com"  # 批量多域名抓包
        """,
    )
    parser.add_argument("--quick", action="store_true", help="快速启动模式")
    parser.add_argument("--auto", action="store_true", help="自动化抓包模式")
    parser.add_argument("--duration", type=int, default=60, help="自动抓包时长（秒，默认 60）")
    parser.add_argument("--port", type=int, default=8080, help="代理端口（默认 8080）")
    parser.add_argument("--domain", type=str, default=None, help="过滤域名")
    parser.add_argument("--ssl", action="store_true", help="启用 HTTPS 解密")
    parser.add_argument("--analyze", type=str, default=None, metavar="FILE", help="分析导出的 JSON 文件")
    parser.add_argument("--agent", action="store_true", help="展示 Agent 集成示例")
    parser.add_argument("--batch", type=str, default=None, help="批量抓包域名（逗号分隔）")

    args = parser.parse_args()

    if args.analyze:
        analyze_capture_file(args.analyze)
    elif args.agent:
        asyncio.run(agent_integration_example())
    elif args.batch:
        domain_list = [d.strip() for d in args.batch.split(",") if d.strip()]
        asyncio.run(batch_capture(domain_list, port=args.port))
    elif args.quick:
        asyncio.run(quick_start(port=args.port, ssl_decrypt=args.ssl))
    elif args.auto:
        asyncio.run(auto_capture(port=args.port, duration=args.duration, domain=args.domain, ssl_decrypt=args.ssl))
    else:
        asyncio.run(interactive_capture(port=args.port, domain=args.domain, ssl_decrypt=args.ssl))


if __name__ == "__main__":
    main()
