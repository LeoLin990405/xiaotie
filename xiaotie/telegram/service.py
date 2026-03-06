from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from .client import TelegramBotClient

logger = logging.getLogger(__name__)

CommandHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[str]]


class TelegramIntegrationService:
    def __init__(
        self,
        bot_client: TelegramBotClient,
        db_path: Optional[str] = None,
        allowed_chat_ids: Optional[list[int]] = None,
        user_auth_map: Optional[dict[int, str]] = None,
    ):
        self.bot_client = bot_client
        self.db_path = db_path
        self.allowed_chat_ids = set(allowed_chat_ids or [])
        self.user_auth_map = user_auth_map or {}
        self.command_handlers: Dict[str, CommandHandler] = {}
        self._register_default_handlers()

    def register_command(self, command: str, handler: CommandHandler) -> None:
        key = command.strip().lower()
        self.command_handlers[key] = handler

    def register_user(self, telegram_user_id: int, app_user_id: str) -> None:
        self.user_auth_map[telegram_user_id] = app_user_id

    async def process_update(self, update: dict[str, Any]) -> Optional[str]:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat = message.get("chat", {})
        chat_id = int(chat.get("id", 0))
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return "当前会话未授权访问应用数据。"

        from_user = message.get("from", {})
        telegram_user_id = int(from_user.get("id", 0))
        if self.user_auth_map and telegram_user_id not in self.user_auth_map:
            return "当前用户未完成身份绑定，请先联系管理员绑定账号。"

        if message.get("text"):
            return await self._process_text(message, update)
        if message.get("photo"):
            largest = message["photo"][-1]
            return f"已收到图片，file_id={largest.get('file_id', '')}"
        if message.get("document"):
            doc = message["document"]
            return f"已收到文件，file_name={doc.get('file_name', '')} file_id={doc.get('file_id', '')}"
        return "暂不支持该消息类型，请发送文本、图片或文件。"

    async def handle_update_and_reply(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id is None:
            return
        try:
            reply_text = await self.process_update(update)
            if reply_text:
                await self.bot_client.send_message(chat_id=chat_id, text=reply_text)
        except Exception as exc:
            logger.exception("telegram update 处理失败: %s", exc)
            await self.bot_client.send_message(chat_id=chat_id, text="处理请求时发生异常，请稍后重试。")

    async def push_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        return await self.bot_client.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)

    async def _process_text(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        text = str(message.get("text", "")).strip()
        if not text:
            return "未检测到文本内容。"
        parts = text.split()
        command = parts[0].lower()
        if command.startswith("/"):
            handler = self.command_handlers.get(command)
            if handler:
                return await handler(message, update)
            return "未知命令，请发送 /help 查看可用命令。"
        return f"已收到文本消息：{text}"

    def _register_default_handlers(self) -> None:
        self.register_command("/start", self._handle_start)
        self.register_command("/help", self._handle_help)
        self.register_command("/sessions", self._handle_sessions)
        self.register_command("/messages", self._handle_messages)
        self.register_command("/stats", self._handle_stats)

    async def _handle_start(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        _ = (message, update)
        return "已连接小铁应用。发送 /help 查看支持的命令。"

    async def _handle_help(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        _ = (message, update)
        return "\n".join(
            [
                "可用命令：",
                "/sessions 查询最近会话",
                "/messages <session_id> 查询会话消息",
                "/stats 查询系统统计",
            ]
        )

    async def _handle_sessions(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        _ = (message, update)
        rows = await asyncio.to_thread(self._query_sessions)
        if not rows:
            return "暂无会话数据。"
        lines = ["最近会话："]
        for session_id, title, updated_at in rows:
            ts = datetime.fromtimestamp(updated_at / 1000).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"- {session_id} | {title} | {ts}")
        return "\n".join(lines)

    async def _handle_messages(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        _ = update
        text = str(message.get("text", "")).strip()
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            return "请使用 /messages <session_id>"
        session_id = parts[1].strip()
        rows = await asyncio.to_thread(self._query_messages, session_id)
        if not rows:
            return "未找到该会话消息。"
        lines = [f"会话 {session_id} 最近消息："]
        for role, content, created_at in rows:
            ts = datetime.fromtimestamp(created_at / 1000).strftime("%H:%M:%S")
            text_content = content[:120].replace("\n", " ")
            lines.append(f"[{ts}] {role}: {text_content}")
        return "\n".join(lines)

    async def _handle_stats(self, message: dict[str, Any], update: dict[str, Any]) -> str:
        _ = (message, update)
        stats = await asyncio.to_thread(self._query_stats)
        return "\n".join(
            [
                "系统统计：",
                f"- 会话总数: {stats['session_count']}",
                f"- 消息总数: {stats['message_count']}",
                f"- 最近更新时间: {stats['last_updated']}",
            ]
        )

    def _query_sessions(self) -> list[tuple[str, str, int]]:
        if not self.db_path or not Path(self.db_path).exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 5"
            )
            return list(cursor.fetchall())

    def _query_messages(self, session_id: str) -> list[tuple[str, str, int]]:
        if not self.db_path or not Path(self.db_path).exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT role, parts, created_at FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 10",
                (session_id,),
            )
            rows = []
            for role, parts, created_at in cursor.fetchall():
                content = self._extract_content(parts)
                rows.append((role, content, created_at))
            return rows

    def _query_stats(self) -> dict[str, Any]:
        if not self.db_path or not Path(self.db_path).exists():
            return {"session_count": 0, "message_count": 0, "last_updated": "N/A"}
        with sqlite3.connect(self.db_path) as conn:
            session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            row = conn.execute("SELECT MAX(updated_at) FROM sessions").fetchone()
            if row and row[0]:
                last_updated = datetime.fromtimestamp(row[0] / 1000).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_updated = "N/A"
            return {
                "session_count": session_count,
                "message_count": message_count,
                "last_updated": last_updated,
            }

    @staticmethod
    def _extract_content(parts_raw: str) -> str:
        try:
            parts = json.loads(parts_raw)
            if not isinstance(parts, list):
                return str(parts_raw)
            texts = []
            for part in parts:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(str(part.get("text", "")))
            return " ".join(texts) if texts else str(parts_raw)
        except Exception:
            return str(parts_raw)
