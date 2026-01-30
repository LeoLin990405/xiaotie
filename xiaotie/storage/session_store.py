"""会话存储

提供会话的 CRUD 操作。
"""

from __future__ import annotations

from typing import Optional

from .database import Database, get_database
from .models import SessionRecord, current_timestamp_ms


class SessionStore:
    """会话存储"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    async def create(self, session: SessionRecord) -> SessionRecord:
        """创建会话"""
        await self.db.execute(
            """
            INSERT INTO sessions (
                id, parent_session_id, title, message_count,
                prompt_tokens, completion_tokens, cost,
                updated_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.parent_session_id,
                session.title,
                session.message_count,
                session.prompt_tokens,
                session.completion_tokens,
                session.cost,
                session.updated_at,
                session.created_at,
            ),
        )
        await self.db.commit()
        return session

    async def get(self, session_id: str) -> Optional[SessionRecord]:
        """获取会话"""
        row = await self.db.fetchone(
            """
            SELECT id, parent_session_id, title, message_count,
                   prompt_tokens, completion_tokens, cost,
                   updated_at, created_at
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        )
        if row:
            return SessionRecord.from_row(row)
        return None

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "updated_at",
        desc: bool = True,
    ) -> list[SessionRecord]:
        """列出会话"""
        order = "DESC" if desc else "ASC"
        rows = await self.db.fetchall(
            f"""
            SELECT id, parent_session_id, title, message_count,
                   prompt_tokens, completion_tokens, cost,
                   updated_at, created_at
            FROM sessions
            ORDER BY {order_by} {order}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [SessionRecord.from_row(row) for row in rows]

    async def update(self, session: SessionRecord) -> SessionRecord:
        """更新会话"""
        session.updated_at = current_timestamp_ms()
        await self.db.execute(
            """
            UPDATE sessions SET
                parent_session_id = ?,
                title = ?,
                message_count = ?,
                prompt_tokens = ?,
                completion_tokens = ?,
                cost = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                session.parent_session_id,
                session.title,
                session.message_count,
                session.prompt_tokens,
                session.completion_tokens,
                session.cost,
                session.updated_at,
                session.id,
            ),
        )
        await self.db.commit()
        return session

    async def delete(self, session_id: str) -> bool:
        """删除会话"""
        cursor = await self.db.execute(
            "DELETE FROM sessions WHERE id = ?",
            (session_id,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def update_tokens(
        self,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float = 0.0,
    ) -> None:
        """更新 token 统计"""
        await self.db.execute(
            """
            UPDATE sessions SET
                prompt_tokens = prompt_tokens + ?,
                completion_tokens = completion_tokens + ?,
                cost = cost + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                prompt_tokens,
                completion_tokens,
                cost,
                current_timestamp_ms(),
                session_id,
            ),
        )
        await self.db.commit()

    async def increment_message_count(self, session_id: str) -> None:
        """增加消息计数"""
        await self.db.execute(
            """
            UPDATE sessions SET
                message_count = message_count + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (current_timestamp_ms(), session_id),
        )
        await self.db.commit()

    async def count(self) -> int:
        """获取会话总数"""
        row = await self.db.fetchone("SELECT COUNT(*) FROM sessions")
        return row[0] if row else 0

    async def search(self, query: str, limit: int = 20) -> list[SessionRecord]:
        """搜索会话"""
        rows = await self.db.fetchall(
            """
            SELECT id, parent_session_id, title, message_count,
                   prompt_tokens, completion_tokens, cost,
                   updated_at, created_at
            FROM sessions
            WHERE title LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        return [SessionRecord.from_row(row) for row in rows]
