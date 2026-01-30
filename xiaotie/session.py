"""会话管理模块"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import FunctionCall, Message, ToolCall


class SessionManager:
    """会话管理器"""

    def __init__(self, sessions_dir: str = "~/.xiaotie/sessions"):
        self.sessions_dir = Path(sessions_dir).expanduser()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[str] = None

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.sessions_dir / f"{session_id}.json"

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions = []
        for f in self.sessions_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    sessions.append(
                        {
                            "id": f.stem,
                            "title": data.get("title", "未命名"),
                            "created_at": data.get("created_at", ""),
                            "updated_at": data.get("updated_at", ""),
                            "message_count": len(data.get("messages", [])),
                        }
                    )
            except Exception:
                continue
        # 按更新时间排序
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions

    def create_session(self, title: Optional[str] = None) -> str:
        """创建新会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not title:
            title = f"会话 {session_id}"

        data = {
            "id": session_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": [],
        }

        path = self._get_session_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.current_session = session_id
        return session_id

    def save_session(
        self,
        session_id: str,
        messages: List[Message],
        title: Optional[str] = None,
    ) -> bool:
        """保存会话"""
        path = self._get_session_path(session_id)

        # 读取现有数据
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "id": session_id,
                "title": title or f"会话 {session_id}",
                "created_at": datetime.now().isoformat(),
            }

        # 更新数据
        data["updated_at"] = datetime.now().isoformat()
        if title:
            data["title"] = title

        # 序列化消息
        data["messages"] = [self._message_to_dict(msg) for msg in messages]

        # 保存
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True

    def load_session(self, session_id: str) -> Optional[List[Message]]:
        """加载会话"""
        path = self._get_session_path(session_id)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = [self._dict_to_message(m) for m in data.get("messages", [])]
        self.current_session = session_id
        return messages

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            if self.current_session == session_id:
                self.current_session = None
            return True
        return False

    def get_session_title(self, session_id: str) -> Optional[str]:
        """获取会话标题"""
        path = self._get_session_path(session_id)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("title")

    def _message_to_dict(self, msg: Message) -> Dict[str, Any]:
        """消息转字典"""
        d = {
            "role": msg.role,
            "content": msg.content,
        }
        if msg.thinking:
            d["thinking"] = msg.thinking
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        return d

    def _dict_to_message(self, d: Dict[str, Any]) -> Message:
        """字典转消息"""
        tool_calls = None
        if "tool_calls" in d:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=FunctionCall(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in d["tool_calls"]
            ]

        return Message(
            role=d["role"],
            content=d.get("content", ""),
            thinking=d.get("thinking"),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
            tool_calls=tool_calls,
        )
