"""LSP 客户端

参考 OpenCode 的 LSP 客户端实现，通过 stdio 与语言服务器通信。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Callable
import threading

from .protocol import (
    Diagnostic, DocumentUri, Position, Range,
    TextDocumentItem, TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    InitializeParams, InitializeResult,
    DidOpenTextDocumentParams, DidCloseTextDocumentParams,
    DidChangeTextDocumentParams, PublishDiagnosticsParams,
    detect_language_id,
)


@dataclass
class LSPConfig:
    """LSP 配置"""
    command: str
    args: list[str] = field(default_factory=list)
    env: Optional[dict[str, str]] = None
    enabled: bool = True


class LSPClient:
    """LSP 客户端"""

    def __init__(
        self,
        config: LSPConfig,
        workspace_dir: str,
        on_diagnostics: Optional[Callable[[str, list[Diagnostic]], None]] = None,
    ):
        self.config = config
        self.workspace_dir = workspace_dir
        self.on_diagnostics = on_diagnostics

        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._diagnostics: dict[DocumentUri, list[Diagnostic]] = {}
        self._open_files: dict[str, int] = {}  # uri -> version
        self._initialized = False
        self._lock = threading.Lock()
        self._read_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """检查 LSP 服务器是否运行中"""
        return self._process is not None and self._process.poll() is None

    async def start(self) -> bool:
        """启动 LSP 服务器"""
        if self.is_running:
            return True

        try:
            env = os.environ.copy()
            if self.config.env:
                env.update(self.config.env)

            self._process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=self.workspace_dir,
            )

            # 启动消息读取任务
            self._read_task = asyncio.create_task(self._read_messages())

            # 初始化
            await self._initialize()
            self._initialized = True

            return True

        except Exception as e:
            print(f"LSP 启动失败: {e}")
            return False

    async def stop(self) -> None:
        """停止 LSP 服务器"""
        if not self.is_running:
            return

        try:
            # 关闭所有打开的文件
            for uri in list(self._open_files.keys()):
                file_path = uri.replace("file://", "")
                await self.close_file(file_path)

            # 发送 shutdown 请求
            await self._request("shutdown", None)

            # 发送 exit 通知
            await self._notify("exit", None)

        except Exception:
            pass

        finally:
            if self._read_task:
                self._read_task.cancel()
                try:
                    await self._read_task
                except asyncio.CancelledError:
                    pass

            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self._process = None

            self._initialized = False

    async def _initialize(self) -> None:
        """初始化 LSP 连接"""
        params = InitializeParams(
            processId=os.getpid(),
            rootUri=f"file://{self.workspace_dir}",
            capabilities={
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "didSave": True,
                    },
                    "publishDiagnostics": {
                        "versionSupport": True,
                    },
                },
                "workspace": {
                    "workspaceFolders": True,
                },
            },
            workspaceFolders=[
                {"uri": f"file://{self.workspace_dir}", "name": Path(self.workspace_dir).name}
            ],
        )

        result = await self._request("initialize", params.to_dict())

        # 发送 initialized 通知
        await self._notify("initialized", {})

    async def open_file(self, file_path: str) -> None:
        """打开文件"""
        if not self._initialized:
            return

        uri = f"file://{os.path.abspath(file_path)}"

        if uri in self._open_files:
            return  # 已打开

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"读取文件失败: {e}")
            return

        params = DidOpenTextDocumentParams(
            textDocument=TextDocumentItem(
                uri=uri,
                languageId=detect_language_id(file_path),
                version=1,
                text=content,
            )
        )

        await self._notify("textDocument/didOpen", params.to_dict())
        self._open_files[uri] = 1

    async def close_file(self, file_path: str) -> None:
        """关闭文件"""
        if not self._initialized:
            return

        uri = f"file://{os.path.abspath(file_path)}"

        if uri not in self._open_files:
            return

        params = DidCloseTextDocumentParams(
            textDocument=TextDocumentIdentifier(uri=uri)
        )

        await self._notify("textDocument/didClose", params.to_dict())
        del self._open_files[uri]

    async def notify_change(self, file_path: str) -> None:
        """通知文件变更"""
        if not self._initialized:
            return

        uri = f"file://{os.path.abspath(file_path)}"

        if uri not in self._open_files:
            await self.open_file(file_path)
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        version = self._open_files[uri] + 1
        self._open_files[uri] = version

        params = DidChangeTextDocumentParams(
            textDocument=VersionedTextDocumentIdentifier(
                uri=uri,
                version=version,
            ),
            contentChanges=[{"text": content}],
        )

        await self._notify("textDocument/didChange", params.to_dict())

    def get_diagnostics(self, file_path: Optional[str] = None) -> dict[str, list[Diagnostic]]:
        """获取诊断信息"""
        if file_path:
            uri = f"file://{os.path.abspath(file_path)}"
            if uri in self._diagnostics:
                return {file_path: self._diagnostics[uri]}
            return {}

        # 返回所有诊断
        result = {}
        for uri, diags in self._diagnostics.items():
            path = uri.replace("file://", "")
            result[path] = diags
        return result

    async def _request(self, method: str, params: Optional[dict]) -> Any:
        """发送请求并等待响应"""
        if not self.is_running:
            raise RuntimeError("LSP 服务器未运行")

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        await self._send_message(message)

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"LSP 请求超时: {method}")

    async def _notify(self, method: str, params: Optional[dict]) -> None:
        """发送通知（无需响应）"""
        if not self.is_running:
            return

        message = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params

        await self._send_message(message)

    async def _send_message(self, message: dict) -> None:
        """发送 LSP 消息"""
        if not self._process or not self._process.stdin:
            return

        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        data = (header + content).encode("utf-8")

        try:
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except Exception as e:
            print(f"发送 LSP 消息失败: {e}")

    async def _read_messages(self) -> None:
        """读取 LSP 消息"""
        if not self._process or not self._process.stdout:
            return

        loop = asyncio.get_event_loop()

        while self.is_running:
            try:
                # 读取 header
                header_data = await loop.run_in_executor(
                    None, self._read_header
                )
                if not header_data:
                    break

                content_length = self._parse_content_length(header_data)
                if content_length <= 0:
                    continue

                # 读取 content
                content = await loop.run_in_executor(
                    None, lambda: self._process.stdout.read(content_length)
                )
                if not content:
                    break

                # 解析消息
                message = json.loads(content.decode("utf-8"))
                await self._handle_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"读取 LSP 消息失败: {e}")
                await asyncio.sleep(0.1)

    def _read_header(self) -> Optional[bytes]:
        """读取 LSP 消息头"""
        if not self._process or not self._process.stdout:
            return None

        header = b""
        while True:
            byte = self._process.stdout.read(1)
            if not byte:
                return None
            header += byte
            if header.endswith(b"\r\n\r\n"):
                return header

    def _parse_content_length(self, header: bytes) -> int:
        """解析 Content-Length"""
        for line in header.decode("utf-8").split("\r\n"):
            if line.lower().startswith("content-length:"):
                return int(line.split(":")[1].strip())
        return 0

    async def _handle_message(self, message: dict) -> None:
        """处理 LSP 消息"""
        if "id" in message and "result" in message:
            # 响应
            request_id = message["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(message.get("result"))

        elif "id" in message and "error" in message:
            # 错误响应
            request_id = message["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    error = message["error"]
                    future.set_exception(
                        RuntimeError(f"LSP 错误: {error.get('message', 'Unknown')}")
                    )

        elif "method" in message and "id" not in message:
            # 通知
            await self._handle_notification(message)

        elif "method" in message and "id" in message:
            # 服务器请求
            await self._handle_server_request(message)

    async def _handle_notification(self, message: dict) -> None:
        """处理通知"""
        method = message.get("method", "")
        params = message.get("params", {})

        if method == "textDocument/publishDiagnostics":
            self._handle_diagnostics(params)

    def _handle_diagnostics(self, params: dict) -> None:
        """处理诊断通知"""
        try:
            diag_params = PublishDiagnosticsParams.from_dict(params)
            self._diagnostics[diag_params.uri] = diag_params.diagnostics

            if self.on_diagnostics:
                file_path = diag_params.uri.replace("file://", "")
                self.on_diagnostics(file_path, diag_params.diagnostics)

        except Exception as e:
            print(f"处理诊断失败: {e}")

    async def _handle_server_request(self, message: dict) -> None:
        """处理服务器请求"""
        request_id = message.get("id")
        method = message.get("method", "")

        # 默认响应
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": None,
        }

        if method == "workspace/configuration":
            response["result"] = [{}]
        elif method == "client/registerCapability":
            response["result"] = None

        await self._send_message(response)
