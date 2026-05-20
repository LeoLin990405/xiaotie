"""
小铁 CLI 入口

交互式命令行界面 v0.4.0
- 新命令系统（约定优于配置）
- 增强显示（Markdown 渲染、代码高亮）
- 插件系统支持
- TUI 模式支持
- 非交互模式支持
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .banner import VERSION, print_banner, print_ready, print_status
from .commands import Commands
from .config import Config
from .display import Display, StreamDisplay, set_display
from .input import EnhancedInput
from .plugins import PluginManager
from .runtime_setup import cleanup_mcp, setup_runtime
from .session import SessionManager

logger = logging.getLogger(__name__)


def start_metrics_server(display: Display):
    import os

    enabled = os.getenv("XIAOTIE_METRICS_ENABLED", "1").lower() not in {"0", "false", "off"}
    if not enabled:
        return
    host = os.getenv("XIAOTIE_METRICS_HOST", "127.0.0.1")
    port = int(os.getenv("XIAOTIE_METRICS_PORT", "9464"))
    try:
        from prometheus_client import start_http_server

        start_http_server(port=port, addr=host)
        display.info(f"Prometheus 指标地址: http://{host}:{port}/")
    except Exception as e:
        display.warning(f"Prometheus 指标服务启动失败: {e}")


async def _setup_agent(
    config: Config,
    stream: bool = True,
    thinking: bool = False,
    quiet: bool = False,
) -> tuple:
    """Shared setup: workspace, tools, plugins, MCP, LLM client, AgentRuntime.

    Returns (runtime, plugin_manager, mcp_tools).
    """
    setup = await setup_runtime(
        config,
        stream=stream,
        thinking=thinking,
        quiet=quiet,
        status_reporter=print_status,
    )
    return setup.runtime, setup.plugin_manager, setup.mcp_tools


async def interactive_loop(
    agent: AgentRuntime,
    session_mgr: SessionManager,
    plugin_mgr: PluginManager,
    display: Display,
):
    """交互循环"""
    # 创建命令管理器
    commands = Commands(agent, session_mgr, plugin_mgr)

    # 创建增强输入（支持自动补全和历史记录）
    enhanced_input = EnhancedInput(commands=commands)

    display.info("输入 /help 查看帮助，/quit 退出")
    if enhanced_input.use_prompt_toolkit:
        display.info("支持 Tab 补全、↑↓ 历史记录、Ctrl+R 搜索历史")
    print()

    while True:
        try:
            # 获取用户输入（使用异步版本）
            try:
                user_input = (await enhanced_input.prompt_async("\n👤 你: ")).strip()
            except EOFError:
                break

            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                cmd_line = user_input[1:]  # 去掉 /
                should_continue, message = await commands.execute(cmd_line)
                if message:
                    print(message)
                if not should_continue:
                    break
                continue

            # 运行 Agent
            cancel_event = asyncio.Event()
            agent.cancel_event = cancel_event

            # 创建流式显示器
            stream_display = StreamDisplay(display)

            # 设置回调
            agent.on_thinking = stream_display.on_thinking
            agent.on_content = stream_display.on_content

            try:
                await agent.run(user_input)
                stream_display.finish()
            except KeyboardInterrupt:
                cancel_event.set()
                print("\n⚠️ 已取消")

        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except EOFError:
            print("\n\n👋 再见！")
            break


async def main_async(stream: bool = True, thinking: bool = False):
    """异步主函数"""
    # 初始化显示
    display = Display()
    set_display(display)
    start_metrics_server(display)

    # 加载配置
    try:
        config = Config.load()
    except (FileNotFoundError, ValueError) as e:
        # 先显示 banner（使用默认值）
        print_banner(workspace=str(Path.cwd()))
        print_status(str(e), "error")
        print("\n请创建配置文件 config/config.yaml（可从 config/config.yaml.example 复制），示例:")
        print(
            """
