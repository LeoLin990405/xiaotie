"""诊断工具

提供代码诊断功能，通过 LSP 获取错误和警告。
"""

from __future__ import annotations

import os
from typing import Optional, Any

from ..tools.base import Tool, ToolResult


class DiagnosticsTool(Tool):
    """诊断工具 - 获取代码诊断信息"""

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self._lsp_manager = None

    @property
    def name(self) -> str:
        return "diagnostics"

    @property
    def description(self) -> str:
        return """获取代码诊断信息（错误、警告等）。

通过 Language Server Protocol (LSP) 获取代码问题：
- 语法错误
- 类型错误
- 未使用的变量
- 导入问题
- 代码风格问题

支持的语言：Python (pylsp), TypeScript/JavaScript (typescript-language-server), Go (gopls), Rust (rust-analyzer)"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要诊断的文件路径（可选，不指定则返回所有已打开文件的诊断）",
                },
            },
            "required": [],
        }

    async def _get_lsp_manager(self):
        """延迟初始化 LSP 管理器"""
        if self._lsp_manager is None:
            from ..lsp import LSPManager
            self._lsp_manager = LSPManager(self.workspace_dir)
        return self._lsp_manager

    async def execute(self, file_path: Optional[str] = None, **kwargs) -> ToolResult:
        """执行诊断"""
        try:
            manager = await self._get_lsp_manager()

            if file_path:
                # 诊断单个文件
                abs_path = os.path.join(self.workspace_dir, file_path)
                if not os.path.exists(abs_path):
                    return ToolResult(
                        success=False,
                        content=f"文件不存在: {file_path}",
                    )

                diagnostics = await manager.get_file_diagnostics(abs_path)

                if not diagnostics:
                    return ToolResult(
                        success=True,
                        content=f"✅ {file_path}: 没有发现问题",
                    )

                # 格式化诊断
                lines = [f"📄 {file_path} 诊断结果:\n"]
                errors = 0
                warnings = 0

                for diag in diagnostics:
                    severity_icon = {
                        1: "❌",  # Error
                        2: "⚠️",  # Warning
                        3: "ℹ️",  # Information
                        4: "💡",  # Hint
                    }.get(diag.severity.value if diag.severity else 0, "❓")

                    if diag.severity and diag.severity.value == 1:
                        errors += 1
                    elif diag.severity and diag.severity.value == 2:
                        warnings += 1

                    line = diag.range.start.line + 1
                    col = diag.range.start.character + 1
                    source = f"[{diag.source}] " if diag.source else ""
                    lines.append(f"  {severity_icon} Line {line}:{col}: {source}{diag.message}")

                summary = f"\n总计: {errors} 个错误, {warnings} 个警告"
                lines.append(summary)

                return ToolResult(
                    success=errors == 0,
                    content="\n".join(lines),
                )

            else:
                # 返回所有诊断
                all_diagnostics = await manager.get_diagnostics()

                if not all_diagnostics:
                    available = manager.list_available_languages()
                    if available:
                        return ToolResult(
                            success=True,
                            content=f"没有打开的文件或没有诊断信息。\n可用的 LSP: {', '.join(available)}",
                        )
                    else:
                        return ToolResult(
                            success=True,
                            content="没有可用的 LSP 服务器。请安装相应的语言服务器。",
                        )

                from ..lsp.manager import format_diagnostics
                content = format_diagnostics(all_diagnostics)

                return ToolResult(
                    success=True,
                    content=content,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                content=f"诊断失败: {str(e)}",
            )

    async def cleanup(self) -> None:
        """清理资源"""
        if self._lsp_manager:
            await self._lsp_manager.stop_all()
