"""消息存储

提供消息的 CRUD 操作。
"""

from __future__ import annotations

from typing import Optional

from .database import Database, get_database
from .models import MessageRecord, current_timestamp_ms


class MessageStore:
    """消息存储"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    async def create(self, message: MessageRecord) -> MessageRecord:
        """创建消息"""
        await self.db.execute(
            """
            INSERT INTO messages (
                id, session_id, role, parts, model,
                created_at, updated_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.session_id,
                message.role,
                message.parts_json(),
                message.model,
                message.created_at,
                message.updated_at,
                message.finished_at,
            ),
        )
        await self.db.commit()
        return message

    async def get(self, message_id: str) -> Optional[MessageRecord]:
        """获取消息"""
        row = await self.db.fetchone(
            """
            SELECT id, session_id, role, parts, model,
                   created_at, updated_at, finished_at
            FROM messages WHERE id = ?
            """,
            (message_id,),
        )
        if row:
            return MessageRecord.from_row(row)
        return None

    async def list_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        desc: bool = False,
    ) -> list[MessageRecord]:
        """列出会话的消息"""
        order = "DESC" if desc else "ASC"
        rows = await self.db.fetchall(
            f"""
            SELECT id, session_id, role, parts, model,
                   created_at, updated_at, finished_at
            FROM messages
            WHERE session_id = ?
            ORDER BY {order_by} {order}
            LIMIT ? OFFSET ?
            """,
            (session_id, limit, offset),
        )
        return [MessageRecord.from_row(row) for row in rows]

    async def update(self, message: MessageRecord) -> MessageRecord:
        """更新消息"""
        message.updated_at = current_timestamp_ms()
        await self.db.execute(
            """
            UPDATE messages SET
                role = ?,
                parts = ?,
                model = ?,
                updated_at = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (
                message.role,
                message.parts_json(),
                message.model,
                message.updated_at,
                message.finished_at,
                message.id,
            ),
        )
        await self.db.commit()
        return message

    async def delete(self, message_id: str) -> bool:
        """删除消息"""
        cursor = await self.db.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def delete_by_session(self, session_id: str) -> int:
        """删除会话的所有消息"""
        cursor = await self.db.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id,),
        )
        await self.db.commit()
        return cursor.rowcount

    async def count_by_session(self, session_id: str) -> int:
        """获取会话的消息数"""
        row = await self.db.fetchone(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,),
        )
        return row[0] if row else 0

    async def get_latest(self, session_id: str, limit: int = 10) -> list[MessageRecord]:
        """获取最新消息"""
        rows = await self.db.fetchall(
            """
            SELECT id, session_id, role, parts, model,
                   created_at, updated_at, finished_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        # 反转顺序，使最早的在前
        return [MessageRecord.from_row(row) for row in reversed(rows)]

    async def mark_finished(self, message_id: str) -> None:
        """标记消息完成"""
        now = current_timestamp_ms()
        await self.db.execute(
            """
            UPDATE messages SET
                finished_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, message_id),
        )
        await self.db.commit()

    async def search(self, session_id: str, query: str, limit: int = 20) -> list[MessageRecord]:
        """搜索消息"""
        rows = await self.db.fetchall(
            """
            SELECT id, session_id, role, parts, model,
                   created_at, updated_at, finished_at
            FROM messages
            WHERE session_id = ? AND parts LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, f"%{query}%", limit),
        )
        return [MessageRecord.from_row(row) for row in rows]

    async def bulk_create(self, messages: list[MessageRecord]) -> None:
        """批量创建消息"""
        await self.db.executemany(
            """
            INSERT INTO messages (
                id, session_id, role, parts, model,
                created_at, updated_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m.id,
                    m.session_id,
                    m.role,
                    m.parts_json(),
                    m.model,
                    m.created_at,
                    m.updated_at,
                    m.finished_at,
                )
                for m in messages
            ],
        )
        await self.db.commit()
