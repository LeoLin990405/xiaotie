from __future__ import annotations

import asyncio
import json
import sqlite3
import urllib.request
from pathlib import Path

import pytest

from xiaotie.telegram.client import TelegramAPIError, TelegramBotClient
from xiaotie.telegram.security import verify_secret_token, verify_source_ip
from xiaotie.telegram.service import TelegramIntegrationService
from xiaotie.telegram.webhook import TelegramWebhookServer


class FakeBotClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
        return {"ok": True, "result": {"chat_id": chat_id, "text": text}}


def _seed_db(path: Path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE messages (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, parts TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("s1", "订单会话", 1730000000000),
        )
        conn.execute(
            "INSERT INTO messages (id, session_id, role, parts, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "m1",
                "s1",
                "user",
                json.dumps([{"type": "text", "text": "hello telegram"}], ensure_ascii=False),
                1730000001000,
            ),
        )
        conn.commit()


def test_verify_secret_token():
    assert verify_secret_token("abc", "abc")
    assert not verify_secret_token("abc", "def")
    assert verify_secret_token(None, None)


def test_verify_source_ip():
    assert verify_source_ip("149.154.167.10", ["149.154.160.0/20"])
    assert not verify_source_ip("8.8.8.8", ["149.154.160.0/20"])
    assert verify_source_ip("8.8.8.8", None)


@pytest.mark.asyncio
async def test_service_handles_sessions_command(tmp_path):
    db_path = tmp_path / "telegram.db"
    _seed_db(db_path)
    service = TelegramIntegrationService(bot_client=FakeBotClient(), db_path=str(db_path))
    update = {"message": {"chat": {"id": 1001}, "from": {"id": 1}, "text": "/sessions"}}
    result = await service.process_update(update)
    assert "最近会话" in result
    assert "订单会话" in result


@pytest.mark.asyncio
async def test_service_handles_messages_command(tmp_path):
    db_path = tmp_path / "telegram.db"
    _seed_db(db_path)
    service = TelegramIntegrationService(bot_client=FakeBotClient(), db_path=str(db_path))
    update = {"message": {"chat": {"id": 1001}, "from": {"id": 1}, "text": "/messages s1"}}
    result = await service.process_update(update)
    assert "最近消息" in result
    assert "hello telegram" in result


@pytest.mark.asyncio
async def test_webhook_server_handles_update():
    bot = FakeBotClient()
    service = TelegramIntegrationService(bot_client=bot, db_path=None)
    loop = asyncio.get_running_loop()
    server = TelegramWebhookServer(
        service=service,
        host="127.0.0.1",
        port=0,
        path="/telegram/webhook",
        loop=loop,
        secret_token="secret",
    )
    await asyncio.to_thread(server.start)
    try:
        payload = {"message": {"chat": {"id": 7}, "from": {"id": 8}, "text": "ping"}}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.actual_port}/telegram/webhook",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Telegram-Bot-Api-Secret-Token", "secret")
        def _post():
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status

        status = await asyncio.to_thread(_post)
        assert status == 200
        await asyncio.sleep(0.1)
        assert bot.sent
        assert bot.sent[0]["chat_id"] == 7
    finally:
        await asyncio.to_thread(server.stop)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_client_request_success(monkeypatch):
    client = TelegramBotClient("token")

    def _fake_urlopen(req, timeout):
        _ = (req, timeout)
        return _FakeHTTPResponse({"ok": True, "result": {"id": 1}})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    result = client._request_sync("getMe", {})
    assert result["ok"] is True


def test_client_request_fail(monkeypatch):
    client = TelegramBotClient("token")

    def _fake_urlopen(req, timeout):
        _ = (req, timeout)
        return _FakeHTTPResponse({"ok": False, "description": "bad request"})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(TelegramAPIError):
        client._request_sync("getMe", {})
