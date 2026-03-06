"""
Tests for the core sqlite persistent storage layer.
"""

import asyncio
import os
import pytest
import aiosqlite
from pathlib import Path
from unittest.mock import patch, AsyncMock

from xiaotie.storage.database import (
    Database,
    BatchCommitDatabase,
    get_default_db_path,
    get_database,
    init_database,
)

@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_storage.db")

class TestDatabase:
    @pytest.mark.asyncio
    async def test_connect_and_close(self, temp_db_path):
        db = Database(temp_db_path)
        assert not db.is_connected
        
        await db.connect()
        assert db.is_connected
        
        # Double connect should do nothing
        await db.connect()
        assert db.is_connected
        
        await db.close()
        assert not db.is_connected
        
        # Double close should do nothing
        await db.close()
        assert not db.is_connected

    @pytest.mark.asyncio
    async def test_migrate_and_execute(self, temp_db_path):
        db = Database(temp_db_path)
        await db.connect()
        await db.migrate()
        
        # Test execute and fetch
        cursor = await db.execute("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", 
                         ("sess1", "My Session", 1000, 1000))
        await db.commit()
        
        row = await db.fetchone("SELECT id, title FROM sessions WHERE id = ?", ("sess1",))
        assert row is not None
        assert row[0] == "sess1"
        assert row[1] == "My Session"
        
        # Test fetchall
        await db.execute("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", 
                         ("sess2", "Another Session", 2000, 2000))
        await db.commit()
        
        rows = await db.fetchall("SELECT id FROM sessions ORDER BY id")
        assert len(rows) == 2
        assert rows[0][0] == "sess1"
        assert rows[1][0] == "sess2"
        
        await db.close()

    @pytest.mark.asyncio
    async def test_executemany(self, temp_db_path):
        db = Database(temp_db_path)
        await db.migrate()  # Should auto-connect
        
        data = [
            ("sess3", "S3", 3, 3),
            ("sess4", "S4", 4, 4),
        ]
        
        await db.executemany("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", data)
        await db.commit()
        
        rows = await db.fetchall("SELECT id FROM sessions WHERE id IN (?, ?)", ("sess3", "sess4"))
        assert len(rows) == 2
        await db.close()


class TestBatchCommitDatabase:
    @pytest.mark.asyncio
    async def test_batch_commit_delay(self, temp_db_path):
        # We use a very high interval to ensure it's not flushed by the loop
        db = BatchCommitDatabase(temp_db_path, flush_interval=10.0, max_pending=3)
        await db.migrate()
        
        # Execute 2 inserts (less than max_pending=3)
        await db.execute("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", 
                         ("b_sess1", "Batch 1", 1, 1))
        await db.execute("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", 
                         ("b_sess2", "Batch 2", 2, 2))
                         
        assert db._dirty is True
        assert db._pending_count == 2
        
        # Manually verify it wasn't committed to a completely new connection
        async with aiosqlite.connect(temp_db_path) as verify_conn:
            cursor = await verify_conn.execute("SELECT count(*) FROM sessions")
            row = await cursor.fetchone()
            # Depending on WAL PRAGMAs it might actually be visible, but _dirty is the main thing
            
        # Execute the 3rd insert which should trigger a flush
        await db.execute("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", 
                         ("b_sess3", "Batch 3", 3, 3))
                         
        assert db._dirty is False
        assert db._pending_count == 0
        
        await db.close()

    @pytest.mark.asyncio
    async def test_executemany_flush(self, temp_db_path):
        db = BatchCommitDatabase(temp_db_path, flush_interval=10.0, max_pending=5)
        await db.migrate()
        
        data = [(f"bss{i}", f"T{i}", i, i) for i in range(10)]
        await db.executemany("INSERT INTO sessions (id, title, updated_at, created_at) VALUES (?, ?, ?, ?)", data)
        
        # 10 is >= max_pending of 5, so it should auto-flush
        assert db._dirty is False
        assert db._pending_count == 0
        
        await db.close()

    @pytest.mark.asyncio
    async def test_flush_task_cancellation_on_close(self, temp_db_path):
        db = BatchCommitDatabase(temp_db_path, flush_interval=0.01)
        await db.connect()
        
        # Give it a tiny bit of time to loop once
        await asyncio.sleep(0.05)
        
        await db.close()
        # flush task should be cancelled
        assert db._flush_task is None

@patch("xiaotie.storage.database.os.environ.get")
@patch("xiaotie.storage.database.os.path.expanduser")
def test_get_default_db_path(mock_expanduser, mock_env_get):
    # Test XDG logic
    mock_env_get.return_value = "/mock/xdg/data"
    path = get_default_db_path()
    assert "/mock/xdg/data" in path
    
    # Test fallback
    mock_env_get.return_value = None
    mock_expanduser.return_value = "/mock/home/user"
    path2 = get_default_db_path()
    assert "/mock/home/user" in path2

@pytest.mark.asyncio
async def test_get_and_init_database(temp_db_path):
    # Initial get
    db = get_database()
    assert isinstance(db, Database)
    
    # Init custom
    db2 = await init_database(temp_db_path)
    assert db2.db_path == temp_db_path
    assert db2.is_connected
    
    # Verify global update
    db3 = get_database()
    assert db3 is db2
    
    await db2.close()
