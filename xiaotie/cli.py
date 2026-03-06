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
import os
import sys
from pathlib import Path

from .agent import Agent
from .banner import VERSION, print_banner, print_ready, print_status
from .commands import Commands
from .config import Config
from .display import Display, StreamDisplay, set_display
from .input import EnhancedInput
from .llm import LLMClient
from .plugins import PluginManager
from .retry import RetryConfig
from .session import SessionManager
from .tools import (
    AutomationTool,
    BashTool,
    CalculatorTool,
    CharlesProxyTool,
    CodeAnalysisTool,
    EditTool,
    EXTENDED_TOOLS,
    GitTool,
    NetworkTool,
    ProcessManagerTool,
    ProxyServerTool,
    PythonTool,
    ReadTool,
    ScraperTool,
    SystemInfoTool,
    TelegramTool,
    WebFetchTool,
    WebSearchTool,
    WriteTool,
)

# MCP 客户端管理器 (全局，用于清理)
_mcp_manager = None


def start_metrics_server(display: Display):
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


async def load_mcp_tools(config: Config) -> list:
    """加载 MCP 工具"""
    global _mcp_manager

    if not config.mcp.enabled:
        return []

    from .mcp import MCPClientManager, create_mcp_tools

    mcp_tools = []
    _mcp_manager = MCPClientManager()

    for server_name, server_config in config.mcp.servers.items():
        if not server_config.enabled:
            continue

        try:
            client = await _mcp_manager.add_server(
                name=server_name,
                command=server_config.command,
                args=server_config.args,
                env=server_config.env if server_config.env else None,
                cwd=server_config.cwd,
            )

            tools = create_mcp_tools(client, server_name)
            mcp_tools.extend(tools)
            print_status(f"MCP 服务器 '{server_name}': {len(tools)} 个工具", "ok")

        except Exception as e:
            print_status(f"MCP 服务器 '{server_name}' 连接失败: {e}", "error")

    return mcp_tools


async def cleanup_mcp():
    """清理 MCP 连接"""
    global _mcp_manager
    if _mcp_manager:
        await _mcp_manager.disconnect_all()
        _mcp_manager = None


def create_tools(config: Config, workspace: Path) -> list:
    """创建工具列表"""
    tools = []

    if config.tools.enable_file_tools:
        tools.extend(
            [
                ReadTool(workspace_dir=str(workspace)),
                WriteTool(workspace_dir=str(workspace)),
                EditTool(workspace_dir=str(workspace)),
            ]
        )

    if config.tools.enable_bash:
        tools.append(BashTool())

    # 代码工具
    if config.tools.enable_python:
        tools.append(PythonTool())
    if config.tools.enable_calculator:
        tools.append(CalculatorTool())

    # Git 工具
    if config.tools.enable_git:
        tools.append(GitTool(workspace_dir=str(workspace)))

    # Web 工具
    if config.tools.enable_web_tools:
        tools.append(WebSearchTool())
        tools.append(WebFetchTool())

    # 代码分析工具
    if config.tools.enable_code_analysis:
        tools.append(CodeAnalysisTool(workspace_dir=str(workspace)))

    # Charles 代理抓包工具
    if config.tools.enable_charles:
        tools.append(CharlesProxyTool(
            charles_path=config.tools.charles_path,
            proxy_port=config.tools.charles_proxy_port,
        ))

    # 内置代理服务器工具（基于 mitmproxy）
    if config.tools.enable_proxy:
        tools.append(ProxyServerTool(
            proxy_port=config.tools.proxy.port,
            enable_https=config.tools.proxy.enable_https,
            cert_path=config.tools.proxy.cert_path,
            storage_path=config.tools.proxy.storage_path,
        ))

    # 爬虫工具
    if config.tools.enable_scraper:
        tools.append(ScraperTool(
            scraper_dir=config.tools.scraper.scraper_dir,
            max_workers=config.tools.scraper.max_workers,
            request_delay=config.tools.scraper.request_delay,
            num_runs=config.tools.scraper.num_runs,
            stability_threshold=config.tools.scraper.stability_threshold,
        ))

    # macOS 自动化工具
    if config.tools.enable_automation:
        tools.append(AutomationTool(
            wechat_bundle_id=config.tools.automation.wechat_bundle_id,
            screenshot_dir=config.tools.automation.screenshot_dir,
            applescript_timeout=config.tools.automation.applescript_timeout,
        ))

    if config.tools.enable_telegram and config.tools.telegram.bot_token:
        tools.append(
            TelegramTool(
                bot_token=config.tools.telegram.bot_token,
                webhook_host=config.tools.telegram.webhook_host,
                webhook_port=config.tools.telegram.webhook_port,
                webhook_path=config.tools.telegram.webhook_path,
                webhook_secret_token=config.tools.telegram.webhook_secret_token,
                allowed_chat_ids=config.tools.telegram.allowed_chat_ids,
                allowed_cidrs=config.tools.telegram.allowed_cidrs,
            )
        )

    # 扩展工具
    tools.extend(EXTENDED_TOOLS)

    return tools