llm:
  api_key: YOUR_API_KEY
  api_base: https://token-plan-sgp.xiaomimimo.com/anthropic
  model: mimo-v2-pro
  provider: mimo
"""
        )
        sys.exit(1)

    # 创建工作目录
    workspace = Path(config.agent.workspace_dir).absolute()
    workspace.mkdir(parents=True, exist_ok=True)

    # 显示启动 banner（带动画）
    print_banner(
        model=config.llm.model,
        provider=config.llm.provider,
        workspace=str(workspace),
        animate=True,
    )

    # 显示状态信息
    print_status(f"模型: {config.llm.model}", "info")
    print_status(f"Provider: {config.llm.provider}", "info")
    print_status(f"工作目录: {workspace}", "info")

    # Setup agent (shared logic)
    agent, plugin_mgr, mcp_tools = await _setup_agent(config, stream=stream, thinking=thinking)
    print_status(f"已加载 {len(agent.tools)} 个工具", "ok")

    # 创建会话管理器
    session_mgr = SessionManager()

    print_ready()

    # 进入交互循环
    try:
        await interactive_loop(agent, session_mgr, plugin_mgr, display)
    finally:
        # 清理 MCP 连接
        await cleanup_mcp()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="小铁 - AI 编程助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  xiaotie                    # 启动交互式 CLI
  xiaotie --tui              # 启动 TUI 模式
  xiaotie -p "你好"          # 非交互模式
  xiaotie -p "分析代码" -f json  # JSON 输出
        """,
    )

    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        help="非交互模式：直接执行提示词",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="输出格式 (默认: text)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="安静模式：只输出结果",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="启动 TUI 模式",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="禁用流式输出",
    )
    parser.add_argument(
        "--no-thinking",
        dest="thinking",
        action="store_false",
        help="禁用深度思考",
    )
    parser.add_argument(
        "--thinking",
        dest="thinking",
        action="store_true",
        help="启用深度思考",
    )
    parser.set_defaults(thinking=False)
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"小铁 XiaoTie v{VERSION}",
    )

    args = parser.parse_args()

    # TUI 模式
    if args.tui:
        try:
            from .tui.main import run_tui

            run_tui()
        except ImportError as e:
            print("❌ TUI 模式需要安装 textual: pip install textual")
            print(f"   错误: {e}")
            sys.exit(1)
        return

    # 非交互模式
    if args.prompt:
        asyncio.run(
            run_non_interactive(
                prompt=args.prompt,
                output_format=args.format,
                quiet=args.quiet,
                stream=not args.no_stream,
                thinking=args.thinking,
            )
        )
        return

    # 交互模式
    asyncio.run(
        main_async(
            stream=not args.no_stream,
            thinking=args.thinking,
        )
    )


async def run_non_interactive(
    prompt: str,
    output_format: str = "text",
    quiet: bool = False,
    stream: bool = True,
    thinking: bool = False,
):
    """非交互模式"""
    start_metrics_server(Display())
    # 加载配置
    try:
        config = Config.load()
    except (FileNotFoundError, ValueError) as e:
        if output_format == "json":
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 配置错误: {e}")
        sys.exit(1)

    # Setup agent (shared logic)
    use_stream = stream and not quiet and output_format != "json"
    use_quiet = quiet or output_format == "json"
    agent, _, _ = await _setup_agent(config, stream=use_stream, thinking=thinking, quiet=use_quiet)

    # 运行
    try:
        result = await agent.run(prompt)

        if output_format == "json":
            output = {
                "success": True,
                "result": result,
                "tokens": agent.api_total_tokens,
                "model": config.llm.model,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # 流式模式下内容已经通过回调打印，不需要再打印
            if not use_stream:
                if not quiet:
                    print()
                print(result)

    except Exception as e:
        if output_format == "json":
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 错误: {e}")
        sys.exit(1)
    finally:
        # 清理 MCP 连接
        await cleanup_mcp()


if __name__ == "__main__":
    main()
