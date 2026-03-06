from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class TelegramAPIError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(self, bot_token: str, timeout: float = 10.0):
        if not bot_token:
            raise ValueError("bot_token 不能为空")
        self.bot_token = bot_token
        self.timeout = timeout
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def get_me(self) -> dict[str, Any]:
        return await self._request("getMe", {})

    async def set_webhook(
        self,
        webhook_url: str,
        secret_token: Optional[str] = None,
        drop_pending_updates: bool = False,
        max_connections: int = 40,
    ) -> dict[str, Any]:
        payload: Dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": drop_pending_updates,
            "max_connections": max_connections,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._request("setWebhook", payload)

    async def get_webhook_info(self) -> dict[str, Any]:
        return await self._request("getWebhookInfo", {})

    async def delete_webhook(self, drop_pending_updates: bool = False) -> dict[str, Any]:
        return await self._request(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._request("sendMessage", payload)

    async def send_photo(
        self,
        chat_id: str | int,
        photo: str,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "photo": photo}
        if caption:
            payload["caption"] = caption
        return await self._request("sendPhoto", payload)

    async def send_document(
        self,
        chat_id: str | int,
        document: str,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "document": document}
        if caption:
            payload["caption"] = caption
        return await self._request("sendDocument", payload)

    async def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, payload)

    def _request_sync(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{method}"
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
        if not data.get("ok"):
            raise TelegramAPIError(data.get("description", "Telegram API 请求失败"))
        return data
