"""文件操作工具"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tiktoken

from ..schema import ToolResult
from .base import Tool


def truncate_text_by_tokens(text: str, max_tokens: int = 8000) -> str:
    """智能截断：保留头尾，截断中间"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(text))
    except Exception:
        # 如果 tiktoken 不可用，按字符估算
        token_count = len(text) // 4

    if token_count <= max_tokens:
        return text

    # 计算 token/字符 比例
    ratio = token_count / len(text) if text else 1
    chars_per_half = int((max_tokens / 2) / ratio * 0.95)

    # 保留前半部分（找最近换行符）
    head_part = text[:chars_per_half]
    last_newline = head_part.rfind("\n")
    if last_newline > 0:
        head_part = head_part[:last_newline]

    # 保留后半部分（找最近换行符）
    tail_part = text[-chars_per_half:]
    first_newline = tail_part.find("\n")
    if first_newline > 0:
        tail_part = tail_part[first_newline + 1 :]

    truncation_note = f"\n\n... [内容已截断: {token_count} tokens -> ~{max_tokens} tokens] ...\n\n"
    return head_part + truncation_note + tail_part


class ReadTool(Tool):
    """读取文件工具"""

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取文件内容。支持文本文件，自动处理大文件截断。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对或绝对路径）",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "最大 token 数（默认 8000）",
                    "default": 8000,
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, max_tokens: int = 8000) -> ToolResult:
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.workspace_dir / file_path

            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {file_path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"不是文件: {file_path}")

            content = file_path.read_text(encoding="utf-8")
            content = truncate_text_by_tokens(content, max_tokens)

            return ToolResult(success=True, content=content)

        except Exception as e:
            return ToolResult(success=False, error=f"读取失败: {e}")


class WriteTool(Tool):
    """写入文件工具"""

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "写入内容到文件。如果文件不存在则创建，存在则覆盖。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对或绝对路径）",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.workspace_dir / file_path

            # 创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(content, encoding="utf-8")

            return ToolResult(success=True, content=f"已写入 {len(content)} 字符到 {file_path}")

        except Exception as e:
            return ToolResult(success=False, error=f"写入失败: {e}")


class EditTool(Tool):
    """编辑文件工具"""

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "编辑文件：精确替换指定文本。old_string 必须在文件中唯一存在。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "old_string": {
                    "type": "string",
                    "description": "要替换的原文本（必须唯一）",
                },
                "new_string": {
                    "type": "string",
                    "description": "替换后的新文本",
                },
            },
            "required": ["path", "old_string", "new_string"],
        }

    async def execute(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.workspace_dir / file_path

            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {file_path}")

            content = file_path.read_text(encoding="utf-8")

            # 检查唯一性
            count = content.count(old_string)
            if count == 0:
                return ToolResult(success=False, error="未找到要替换的文本")
            if count > 1:
                return ToolResult(
                    success=False, error=f"找到 {count} 处匹配，请提供更多上下文使其唯一"
                )

            # 执行替换
            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True, content=f"已替换 {len(old_string)} -> {len(new_string)} 字符"
            )

        except Exception as e:
            return ToolResult(success=False, error=f"编辑失败: {e}")