def load_system_prompt(config: Config) -> str:
    """加载系统提示词"""
    prompt_path = Config.find_config_file(config.agent.system_prompt_path)

    if prompt_path and prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    # 默认提示词
    return """你是小铁，一个智能 AI 助手。

你可以使用以下工具来帮助用户完成任务：
- read_file: 读取文件内容
- write_file: 写入文件
- edit_file: 编辑文件（精确替换）
- bash: 执行 shell 命令
- python: 执行 Python 代码
- calculator: 数学计算
- git: Git 版本控制操作
- web_search: 网络搜索
- web_fetch: 获取网页内容

请用中文回复用户，保持简洁专业。"""


async def _setup_agent(
    config: Config,
    stream: bool = True,
    thinking: bool = True,
    quiet: bool = False,
) -> tuple[Agent, PluginManager, list]:
    """Shared setup: workspace, tools, plugins, MCP, LLM client, Agent.

    Returns (agent, plugin_manager, mcp_tools).
    """
    workspace = Path(config.agent.workspace_dir).absolute()
    workspace.mkdir(parents=True, exist_ok=True)

    # Tools
    tools = create_tools(config, workspace)

    # Plugins
    plugin_mgr = PluginManager()
    plugin_tools = plugin_mgr.load_all_plugins()
    if plugin_tools:
        tools.extend(plugin_tools)

    # MCP
    mcp_tools = await load_mcp_tools(config)
    if mcp_tools:
        tools.extend(mcp_tools)

    # System prompt
    system_prompt = load_system_prompt(config)

    # LLM client
    retry_config = RetryConfig(
        enabled=config.llm.retry.enabled,
        max_retries=config.llm.retry.max_retries,
        initial_delay=config.llm.retry.initial_delay,
        max_delay=config.llm.retry.max_delay,
        exponential_base=config.llm.retry.exponential_base,
    )

    llm_client = LLMClient(
        api_key=config.llm.api_key,
        api_base=config.llm.api_base,
        model=config.llm.model,
        provider=config.llm.provider,
        retry_config=retry_config,
    )

    # Agent
    agent = Agent(
        llm_client=llm_client,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=config.agent.max_steps,
        workspace_dir=str(workspace),
        stream=stream,
        enable_thinking=thinking,
        quiet=quiet,
    )

    return agent, plugin_mgr, mcp_tools


async def interactive_loop(
    agent: Agent,
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


async def main_async(stream: bool = True, thinking: bool = True):
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
        print("\n请创建配置文件 config/config.yaml，示例:")
        print(
            """
api_key: YOUR_API_KEY
api_base: https://api.anthropic.com
model: claude-sonnet-4-20250514
provider: anthropic
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
        action="store_true",
        help="禁用深度思考",
    )
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
                thinking=not args.no_thinking,
            )
        )
        return

    # 交互模式
    asyncio.run(
        main_async(
            stream=not args.no_stream,
            thinking=not args.no_thinking,
        )
    )


async def run_non_interactive(
    prompt: str,
    output_format: str = "text",
    quiet: bool = False,
    stream: bool = True,
    thinking: bool = True,
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
