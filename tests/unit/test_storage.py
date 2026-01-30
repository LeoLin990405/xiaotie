"""存储模块测试"""

import os
import tempfile

import pytest

from xiaotie.storage import (
    Database,
    MessageRecord,
    MessageStore,
    SessionRecord,
    SessionStore,
    init_database,
)


@pytest.fixture
async def db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    database = await init_database(db_path)
    yield database

    await database.close()
    os.unlink(db_path)


@pytest.fixture
async def session_store(db):
    """创建会话存储"""
    return SessionStore(db)


@pytest.fixture
async def message_store(db):
    """创建消息存储"""
    return MessageStore(db)


class TestSessionStore:
    """会话存储测试"""

    async def test_create_session(self, session_store):
        """测试创建会话"""
        session = SessionRecord(title="测试会话")
        created = await session_store.create(session)

        assert created.id == session.id
        assert created.title == "测试会话"

    async def test_get_session(self, session_store):
        """测试获取会话"""
        session = SessionRecord(title="测试会话")
        await session_store.create(session)

        fetched = await session_store.get(session.id)
        assert fetched is not None
        assert fetched.id == session.id
        assert fetched.title == "测试会话"

    async def test_get_nonexistent_session(self, session_store):
        """测试获取不存在的会话"""
        fetched = await session_store.get("nonexistent")
        assert fetched is None

    async def test_list_sessions(self, session_store):
        """测试列出会话"""
        for i in range(5):
            await session_store.create(SessionRecord(title=f"会话 {i}"))

        sessions = await session_store.list(limit=10)
        assert len(sessions) == 5

    async def test_update_session(self, session_store):
        """测试更新会话"""
        session = SessionRecord(title="原标题")
        await session_store.create(session)

        session.title = "新标题"
        await session_store.update(session)

        fetched = await session_store.get(session.id)
        assert fetched.title == "新标题"

    async def test_delete_session(self, session_store):
        """测试删除会话"""
        session = SessionRecord(title="待删除")
        await session_store.create(session)

        deleted = await session_store.delete(session.id)
        assert deleted is True

        fetched = await session_store.get(session.id)
        assert fetched is None

    async def test_update_tokens(self, session_store):
        """测试更新 token 统计"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        await session_store.update_tokens(session.id, 100, 50, 0.01)

        fetched = await session_store.get(session.id)
        assert fetched.prompt_tokens == 100
        assert fetched.completion_tokens == 50
        assert fetched.cost == 0.01

    async def test_search_sessions(self, session_store):
        """测试搜索会话"""
        await session_store.create(SessionRecord(title="Python 开发"))
        await session_store.create(SessionRecord(title="JavaScript 开发"))
        await session_store.create(SessionRecord(title="其他"))

        results = await session_store.search("开发")
        assert len(results) == 2


class TestMessageStore:
    """消息存储测试"""

    async def test_create_message(self, session_store, message_store):
        """测试创建消息"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        message = MessageRecord(
            session_id=session.id,
            role="user",
            parts=[{"type": "text", "text": "你好"}],
        )
        created = await message_store.create(message)

        assert created.id == message.id
        assert created.content == "你好"

    async def test_get_message(self, session_store, message_store):
        """测试获取消息"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        message = MessageRecord(
            session_id=session.id,
            role="assistant",
            parts=[{"type": "text", "text": "你好！"}],
        )
        await message_store.create(message)

        fetched = await message_store.get(message.id)
        assert fetched is not None
        assert fetched.content == "你好！"

    async def test_list_by_session(self, session_store, message_store):
        """测试列出会话消息"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        for i in range(5):
            message = MessageRecord(
                session_id=session.id,
                role="user",
                parts=[{"type": "text", "text": f"消息 {i}"}],
            )
            await message_store.create(message)

        messages = await message_store.list_by_session(session.id)
        assert len(messages) == 5

    async def test_delete_message(self, session_store, message_store):
        """测试删除消息"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        message = MessageRecord(
            session_id=session.id,
            role="user",
            parts=[{"type": "text", "text": "待删除"}],
        )
        await message_store.create(message)

        deleted = await message_store.delete(message.id)
        assert deleted is True

        fetched = await message_store.get(message.id)
        assert fetched is None

    async def test_cascade_delete(self, session_store, message_store):
        """测试级联删除"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        message = MessageRecord(
            session_id=session.id,
            role="user",
            parts=[{"type": "text", "text": "测试"}],
        )
        await message_store.create(message)

        # 删除会话应该级联删除消息
        await session_store.delete(session.id)

        fetched = await message_store.get(message.id)
        assert fetched is None

    async def test_message_with_thinking(self, session_store, message_store):
        """测试带思考的消息"""
        session = SessionRecord(title="测试")
        await session_store.create(session)

        message = MessageRecord(
            session_id=session.id,
            role="assistant",
            parts=[
                {"type": "thinking", "text": "让我思考一下..."},
                {"type": "text", "text": "答案是 42"},
            ],
        )
        await message_store.create(message)

        fetched = await message_store.get(message.id)
        assert fetched.thinking == "让我思考一下..."
        assert fetched.content == "答案是 42"


class TestMessageRecord:
    """消息记录测试"""

    def test_content_property(self):
        """测试 content 属性"""
        message = MessageRecord()
        message.content = "测试内容"

        assert message.content == "测试内容"
        assert message.parts == [{"type": "text", "text": "测试内容"}]

    def test_thinking_property(self):
        """测试 thinking 属性"""
        message = MessageRecord()
        message.content = "回答"
        message.thinking = "思考过程"

        assert message.thinking == "思考过程"
        assert message.content == "回答"
        assert len(message.parts) == 2
