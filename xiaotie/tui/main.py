"""小铁 TUI 入口

使用 Textual 构建的现代化终端界面
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..agent import Agent
from ..commands import Commands
from ..config import Config
from ..llm import LLMClient
from ..plugins import PluginManager
from ..retry import RetryConfig
from ..session import SessionManager
from ..tools import (
    BashTool,
    CalculatorTool,
    EditTool,
    GitTool,
    PythonTool,
    ReadTool,
    WebFetchTool,
    WebSearchTool,
    WriteTool,
)
from .app import XiaoTieApp


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

    tools.append(PythonTool())
    tools.append(CalculatorTool())
    tools.append(GitTool(workspace_dir=str(workspace)))
    tools.append(WebSearchTool())
    tools.append(WebFetchTool())

    return tools


def load_system_prompt(config: Config) -> str:
    """加载系统提示词"""
    prompt_path = Config.find_config_file(config.agent.system_prompt_path)

    if prompt_path and prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

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


def run_tui():
    """运行 TUI 模式"""
    # 加载配置
    try:
        config = Config.load()
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ 配置错误: {e}")
        print("\n请创建配置文件 config/config.yaml")
        sys.exit(1)

    # 创建工作目录
    workspace = Path(config.agent.workspace_dir).absolute()
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建工具
    tools = create_tools(config, workspace)

    # 加载插件
    plugin_mgr = PluginManager()
    plugin_tools = plugin_mgr.load_all_plugins()
    if plugin_tools:
        tools.extend(plugin_tools)

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
        stream=False,  # TUI 模式下不使用流式
        enable_thinking=True,
    )

    # 创建命令管理器
    commands = Commands(agent, session_mgr, plugin_mgr)

    # 创建并运行 TUI 应用
    app = XiaoTieApp(
        agent=agent,
        session_mgr=session_mgr,
        plugin_mgr=plugin_mgr,
        commands=commands,
    )

    # 设置模型名称
    app.model_name = config.llm.model

    app.run()


if __name__ == "__main__":
    run_tui()
