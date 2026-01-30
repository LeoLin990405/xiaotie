"""数据模型定义

参考 OpenCode 的数据库模型设计。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


def generate_id() -> str:
    """生成唯一 ID"""
    return str(uuid.uuid4())


def current_timestamp_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


@dataclass
class SessionRecord:
    """会话记录"""

    id: str = field(default_factory=generate_id)
    title: str = "新会话"
    parent_session_id: Optional[str] = None
    message_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    created_at: int = field(default_factory=current_timestamp_ms)
    updated_at: int = field(default_factory=current_timestamp_ms)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "parent_session_id": self.parent_session_id,
            "message_count": self.message_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost": self.cost,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        """从字典创建"""
        return cls(
            id=data.get("id", generate_id()),
            title=data.get("title", "新会话"),
            parent_session_id=data.get("parent_session_id"),
            message_count=data.get("message_count", 0),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            cost=data.get("cost", 0.0),
            created_at=data.get("created_at", current_timestamp_ms()),
            updated_at=data.get("updated_at", current_timestamp_ms()),
        )

    @classmethod
    def from_row(cls, row: tuple) -> SessionRecord:
        """从数据库行创建"""
        return cls(
            id=row[0],
            parent_session_id=row[1],
            title=row[2],
            message_count=row[3],
            prompt_tokens=row[4],
            completion_tokens=row[5],
            cost=row[6],
            updated_at=row[7],
            created_at=row[8],
        )


@dataclass
class MessageRecord:
    """消息记录"""

    id: str = field(default_factory=generate_id)
    session_id: str = ""
    role: str = "user"  # user, assistant, system, tool
    parts: list[dict[str, Any]] = field(default_factory=list)
    model: Optional[str] = None
    created_at: int = field(default_factory=current_timestamp_ms)
    updated_at: int = field(default_factory=current_timestamp_ms)
    finished_at: Optional[int] = None

    @property
    def content(self) -> str:
        """获取消息内容"""
        for part in self.parts:
            if part.get("type") == "text":
                return part.get("text", "")
        return ""

    @content.setter
    def content(self, value: str) -> None:
        """设置消息内容"""
        self.parts = [{"type": "text", "text": value}]

    @property
    def thinking(self) -> Optional[str]:
        """获取思考内容"""
        for part in self.parts:
            if part.get("type") == "thinking":
                return part.get("text")
        return None

    @thinking.setter
    def thinking(self, value: str) -> None:
        """设置思考内容"""
        # 移除现有的 thinking
        self.parts = [p for p in self.parts if p.get("type") != "thinking"]
        if value:
            self.parts.insert(0, {"type": "thinking", "text": value})

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "parts": self.parts,
            "model": self.model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MessageRecord:
        """从字典创建"""
        return cls(
            id=data.get("id", generate_id()),
            session_id=data.get("session_id", ""),
            role=data.get("role", "user"),
            parts=data.get("parts", []),
            model=data.get("model"),
            created_at=data.get("created_at", current_timestamp_ms()),
            updated_at=data.get("updated_at", current_timestamp_ms()),
            finished_at=data.get("finished_at"),
        )

    @classmethod
    def from_row(cls, row: tuple) -> MessageRecord:
        """从数据库行创建"""
        parts = json.loads(row[3]) if isinstance(row[3], str) else row[3]
        return cls(
            id=row[0],
            session_id=row[1],
            role=row[2],
            parts=parts,
            model=row[4],
            created_at=row[5],
            updated_at=row[6],
            finished_at=row[7],
        )

    def parts_json(self) -> str:
        """获取 parts 的 JSON 字符串"""
        return json.dumps(self.parts, ensure_ascii=False)


@dataclass
class FileRecord:
    """文件记录（用于版本控制）"""

    id: str = field(default_factory=generate_id)
    session_id: str = ""
    path: str = ""
    content: str = ""
    version: str = "1"
    created_at: int = field(default_factory=current_timestamp_ms)
    updated_at: int = field(default_factory=current_timestamp_ms)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "path": self.path,
            "content": self.content,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        """从字典创建"""
        return cls(
            id=data.get("id", generate_id()),
            session_id=data.get("session_id", ""),
            path=data.get("path", ""),
            content=data.get("content", ""),
            version=data.get("version", "1"),
            created_at=data.get("created_at", current_timestamp_ms()),
            updated_at=data.get("updated_at", current_timestamp_ms()),
        )

    @classmethod
    def from_row(cls, row: tuple) -> FileRecord:
        """从数据库行创建"""
        return cls(
            id=row[0],
            session_id=row[1],
            path=row[2],
            content=row[3],
            version=row[4],
            created_at=row[5],
            updated_at=row[6],
        )
