"""小铁 TUI 入口

使用 Textual 构建的现代化终端界面
"""

from __future__ import annotations

import asyncio
import sys

from ..commands import Commands
from ..config import Config
from ..runtime_setup import cleanup_mcp, setup_runtime
from ..session import SessionManager
from .app import XiaoTieApp
from .onboarding import get_bootstrap_config_path


def run_tui():
    """运行 TUI 模式"""
    config = None
    try:
        config = Config.load()
    except (FileNotFoundError, ValueError):
        bootstrap_app = XiaoTieApp(show_onboarding=True, onboarding_required=True)
        bootstrap_app.run()
        result = bootstrap_app.onboarding_result or {}
        if not result.get("completed"):
            print("❌ 未完成引导配置，已退出。")
            sys.exit(1)
        bootstrap_config = get_bootstrap_config_path()
        if bootstrap_config.exists():
            config = Config.load(bootstrap_config)
        else:
            print("❌ 引导配置未生成有效配置文件。")
            sys.exit(1)

    setup = asyncio.run(setup_runtime(config, stream=True, thinking=True))

    try:
        session_mgr = SessionManager()
        commands = Commands(setup.runtime, session_mgr, setup.plugin_manager)
        app = XiaoTieApp(
            agent=setup.runtime,
            session_mgr=session_mgr,
            plugin_mgr=setup.plugin_manager,
            commands=commands,
        )
        app.model_name = config.llm.model
        app.run()
    finally:
        asyncio.run(cleanup_mcp())


if __name__ == "__main__":
    run_tui()
