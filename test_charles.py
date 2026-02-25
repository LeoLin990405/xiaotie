#!/usr/bin/env python3
"""Charles 代理抓包工具测试脚本"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from xiaotie.tools.charles_tool import CharlesProxyTool


async def test_charles_tool():
    """测试 Charles 工具"""
    tool = CharlesProxyTool()

    print("=" * 60)
    print("Charles 代理抓包工具测试")
    print("=" * 60)

    # 1. 查看初始状态
    print("\n1. 查看初始状态...")
    result = await tool.execute(action="status")
    print(f"✓ {result.content}")

    # 2. 启动 Charles 代理
    print("\n2. 启动 Charles 代理...")
    result = await tool.execute(action="start", port=8888)
    if result.success:
        print(f"✓ {result.content}")
    else:
        print(f"✗ 启动失败: {result.error}")
        return

    # 3. 等待用户操作
    print("\n" + "=" * 60)
    print("Charles 代理已启动！")
    print("=" * 60)
    print("\n请按照以下步骤操作：")
    print("\n1. 在小程序设备上配置代理：")
    print("   - HTTP 代理: 127.0.0.1:8888")
    print("   - HTTPS 代理: 127.0.0.1:8888")
    print("\n2. 在小程序中进行操作（发送网络请求）")
    print("\n3. 在 Charles 中查看抓取的请求")
    print("\n4. 按回车键继续...")
    input()

    # 4. 查看运行状态
    print("\n4. 查看运行状态...")
    result = await tool.execute(action="status")
    print(f"✓ {result.content}")

    # 5. 导出说明
    print("\n5. 导出抓包数据...")
    result = await tool.execute(
        action="export",
        output_file="miniapp_capture.json"
    )
    print(f"✓ {result.content}")

    # 6. 停止 Charles 代理
    print("\n6. 停止 Charles 代理...")
    result = await tool.execute(action="stop")
    if result.success:
        print(f"✓ {result.content}")
    else:
        print(f"✗ 停止失败: {result.error}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


async def quick_start():
    """快速启动 Charles 代理"""
    tool = CharlesProxyTool()

    print("启动 Charles 代理...")
    result = await tool.execute(action="start", port=8888)

    if result.success:
        print("\n✓ Charles 代理已启动！")
        print(result.content)
        print("\n按 Ctrl+C 停止代理...")

        try:
            # 保持运行
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n停止 Charles 代理...")
            result = await tool.execute(action="stop")
            print(f"✓ {result.content}")
    else:
        print(f"\n✗ 启动失败: {result.error}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Charles 代理抓包工具测试")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速启动模式（直接启动代理）"
    )
    args = parser.parse_args()

    if args.quick:
        asyncio.run(quick_start())
    else:
        asyncio.run(test_charles_tool())


if __name__ == "__main__":
    main()
