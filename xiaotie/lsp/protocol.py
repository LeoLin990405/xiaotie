"""LSP 协议类型定义

基于 LSP 3.17 规范定义核心类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Union

# 基础类型
DocumentUri = str


@dataclass
class Position:
    """文档中的位置"""

    line: int  # 0-indexed
    character: int  # 0-indexed

    def to_dict(self) -> dict:
        return {"line": self.line, "character": self.character}

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(line=data["line"], character=data["character"])


@dataclass
class Range:
    """文档中的范围"""

    start: Position
    end: Position

    def to_dict(self) -> dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Range":
        return cls(
            start=Position.from_dict(data["start"]),
            end=Position.from_dict(data["end"]),
        )


@dataclass
class Location:
    """文档位置"""

    uri: DocumentUri
    range: Range

    def to_dict(self) -> dict:
        return {"uri": self.uri, "range": self.range.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        return cls(uri=data["uri"], range=Range.from_dict(data["range"]))


@dataclass
class TextDocumentIdentifier:
    """文档标识符"""

    uri: DocumentUri

    def to_dict(self) -> dict:
        return {"uri": self.uri}


@dataclass
class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    """带版本的文档标识符"""

    version: int

    def to_dict(self) -> dict:
        return {"uri": self.uri, "version": self.version}


@dataclass
class TextDocumentItem:
    """文档项"""

    uri: DocumentUri
    languageId: str
    version: int
    text: str

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "languageId": self.languageId,
            "version": self.version,
            "text": self.text,
        }


class DiagnosticSeverity(IntEnum):
    """诊断严重程度"""

    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


@dataclass
class DiagnosticRelatedInformation:
    """诊断相关信息"""

    location: Location
    message: str

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticRelatedInformation":
        return cls(
            location=Location.from_dict(data["location"]),
            message=data["message"],
        )


@dataclass
class Diagnostic:
    """诊断信息"""

    range: Range
    message: str
    severity: Optional[DiagnosticSeverity] = None
    code: Optional[Union[int, str]] = None
    source: Optional[str] = None
    relatedInformation: Optional[list[DiagnosticRelatedInformation]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Diagnostic":
        severity = None
        if "severity" in data:
            severity = DiagnosticSeverity(data["severity"])

        related = None
        if "relatedInformation" in data:
            related = [
                DiagnosticRelatedInformation.from_dict(r) for r in data["relatedInformation"]
            ]

        return cls(
            range=Range.from_dict(data["range"]),
            message=data["message"],
            severity=severity,
            code=data.get("code"),
            source=data.get("source"),
            relatedInformation=related,
        )

    @property
    def severity_str(self) -> str:
        """获取严重程度字符串"""
        if self.severity is None:
            return "Unknown"
        return {
            DiagnosticSeverity.Error: "Error",
            DiagnosticSeverity.Warning: "Warning",
            DiagnosticSeverity.Information: "Info",
            DiagnosticSeverity.Hint: "Hint",
        }.get(self.severity, "Unknown")

    def format(self) -> str:
        """格式化诊断信息"""
        line = self.range.start.line + 1  # 转为 1-indexed
        col = self.range.start.character + 1
        severity = self.severity_str
        source = f"[{self.source}] " if self.source else ""
        return f"{source}{severity} at line {line}:{col}: {self.message}"


# LSP 请求/响应类型


@dataclass
class InitializeParams:
    """初始化参数"""

    processId: Optional[int]
    rootUri: Optional[DocumentUri]
    capabilities: dict = field(default_factory=dict)
    workspaceFolders: Optional[list[dict]] = None

    def to_dict(self) -> dict:
        result = {
            "processId": self.processId,
            "rootUri": self.rootUri,
            "capabilities": self.capabilities,
        }
        if self.workspaceFolders:
            result["workspaceFolders"] = self.workspaceFolders
        return result


@dataclass
class InitializeResult:
    """初始化结果"""

    capabilities: dict

    @classmethod
    def from_dict(cls, data: dict) -> "InitializeResult":
        return cls(capabilities=data.get("capabilities", {}))


@dataclass
class DidOpenTextDocumentParams:
    """打开文档参数"""

    textDocument: TextDocumentItem

    def to_dict(self) -> dict:
        return {"textDocument": self.textDocument.to_dict()}


@dataclass
class DidCloseTextDocumentParams:
    """关闭文档参数"""

    textDocument: TextDocumentIdentifier

    def to_dict(self) -> dict:
        return {"textDocument": self.textDocument.to_dict()}


@dataclass
class DidChangeTextDocumentParams:
    """文档变更参数"""

    textDocument: VersionedTextDocumentIdentifier
    contentChanges: list[dict]

    def to_dict(self) -> dict:
        return {
            "textDocument": self.textDocument.to_dict(),
            "contentChanges": self.contentChanges,
        }


@dataclass
class PublishDiagnosticsParams:
    """发布诊断参数"""

    uri: DocumentUri
    diagnostics: list[Diagnostic]
    version: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PublishDiagnosticsParams":
        return cls(
            uri=data["uri"],
            diagnostics=[Diagnostic.from_dict(d) for d in data["diagnostics"]],
            version=data.get("version"),
        )


# 语言 ID 映射
LANGUAGE_ID_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascriptreact",
    ".tsx": "typescriptreact",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".lua": "lua",
    ".sh": "shellscript",
    ".bash": "shellscript",
    ".zsh": "shellscript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".md": "markdown",
    ".sql": "sql",
    ".r": "r",
    ".R": "r",
}


def detect_language_id(file_path: str) -> str:
    """根据文件扩展名检测语言 ID"""
    import os

    ext = os.path.splitext(file_path)[1].lower()
    return LANGUAGE_ID_MAP.get(ext, "plaintext")
