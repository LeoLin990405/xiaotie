"""数据库连接管理

使用 aiosqlite 实现异步 SQLite 操作。
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import aiosqlite

# 数据库迁移 SQL
MIGRATIONS = [
    # 初始迁移 - 创建基础表
    """
    -- 会话表
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        parent_session_id TEXT,
        title TEXT NOT NULL,
        message_count INTEGER NOT NULL DEFAULT 0 CHECK (message_count >= 0),
        prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
        completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
        cost REAL NOT NULL DEFAULT 0.0 CHECK (cost >= 0.0),
        updated_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    );

    -- 消息表
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        parts TEXT NOT NULL DEFAULT '[]',
        model TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        finished_at INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
    );

    -- 文件表
    CREATE TABLE IF NOT EXISTS files (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        path TEXT NOT NULL,
        content TEXT NOT NULL,
        version TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
        UNIQUE(path, session_id, version)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
    CREATE INDEX IF NOT EXISTS idx_files_session_id ON files(session_id);
    CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
    CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

    -- 迁移版本表
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at INTEGER NOT NULL
    );
    """,
]


class Database:
    """数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connection is not None

    async def connect(self) -> None:
        """连接数据库"""
        if self._connection is not None:
            return

        # 确保目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        # 启用外键约束
        await self._connection.execute("PRAGMA foreign_keys = ON")
        # 启用 WAL 模式提高并发性能
        await self._connection.execute("PRAGMA journal_mode = WAL")
        await self._connection.commit()

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def migrate(self) -> None:
        """执行数据库迁移"""
        if self._connection is None:
            await self.connect()

        async with self._lock:
            # 获取当前版本
            cursor = await self._connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_migrations'
                """
            )
            table_exists = await cursor.fetchone()

            current_version = 0
            if table_exists:
                cursor = await self._connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                )
                row = await cursor.fetchone()
                if row and row[0]:
                    current_version = row[0]

            # 执行未应用的迁移
            for i, migration in enumerate(MIGRATIONS):
                version = i + 1
                if version > current_version:
                    await self._connection.executescript(migration)
                    await self._connection.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, int(asyncio.get_event_loop().time() * 1000)),
                    )
                    await self._connection.commit()

    async def execute(self, sql: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """执行 SQL"""
        if self._connection is None:
            await self.connect()
        return await self._connection.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: list[tuple]) -> aiosqlite.Cursor:
        """批量执行 SQL"""
        if self._connection is None:
            await self.connect()
        return await self._connection.executemany(sql, parameters)

    async def commit(self) -> None:
        """提交事务"""
        if self._connection is not None:
            await self._connection.commit()

    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[tuple]:
        """查询单行"""
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, parameters: tuple = ()) -> list[tuple]:
        """查询多行"""
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchall()


# 全局数据库实例
_database: Optional[Database] = None


def get_default_db_path() -> str:
    """获取默认数据库路径"""
    # 优先使用 XDG 数据目录
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return os.path.join(xdg_data, "xiaotie", "xiaotie.db")

    # 否则使用 ~/.xiaotie/
    home = os.path.expanduser("~")
    return os.path.join(home, ".xiaotie", "xiaotie.db")


def get_database() -> Database:
    """获取全局数据库实例"""
    global _database
    if _database is None:
        _database = Database(get_default_db_path())
    return _database


async def init_database(db_path: Optional[str] = None) -> Database:
    """初始化数据库"""
    global _database
    if db_path:
        _database = Database(db_path)
    else:
        _database = Database(get_default_db_path())

    await _database.connect()
    await _database.migrate()
    return _database
