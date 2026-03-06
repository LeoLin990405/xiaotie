"""核心业务冒烟测试"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xiaotie.proxy.storage import CapturedRequest, RequestStorage
from xiaotie.scraper.auth import AuthConfig, AuthHandler, AuthMethod
from xiaotie.storage import MessageRecord, MessageStore, SessionRecord, SessionStore, init_database


@pytest.mark.smoke
def test_smoke_user_login_flow():
    config = AuthConfig(method=AuthMethod.BEARER, token="smoke-token")
    handler = AuthHandler(config)

    result = handler.apply_to_kwargs({"headers": {"Accept": "application/json"}})

    assert result["headers"]["Authorization"] == "Bearer smoke-token"
    assert result["headers"]["Accept"] == "application/json"


@pytest.mark.smoke
def test_smoke_key_transaction_flow(tmp_path):
    storage = RequestStorage(max_entries=20)
    entry = CapturedRequest(
        url="https://trade.example.com/api/settlement",
        method="POST",
        host="trade.example.com",
        path="/api/settlement",
        status_code=200,
        response_size=512,
        duration_ms=18.6,
    )
    storage.add(entry)

    records = storage.filter(method="POST", status_code=200, path_prefix="/api")
    assert len(records) == 1
    assert records[0].host == "trade.example.com"

    output_file = Path(tmp_path) / "transaction-smoke.json"
    storage.export_json(output_file)
    exported = json.loads(output_file.read_text(encoding="utf-8"))
    assert len(exported) == 1
    assert exported[0]["path"] == "/api/settlement"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_data_persistence_flow(tmp_path):
    db_path = Path(tmp_path) / "smoke-persistence.db"
    database = await init_database(str(db_path))
    session_store = SessionStore(database)
    message_store = MessageStore(database)

    session = SessionRecord(title="smoke-session")
    await session_store.create(session)

    message = MessageRecord(
        session_id=session.id,
        role="user",
        parts=[{"type": "text", "text": "smoke payload"}],
    )
    await message_store.create(message)

    stored_session = await session_store.get(session.id)
    stored_messages = await message_store.list_by_session(session.id)

    assert stored_session is not None
    assert stored_session.title == "smoke-session"
    assert len(stored_messages) == 1
    assert stored_messages[0].content == "smoke payload"

    await database.close()
