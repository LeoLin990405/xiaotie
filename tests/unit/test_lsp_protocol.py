"""LSP 协议测试

测试 LSP 客户端初始化、诊断信息获取、服务器管理、错误处理。
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.lsp.protocol import (
    Diagnostic,
    DiagnosticRelatedInformation,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    InitializeParams,
    InitializeResult,
    Location,
    Position,
    PublishDiagnosticsParams,
    Range,
    TextDocumentIdentifier,
    TextDocumentItem,
    VersionedTextDocumentIdentifier,
    detect_language_id,
)
from xiaotie.lsp.client import LSPClient, LSPConfig
from xiaotie.lsp.manager import LSPManager, format_diagnostics
from xiaotie.lsp.diagnostics import DiagnosticsTool


# =============================================================================
# LSP 协议类型序列化/反序列化
# =============================================================================


class TestPosition:
    """Position 类型测试"""

    def test_basic(self):
        pos = Position(line=10, character=5)
        assert pos.line == 10
        assert pos.character == 5

    def test_to_dict(self):
        pos = Position(line=0, character=0)
        assert pos.to_dict() == {"line": 0, "character": 0}

    def test_from_dict(self):
        pos = Position.from_dict({"line": 3, "character": 7})
        assert pos.line == 3
        assert pos.character == 7


class TestRange:
    """Range 类型测试"""

    def test_basic(self):
        r = Range(start=Position(0, 0), end=Position(0, 10))
        assert r.start.line == 0
        assert r.end.character == 10

    def test_to_dict(self):
        r = Range(start=Position(1, 2), end=Position(3, 4))
        d = r.to_dict()
        assert d["start"] == {"line": 1, "character": 2}
        assert d["end"] == {"line": 3, "character": 4}

    def test_from_dict(self):
        data = {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 20}}
        r = Range.from_dict(data)
        assert r.start.line == 5
        assert r.end.character == 20


class TestLocation:
    """Location 类型测试"""

    def test_basic(self):
        loc = Location(
            uri="file:///test.py",
            range=Range(start=Position(0, 0), end=Position(0, 5)),
        )
        assert loc.uri == "file:///test.py"

    def test_roundtrip(self):
        loc = Location(
            uri="file:///test.py",
            range=Range(start=Position(1, 2), end=Position(3, 4)),
        )
        d = loc.to_dict()
        restored = Location.from_dict(d)
        assert restored.uri == loc.uri
        assert restored.range.start.line == 1


class TestTextDocumentTypes:
    """文档类型测试"""

    def test_text_document_identifier(self):
        tdi = TextDocumentIdentifier(uri="file:///test.py")
        assert tdi.to_dict() == {"uri": "file:///test.py"}

    def test_versioned_text_document_identifier(self):
        vtdi = VersionedTextDocumentIdentifier(uri="file:///test.py", version=3)
        d = vtdi.to_dict()
        assert d["uri"] == "file:///test.py"
        assert d["version"] == 3

    def test_text_document_item(self):
        item = TextDocumentItem(
            uri="file:///test.py",
            languageId="python",
            version=1,
            text="print('hello')",
        )
        d = item.to_dict()
        assert d["languageId"] == "python"
        assert d["text"] == "print('hello')"


class TestDiagnosticSeverity:
    """诊断严重程度测试"""

    def test_values(self):
        assert DiagnosticSeverity.Error == 1
        assert DiagnosticSeverity.Warning == 2
        assert DiagnosticSeverity.Information == 3
        assert DiagnosticSeverity.Hint == 4


class TestDiagnostic:
    """Diagnostic 类型测试"""

    def _make_diagnostic(self, severity=DiagnosticSeverity.Error, message="test error"):
        return Diagnostic(
            range=Range(start=Position(0, 0), end=Position(0, 5)),
            message=message,
            severity=severity,
            code="E001",
            source="pylsp",
        )

    def test_basic(self):
        diag = self._make_diagnostic()
        assert diag.message == "test error"
        assert diag.severity == DiagnosticSeverity.Error
        assert diag.code == "E001"
        assert diag.source == "pylsp"

    def test_severity_str(self):
        assert self._make_diagnostic(DiagnosticSeverity.Error).severity_str == "Error"
        assert self._make_diagnostic(DiagnosticSeverity.Warning).severity_str == "Warning"
        assert self._make_diagnostic(DiagnosticSeverity.Information).severity_str == "Info"
        assert self._make_diagnostic(DiagnosticSeverity.Hint).severity_str == "Hint"

    def test_severity_str_none(self):
        diag = Diagnostic(
            range=Range(start=Position(0, 0), end=Position(0, 5)),
            message="test",
        )
        assert diag.severity_str == "Unknown"

    def test_format(self):
        diag = self._make_diagnostic()
        formatted = diag.format()
        assert "[pylsp]" in formatted
        assert "Error" in formatted
        assert "line 1" in formatted
        assert "test error" in formatted

    def test_from_dict(self):
        data = {
            "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 10}},
            "message": "undefined variable",
            "severity": 1,
            "code": "F821",
            "source": "pyflakes",
        }
        diag = Diagnostic.from_dict(data)
        assert diag.message == "undefined variable"
        assert diag.severity == DiagnosticSeverity.Error
        assert diag.code == "F821"
        assert diag.source == "pyflakes"

    def test_from_dict_with_related_info(self):
        data = {
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
            "message": "test",
            "relatedInformation": [
                {
                    "location": {
                        "uri": "file:///other.py",
                        "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 5}},
                    },
                    "message": "related info",
                }
            ],
        }
        diag = Diagnostic.from_dict(data)
        assert diag.relatedInformation is not None
        assert len(diag.relatedInformation) == 1
        assert diag.relatedInformation[0].message == "related info"

    def test_from_dict_minimal(self):
        data = {
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
            "message": "minimal",
        }
        diag = Diagnostic.from_dict(data)
        assert diag.severity is None
        assert diag.code is None
        assert diag.source is None


class TestPublishDiagnosticsParams:
    """PublishDiagnosticsParams 测试"""

    def test_from_dict(self):
        data = {
            "uri": "file:///test.py",
            "diagnostics": [
                {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
                    "message": "error here",
                    "severity": 1,
                }
            ],
            "version": 2,
        }
        params = PublishDiagnosticsParams.from_dict(data)
        assert params.uri == "file:///test.py"
        assert len(params.diagnostics) == 1
        assert params.version == 2

    def test_from_dict_no_version(self):
        data = {
            "uri": "file:///test.py",
            "diagnostics": [],
        }
        params = PublishDiagnosticsParams.from_dict(data)
        assert params.version is None


class TestInitializeParams:
    """LSP InitializeParams 测试"""

    def test_to_dict(self):
        params = InitializeParams(
            processId=1234,
            rootUri="file:///workspace",
            capabilities={"textDocument": {}},
        )
        d = params.to_dict()
        assert d["processId"] == 1234
        assert d["rootUri"] == "file:///workspace"

    def test_to_dict_with_workspace_folders(self):
        params = InitializeParams(
            processId=1234,
            rootUri="file:///workspace",
            workspaceFolders=[{"uri": "file:///workspace", "name": "ws"}],
        )
        d = params.to_dict()
        assert "workspaceFolders" in d


class TestInitializeResult:
    """LSP InitializeResult 测试"""

    def test_from_dict(self):
        data = {"capabilities": {"textDocumentSync": 1}}
        result = InitializeResult.from_dict(data)
        assert result.capabilities["textDocumentSync"] == 1

    def test_from_dict_empty(self):
        result = InitializeResult.from_dict({})
        assert result.capabilities == {}


class TestDetectLanguageId:
    """语言检测测试"""

    def test_python(self):
        assert detect_language_id("test.py") == "python"

    def test_javascript(self):
        assert detect_language_id("app.js") == "javascript"

    def test_typescript(self):
        assert detect_language_id("app.ts") == "typescript"

    def test_go(self):
        assert detect_language_id("main.go") == "go"

    def test_rust(self):
        assert detect_language_id("lib.rs") == "rust"

    def test_unknown(self):
        assert detect_language_id("file.xyz") == "plaintext"

    def test_case_insensitive(self):
        assert detect_language_id("TEST.PY") == "python"


class TestDidOpenCloseChangeParams:
    """文档操作参数测试"""

    def test_did_open(self):
        params = DidOpenTextDocumentParams(
            textDocument=TextDocumentItem(
                uri="file:///test.py", languageId="python", version=1, text="x = 1"
            )
        )
        d = params.to_dict()
        assert d["textDocument"]["languageId"] == "python"

    def test_did_close(self):
        params = DidCloseTextDocumentParams(
            textDocument=TextDocumentIdentifier(uri="file:///test.py")
        )
        d = params.to_dict()
        assert d["textDocument"]["uri"] == "file:///test.py"

    def test_did_change(self):
        params = DidChangeTextDocumentParams(
            textDocument=VersionedTextDocumentIdentifier(uri="file:///test.py", version=2),
            contentChanges=[{"text": "x = 2"}],
        )
        d = params.to_dict()
        assert d["textDocument"]["version"] == 2
        assert d["contentChanges"][0]["text"] == "x = 2"


# =============================================================================
# LSP 客户端测试
# =============================================================================


class TestLSPClient:
    """LSP 客户端测试"""

    def test_config(self):
        config = LSPConfig(command="pylsp", args=[], enabled=True)
        assert config.command == "pylsp"
        assert config.enabled

    def test_config_disabled(self):
        config = LSPConfig(command="pylsp", enabled=False)
        assert not config.enabled

    def test_client_init(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        assert not client.is_running
        assert not client._initialized

    def test_get_diagnostics_empty(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        assert client.get_diagnostics() == {}

    def test_get_diagnostics_for_file(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        uri = "file:///tmp/workspace/test.py"
        client._diagnostics[uri] = [
            Diagnostic(
                range=Range(start=Position(0, 0), end=Position(0, 5)),
                message="test error",
                severity=DiagnosticSeverity.Error,
            )
        ]
        result = client.get_diagnostics("/tmp/workspace/test.py")
        assert "/tmp/workspace/test.py" in result
        assert len(result["/tmp/workspace/test.py"]) == 1

    def test_get_diagnostics_file_not_found(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        result = client.get_diagnostics("/nonexistent.py")
        assert result == {}

    def test_handle_diagnostics(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        params = {
            "uri": "file:///tmp/test.py",
            "diagnostics": [
                {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
                    "message": "syntax error",
                    "severity": 1,
                }
            ],
        }
        client._handle_diagnostics(params)
        assert "file:///tmp/test.py" in client._diagnostics
        assert len(client._diagnostics["file:///tmp/test.py"]) == 1

    def test_handle_diagnostics_with_callback(self):
        config = LSPConfig(command="pylsp")
        callback_called = []
        client = LSPClient(
            config, "/tmp/workspace",
            on_diagnostics=lambda path, diags: callback_called.append((path, diags)),
        )
        params = {
            "uri": "file:///tmp/test.py",
            "diagnostics": [
                {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
                    "message": "warning",
                    "severity": 2,
                }
            ],
        }
        client._handle_diagnostics(params)
        assert len(callback_called) == 1
        assert callback_called[0][0] == "/tmp/test.py"

    @pytest.mark.asyncio
    async def test_handle_message_response(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        client._pending_requests[1] = future
        await client._handle_message({"id": 1, "result": {"capabilities": {}}})
        assert future.done()
        assert future.result() == {"capabilities": {}}

    @pytest.mark.asyncio
    async def test_handle_message_error_response(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        client._pending_requests[1] = future
        await client._handle_message({"id": 1, "error": {"code": -32600, "message": "Invalid"}})
        assert future.done()
        with pytest.raises(RuntimeError, match="LSP"):
            future.result()

    @pytest.mark.asyncio
    async def test_handle_notification(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        msg = {
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": "file:///test.py",
                "diagnostics": [],
            },
        }
        await client._handle_notification(msg)
        assert "file:///test.py" in client._diagnostics

    @pytest.mark.asyncio
    async def test_handle_server_request(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        client._process = MagicMock()
        client._process.stdin = MagicMock()
        client._process.stdin.write = MagicMock()
        client._process.stdin.flush = MagicMock()
        client._process.poll = MagicMock(return_value=None)
        msg = {"id": 1, "method": "workspace/configuration", "params": {}}
        await client._handle_server_request(msg)

    def test_parse_content_length(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        header = b"Content-Length: 42\r\n\r\n"
        assert client._parse_content_length(header) == 42

    def test_parse_content_length_missing(self):
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        header = b"X-Custom: value\r\n\r\n"
        assert client._parse_content_length(header) == 0


# =============================================================================
# LSP Manager 测试
# =============================================================================


class TestLSPManager:
    """LSP 管理器测试"""

    def test_init(self):
        manager = LSPManager("/tmp/workspace")
        assert manager.workspace_dir == "/tmp/workspace"
        assert manager._clients == {}

    def test_get_config_default(self):
        manager = LSPManager("/tmp/workspace")
        config = manager.get_config("python")
        assert config is not None
        assert config.command == "pylsp"

    def test_get_config_custom(self):
        custom = {"python": LSPConfig(command="pyright", args=["--stdio"])}
        manager = LSPManager("/tmp/workspace", configs=custom)
        config = manager.get_config("python")
        assert config.command == "pyright"

    def test_get_config_unknown(self):
        manager = LSPManager("/tmp/workspace")
        config = manager.get_config("brainfuck")
        assert config is None

    @pytest.mark.asyncio
    async def test_get_diagnostics_empty(self):
        manager = LSPManager("/tmp/workspace")
        result = await manager.get_diagnostics()
        assert result == {}

    @pytest.mark.asyncio
    async def test_stop_all(self):
        manager = LSPManager("/tmp/workspace")
        mock_client = MagicMock()
        mock_client.stop = AsyncMock()
        manager._clients["python"] = mock_client
        await manager.stop_all()
        mock_client.stop.assert_called_once()
        assert manager._clients == {}

    def test_list_available_languages(self):
        manager = LSPManager("/tmp/workspace")
        with patch.object(manager, "_command_exists", return_value=True):
            available = manager.list_available_languages()
            assert "python" in available

    def test_list_available_languages_none(self):
        manager = LSPManager("/tmp/workspace")
        with patch.object(manager, "_command_exists", return_value=False):
            available = manager.list_available_languages()
            assert available == []


class TestFormatDiagnostics:
    """format_diagnostics 测试"""

    def test_empty(self):
        assert format_diagnostics({}) == "No diagnostics found."

    def test_with_diagnostics(self):
        diags = {
            "/test.py": [
                Diagnostic(
                    range=Range(start=Position(0, 0), end=Position(0, 5)),
                    message="syntax error",
                    severity=DiagnosticSeverity.Error,
                )
            ]
        }
        result = format_diagnostics(diags)
        assert "/test.py" in result
        assert "syntax error" in result

    def test_empty_diags_list(self):
        result = format_diagnostics({"/test.py": []})
        assert result == "No diagnostics found."


# =============================================================================
# DiagnosticsTool 测试
# =============================================================================


class TestDiagnosticsTool:
    """诊断工具测试"""

    def test_init(self):
        tool = DiagnosticsTool("/tmp/workspace")
        assert tool.name == "diagnostics"
        assert "LSP" in tool.description

    def test_parameters(self):
        tool = DiagnosticsTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "file_path" in params["properties"]

    @pytest.mark.asyncio
    async def test_execute_file_not_exists(self):
        tool = DiagnosticsTool("/tmp/workspace")
        result = await tool.execute(file_path="nonexistent.py")
        assert not result.success
        assert "不存在" in result.content

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        tool = DiagnosticsTool("/tmp/workspace")
        with patch.object(tool, "_get_lsp_manager", side_effect=RuntimeError("boom")):
            result = await tool.execute()
            assert not result.success
            assert "诊断失败" in result.content

    @pytest.mark.asyncio
    async def test_cleanup(self):
        tool = DiagnosticsTool("/tmp/workspace")
        mock_manager = MagicMock()
        mock_manager.stop_all = AsyncMock()
        tool._lsp_manager = mock_manager
        await tool.cleanup()
        mock_manager.stop_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_manager(self):
        tool = DiagnosticsTool("/tmp/workspace")
        # Should not raise
        await tool.cleanup()
