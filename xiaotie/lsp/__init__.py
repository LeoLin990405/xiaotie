"""LSP (Language Server Protocol) 支持

参考 OpenCode 的 LSP 实现，提供代码诊断功能。

主要组件:
- LSPClient: LSP 客户端，管理与语言服务器的通信
- LSPManager: 多语言 LSP 管理器
- DiagnosticsTool: 诊断工具，供 Agent 使用
"""

from .client import LSPClient, LSPConfig
from .diagnostics import DiagnosticsTool
from .manager import LSPManager, format_diagnostics
from .protocol import (
    Diagnostic,
    DiagnosticSeverity,
    DocumentUri,
    Location,
    Position,
    Range,
    TextDocumentIdentifier,
    detect_language_id,
)

__all__ = [
    "LSPClient",
    "LSPConfig",
    "LSPManager",
    "DiagnosticsTool",
    "Diagnostic",
    "DiagnosticSeverity",
    "Position",
    "Range",
    "Location",
    "TextDocumentIdentifier",
    "DocumentUri",
    "detect_language_id",
    "format_diagnostics",
]
