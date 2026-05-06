from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ..schema import ToolResult
from ..storage.database import get_default_db_path
from ..telegram import TelegramBotClient, TelegramIntegrationService, TelegramWebhookServer
from .base import Tool


class TelegramTool(Tool):
    def __init__(
        self,
        bot_token: str,
        webhook_host: str = "0.0.0.0",
        webhook_port: int = 9000,
        webhook_path: str = "/telegram/webhook",
        webhook_secret_token: Optional[str] = None,
        db_path: Optional[str] = None,
        allowed_chat_ids: Optional[list[int]] = None,
        allowed_cidrs: Optional[list[str]] = None,
    ):
        super().__init__()
        self.client = TelegramBotClient(bot_token=bot_token)
        self.service = TelegramIntegrationService(
            bot_client=self.client,
            db_path=db_path or get_default_db_path(),
            allowed_chat_ids=allowed_chat_ids,
        )
        self.webhook_host = webhook_host
        self.webhook_port = webhook_port
        self.webhook_path = webhook_path
        self.webhook_secret_token = webhook_secret_token
        self.allowed_cidrs = allowed_cidrs or []
        self._server: Optional[TelegramWebhookServer] = None

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def description(self) -> str:
        return "Telegram Bot 集成工具，支持 webhook、消息收发、身份绑定与数据查询"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "get_me",
                        "set_webhook",
                        "get_webhook_info",
                        "delete_webhook",
                        "start_webhook_server",
                        "stop_webhook_server",
                        "send_message",
                        "send_photo",
                        "send_document",
                        "process_update",
                        "register_user",
                    ],
                },
                "webhook_url": {"type": "string"},
                "chat_id": {"type": ["integer", "string"]},
                "text": {"type": "string"},
                "photo": {"type": "string"},
                "document": {"type": "string"},
                "caption": {"type": "string"},
                "telegram_user_id": {"type": "integer"},
                "app_user_id": {"type": "string"},
                "update": {"type": "object"},
                "drop_pending_updates": {"type": "boolean"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        try:
            if action == "get_me":
                resp = await self.client.get_me()
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "set_webhook":
                return await self._set_webhook(kwargs)
            if action == "get_webhook_info":
                resp = await self.client.get_webhook_info()
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "delete_webhook":
                resp = await self.client.delete_webhook(
                    drop_pending_updates=bool(kwargs.get("drop_pending_updates", False))
                )
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "start_webhook_server":
                return await self._start_webhook_server()
            if action == "stop_webhook_server":
                return self._stop_webhook_server()
            if action == "send_message":
                resp = await self.client.send_message(
                    chat_id=kwargs["chat_id"],
                    text=kwargs["text"],
                )
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "send_photo":
                resp = await self.client.send_photo(
                    chat_id=kwargs["chat_id"],
                    photo=kwargs["photo"],
                    caption=kwargs.get("caption"),
                )
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "send_document":
                resp = await self.client.send_document(
                    chat_id=kwargs["chat_id"],
                    document=kwargs["document"],
                    caption=kwargs.get("caption"),
                )
                return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))
            if action == "process_update":
                update = kwargs.get("update", {})
                reply = await self.service.process_update(update)
                return ToolResult(success=True, content=reply or "")
            if action == "register_user":
                user_id = int(kwargs["telegram_user_id"])
                app_user_id = str(kwargs["app_user_id"])
                self.service.register_user(user_id, app_user_id)
                return ToolResult(
                    success=True, content=f"已绑定 Telegram 用户 {user_id} -> {app_user_id}"
                )
            return ToolResult(success=False, content=f"不支持的 action: {action}")
        except Exception as exc:
            return ToolResult(success=False, content=f"Telegram 操作失败: {exc}")

    async def _set_webhook(self, kwargs: dict[str, Any]) -> ToolResult:
        webhook_url = kwargs.get("webhook_url")
        if not webhook_url:
            return ToolResult(success=False, content="webhook_url 不能为空")
        resp = await self.client.set_webhook(
            webhook_url=webhook_url,
            secret_token=self.webhook_secret_token,
            drop_pending_updates=bool(kwargs.get("drop_pending_updates", False)),
        )
        return ToolResult(success=True, content=json.dumps(resp, ensure_ascii=False))

    async def _start_webhook_server(self) -> ToolResult:
        if self._server and self._server.is_running:
            return ToolResult(
                success=True,
                content=f"webhook server 已运行: {self.webhook_host}:{self._server.actual_port}{self.webhook_path}",
            )
        loop = asyncio.get_running_loop()
        self._server = TelegramWebhookServer(
            service=self.service,
            host=self.webhook_host,
            port=self.webhook_port,
            path=self.webhook_path,
            loop=loop,
            secret_token=self.webhook_secret_token,
            allowed_cidrs=self.allowed_cidrs,
        )
        await asyncio.to_thread(self._server.start)
        return ToolResult(
            success=True,
            content=f"webhook server 启动成功: {self.webhook_host}:{self._server.actual_port}{self.webhook_path}",
        )

    def _stop_webhook_server(self) -> ToolResult:
        if not self._server or not self._server.is_running:
            return ToolResult(success=True, content="webhook server 未运行")
        self._server.stop()
        return ToolResult(success=True, content="webhook server 已停止")
