"""共享的运行时装配逻辑。

为 CLI 和 TUI 提供一致的工具创建、MCP 加载、系统提示词与 AgentRuntime
初始化流程，避免两套入口在 v3 继续分叉。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .agent import AgentConfig, AgentRuntime
from .config import Config
from .llm import LLMClient
from .plugins import PluginManager
from .retry import RetryConfig
from .tools import (
    EXTENDED_TOOLS,
    AutomationTool,
    BashTool,
    CalculatorTool,
    CharlesProxyTool,
    CodeAnalysisTool,
    EditTool,
    GitTool,
    ProxyServerTool,
    PythonTool,
    ReadTool,
    ScraperTool,
    TelegramTool,
    WebFetchTool,
    WebSearchTool,
    WriteTool,
)

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """你是小铁，一个智能 AI 助手。

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

_mcp_manager = None


@dataclass
class RuntimeSetup:
    """共享装配结果。"""

    runtime: AgentRuntime
    plugin_manager: PluginManager
    mcp_tools: list
    tools: list
    workspace: Path
    system_prompt: str


async def load_mcp_tools(
    config: Config,
    status_reporter: Callable[[str, str], None] | None = None,
) -> list:
    """按配置加载 MCP 工具。"""
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
            if status_reporter:
                status_reporter(
                    f"MCP 服务器 '{server_name}': {len(tools)} 个工具",
                    "ok",
                )
        except Exception as e:
            if status_reporter:
                status_reporter(f"MCP 服务器 '{server_name}' 连接失败: {e}", "error")
            else:
                logger.warning("MCP 服务器 '%s' 连接失败: %s", server_name, e)

    return mcp_tools


async def cleanup_mcp() -> None:
    """清理 MCP 连接。"""
    global _mcp_manager

    if _mcp_manager:
        await _mcp_manager.disconnect_all()
        _mcp_manager = None


def create_tools(config: Config, workspace: Path) -> list:
    """根据配置创建工具列表。"""
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
    if config.tools.enable_python:
        tools.append(PythonTool())
    if config.tools.enable_calculator:
        tools.append(CalculatorTool())
    if config.tools.enable_git:
        tools.append(GitTool(workspace_dir=str(workspace)))
    if config.tools.enable_web_tools:
        tools.append(WebSearchTool())
        tools.append(WebFetchTool())
    if config.tools.enable_code_analysis:
        tools.append(CodeAnalysisTool(workspace_dir=str(workspace)))
    if config.tools.enable_charles:
        tools.append(
            CharlesProxyTool(
                charles_path=config.tools.charles_path,
                proxy_port=config.tools.charles_proxy_port,
            )
        )
    if config.tools.enable_proxy:
        tools.append(
            ProxyServerTool(
                proxy_port=config.tools.proxy.port,
                enable_https=config.tools.proxy.enable_https,
                cert_path=config.tools.proxy.cert_path,
                storage_path=config.tools.proxy.storage_path,
            )
        )
    if config.tools.enable_scraper:
        tools.append(
            ScraperTool(
                scraper_dir=config.tools.scraper.scraper_dir,
                max_workers=config.tools.scraper.max_workers,
                request_delay=config.tools.scraper.request_delay,
                num_runs=config.tools.scraper.num_runs,
                stability_threshold=config.tools.scraper.stability_threshold,
            )
        )
    if config.tools.enable_automation:
        tools.append(
            AutomationTool(
                wechat_bundle_id=config.tools.automation.wechat_bundle_id,
                screenshot_dir=config.tools.automation.screenshot_dir,
                applescript_timeout=config.tools.automation.applescript_timeout,
            )
        )
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

    tools.extend(EXTENDED_TOOLS)
    return tools


def load_system_prompt(config: Config) -> str:
    """加载系统提示词。"""
    prompt_path = Config.find_config_file(config.agent.system_prompt_path)
    if prompt_path and prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT


async def setup_runtime(
    config: Config,
    *,
    stream: bool = True,
    thinking: bool = False,
    quiet: bool = False,
    status_reporter: Callable[[str, str], None] | None = None,
) -> RuntimeSetup:
    """创建共享运行时依赖。"""
    workspace = Path(config.agent.workspace_dir).absolute()
    workspace.mkdir(parents=True, exist_ok=True)

    tools = create_tools(config, workspace)

    plugin_mgr = PluginManager()
    plugin_tools = plugin_mgr.load_all_plugins()
    if plugin_tools:
        tools.extend(plugin_tools)

    mcp_tools = await load_mcp_tools(config, status_reporter=status_reporter)
    if mcp_tools:
        tools.extend(mcp_tools)

    system_prompt = load_system_prompt(config)

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

    agent_config = AgentConfig(
        max_steps=config.agent.max_steps,
        stream=stream,
        enable_thinking=thinking,
        quiet=quiet,
    )
    runtime = AgentRuntime(
        llm_client=llm_client,
        system_prompt=system_prompt,
        tools=tools,
        config=agent_config,
        workspace_dir=str(workspace),
    )

    try:
        from xiaotie.context_engine import ContextEngine

        context_engine = ContextEngine(token_budget=agent_config.token_limit)
        runtime.set_context_engine(context_engine)
        logger.debug("ContextEngine 已集成 (budget=%d)", agent_config.token_limit)
    except Exception as e:
        logger.debug("ContextEngine 未启用: %s", e)

    try:
        from xiaotie.repomap_v2 import RepoMapEngine

        repomap_engine = RepoMapEngine(workspace_dir=str(workspace))
        runtime.set_repomap_engine(repomap_engine)
        logger.debug("RepoMapEngine 已集成 (workspace=%s)", workspace)
    except Exception as e:
        logger.debug("RepoMapEngine 未启用: %s", e)

    return RuntimeSetup(
        runtime=runtime,
        plugin_manager=plugin_mgr,
        mcp_tools=mcp_tools,
        tools=tools,
        workspace=workspace,
        system_prompt=system_prompt,
    )
