from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

from .security import verify_secret_token, verify_source_ip
from .service import TelegramIntegrationService

logger = logging.getLogger(__name__)


class TelegramWebhookServer:
    def __init__(
        self,
        service: TelegramIntegrationService,
        host: str,
        port: int,
        path: str,
        loop: asyncio.AbstractEventLoop,
        secret_token: Optional[str] = None,
        allowed_cidrs: Optional[list[str]] = None,
        max_body_size: int = 2 * 1024 * 1024,
        task_timeout: float = 5.0,
    ):
        self.service = service
        self.host = host
        self.port = port
        self.path = path if path.startswith("/") else f"/{path}"
        self.loop = loop
        self.secret_token = secret_token
        self.allowed_cidrs = allowed_cidrs or []
        self.max_body_size = max_body_size
        self.task_timeout = task_timeout
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def actual_port(self) -> int:
        if not self._server:
            return self.port
        return int(self._server.server_address[1])

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        handler_cls = self._build_handler()
        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def _build_handler(self):
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                parsed = urlparse(self.path)
                if parsed.path != outer.path:
                    self._write_json(404, {"ok": False, "error": "not_found"})
                    return

                remote_ip = self.client_address[0]
                if not verify_source_ip(remote_ip, outer.allowed_cidrs):
                    self._write_json(403, {"ok": False, "error": "forbidden_ip"})
                    return

                provided_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if not verify_secret_token(provided_secret, outer.secret_token):
                    self._write_json(403, {"ok": False, "error": "forbidden_secret"})
                    return

                body_size = int(self.headers.get("Content-Length", "0"))
                if body_size <= 0 or body_size > outer.max_body_size:
                    self._write_json(400, {"ok": False, "error": "invalid_body_size"})
                    return

                raw = self.rfile.read(body_size)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    self._write_json(400, {"ok": False, "error": "invalid_json"})
                    return

                future = asyncio.run_coroutine_threadsafe(
                    outer.service.handle_update_and_reply(payload),
                    outer.loop,
                )
                try:
                    future.result(timeout=outer.task_timeout)
                except Exception as exc:
                    logger.exception("telegram webhook 异步处理失败: %s", exc)
                    self._write_json(500, {"ok": False, "error": "handler_failed"})
                    return

                self._write_json(200, {"ok": True})

            def log_message(self, format: str, *args: Any) -> None:
                logger.info("telegram webhook - " + format, *args)

            def _write_json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return _Handler
