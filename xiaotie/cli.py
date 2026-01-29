"""
小铁 CLI 入口

交互式命令行界面 v0.3.0
- 新命令系统（约定优于配置）
- 增强显示（Markdown 渲染、代码高亮）
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .agent import Agent
from .config import Config
from .llm import LLMClient, LLMProvider
from .retry import RetryConfig
from .tools import ReadTool, WriteTool, EditTool, BashTool, PythonTool, CalculatorTool
from .banner import print_banner, print_status, print_ready, VERSION
from .session import SessionManager
from .commands import Commands
from .display import Display, StreamDisplay, get_display, set_display


def create_tools(config: Config, workspace: Path) -> list:
    """创建工具列表"""
    tools = []

    if config.tools.enable_file_tools:
        tools.extend([
            ReadTool(workspace_dir=str(workspace)),
            WriteTool(workspace_dir=str(workspace)),
            EditTool(workspace_dir=str(workspace)),
        ])

    if config.tools.enable_bash:
        tools.append(BashTool())

    # 新增工具
    tools.append(PythonTool())
    tools.append(CalculatorTool())

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

请用中文回复用户，保持简洁专业。"""


async def interactive_loop(agent: Agent, session_mgr: SessionManager, display: Display):
    """交互循环"""
    # 创建命令管理器
    commands = Commands(agent, session_mgr)

    display.info("输入 /help 查看帮助，/quit 退出")
    print()

    while True:
        try:
            # 获取用户输入
            try:
                user_input = display.user_prompt().strip()
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


async def main_async():
    """异步主函数"""
    # 初始化显示
    display = Display()
    set_display(display)

    # 加载配置
    try:
        config = Config.load()
    except (FileNotFoundError, ValueError) as e:
        # 先显示 banner（使用默认值）
        print_banner(workspace=str(Path.cwd()))
        print_status(str(e), "error")
        print("\n请创建配置文件 config/config.yaml，示例:")
        print("""
api_key: YOUR_API_KEY
api_base: https://api.anthropic.com
model: claude-sonnet-4-20250514
provider: anthropic
""")
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

    # 创建工具
    tools = create_tools(config, workspace)
    print_status(f"已加载 {len(tools)} 个工具", "ok")

    # 加载系统提示词
    system_prompt = load_system_prompt(config)

    # 创建 LLM 客户端
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

    # 创建会话管理器
    session_mgr = SessionManager()

    # 创建 Agent
    agent = Agent(
        llm_client=llm_client,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=config.agent.max_steps,
        workspace_dir=str(workspace),
        stream=True,
        enable_thinking=True,
    )

    print_ready()

    # 进入交互循环
    await interactive_loop(agent, session_mgr, display)


def main():
    """主入口"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
