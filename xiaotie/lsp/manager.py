"""LSP 管理器

管理多个语言的 LSP 客户端。
"""

from __future__ import annotations

from typing import Optional

from .client import LSPClient, LSPConfig
from .protocol import Diagnostic, detect_language_id

# 默认 LSP 配置
DEFAULT_LSP_CONFIGS: dict[str, LSPConfig] = {
    "python": LSPConfig(
        command="pylsp",
        args=[],
    ),
    "typescript": LSPConfig(
        command="typescript-language-server",
        args=["--stdio"],
    ),
    "javascript": LSPConfig(
        command="typescript-language-server",
        args=["--stdio"],
    ),
    "go": LSPConfig(
        command="gopls",
        args=[],
    ),
    "rust": LSPConfig(
        command="rust-analyzer",
        args=[],
    ),
}


class LSPManager:
    """LSP 管理器"""

    def __init__(
        self,
        workspace_dir: str,
        configs: Optional[dict[str, LSPConfig]] = None,
    ):
        self.workspace_dir = workspace_dir
        self.configs = configs or {}
        self._clients: dict[str, LSPClient] = {}

    def get_config(self, language: str) -> Optional[LSPConfig]:
        """获取语言的 LSP 配置"""
        # 优先使用用户配置
        if language in self.configs:
            return self.configs[language]
        # 使用默认配置
        return DEFAULT_LSP_CONFIGS.get(language)

    async def get_client(self, language: str) -> Optional[LSPClient]:
        """获取或创建语言的 LSP 客户端"""
        if language in self._clients:
            client = self._clients[language]
            if client.is_running:
                return client

        config = self.get_config(language)
        if not config or not config.enabled:
            return None

        # 检查命令是否存在
        if not self._command_exists(config.command):
            return None

        client = LSPClient(config, self.workspace_dir)
        if await client.start():
            self._clients[language] = client
            return client

        return None

    def _command_exists(self, command: str) -> bool:
        """检查命令是否存在"""
        import shutil

        return shutil.which(command) is not None

    async def get_client_for_file(self, file_path: str) -> Optional[LSPClient]:
        """根据文件获取 LSP 客户端"""
        language = detect_language_id(file_path)
        return await self.get_client(language)

    async def open_file(self, file_path: str) -> None:
        """打开文件"""
        client = await self.get_client_for_file(file_path)
        if client:
            await client.open_file(file_path)

    async def close_file(self, file_path: str) -> None:
        """关闭文件"""
        client = await self.get_client_for_file(file_path)
        if client:
            await client.close_file(file_path)

    async def notify_change(self, file_path: str) -> None:
        """通知文件变更"""
        client = await self.get_client_for_file(file_path)
        if client:
            await client.notify_change(file_path)

    async def get_diagnostics(self, file_path: Optional[str] = None) -> dict[str, list[Diagnostic]]:
        """获取诊断信息"""
        if file_path:
            client = await self.get_client_for_file(file_path)
            if client:
                return client.get_diagnostics(file_path)
            return {}

        # 获取所有客户端的诊断
        result = {}
        for client in self._clients.values():
            result.update(client.get_diagnostics())
        return result

    async def get_file_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """获取单个文件的诊断"""
        client = await self.get_client_for_file(file_path)
        if not client:
            return []

        # 确保文件已打开
        await client.open_file(file_path)

        # 等待一小段时间让 LSP 处理
        import asyncio

        await asyncio.sleep(0.5)

        diags = client.get_diagnostics(file_path)
        return diags.get(file_path, [])

    async def stop_all(self) -> None:
        """停止所有 LSP 客户端"""
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()

    def list_available_languages(self) -> list[str]:
        """列出可用的语言"""
        available = []
        for lang, config in {**DEFAULT_LSP_CONFIGS, **self.configs}.items():
            if config.enabled and self._command_exists(config.command):
                available.append(lang)
        return available


def format_diagnostics(diagnostics: dict[str, list[Diagnostic]]) -> str:
    """格式化诊断信息为字符串"""
    if not diagnostics:
        return "No diagnostics found."

    lines = []
    for file_path, diags in diagnostics.items():
        if not diags:
            continue

        lines.append(f"\n📄 {file_path}:")
        for diag in diags:
            severity_icon = {
                1: "❌",  # Error
                2: "⚠️",  # Warning
                3: "ℹ️",  # Information
                4: "💡",  # Hint
            }.get(diag.severity.value if diag.severity else 0, "❓")

            line = diag.range.start.line + 1
            col = diag.range.start.character + 1
            lines.append(f"  {severity_icon} Line {line}:{col}: {diag.message}")

    return "\n".join(lines) if lines else "No diagnostics found."
