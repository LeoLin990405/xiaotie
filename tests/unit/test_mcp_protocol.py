"""MCP 协议测试

测试 MCP 协议消息序列化/反序列化、客户端连接/断开、工具发现和调用、错误处理。
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.mcp.protocol import (
    LATEST_PROTOCOL_VERSION,
    ClientCapabilities,
    ContentType,
    ImageContent,
    Implementation,
    InitializeParams,
    InitializeResult,
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    ListToolsResult,
    MCPTool,
    MCPToolCall,
    MCPToolResult,
    ResourceContent,
    ServerCapabilities,
    TextContent,
    ToolsCapability,
)
from xiaotie.mcp.client import MCPClient, MCPClientError, MCPClientManager
from xiaotie.mcp.transport import StdioTransport, TransportError
from xiaotie.mcp.tools import MCPToolWrapper, create_mcp_tools


# =============================================================================
# 协议消息序列化/反序列化
# =============================================================================


class TestJSONRPCRequest:
    """JSON-RPC 请求序列化测试"""

    def test_basic_request(self):
        req = JSONRPCRequest(id=1, method="initialize")
        data = req.model_dump(exclude_none=True)
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["method"] == "initialize"
        assert "params" not in data

    def test_request_with_params(self):
        req = JSONRPCRequest(id=2, method="tools/call", params={"name": "read_file"})
        data = req.model_dump(exclude_none=True)
        assert data["params"] == {"name": "read_file"}

    def test_request_with_string_id(self):
        req = JSONRPCRequest(id="abc-123", method="test")
        assert req.id == "abc-123"

    def test_request_json_roundtrip(self):
        req = JSONRPCRequest(id=1, method="test", params={"key": "value"})
        json_str = req.model_dump_json(exclude_none=True)
        parsed = json.loads(json_str)
        restored = JSONRPCRequest(**parsed)
        assert restored.id == req.id
        assert restored.method == req.method
        assert restored.params == req.params


class TestJSONRPCNotification:
    """JSON-RPC 通知序列化测试"""

    def test_notification_no_id(self):
        notif = JSONRPCNotification(method="notifications/initialized")
        data = notif.model_dump(exclude_none=True)
        assert "id" not in data
        assert data["method"] == "notifications/initialized"

    def test_notification_with_params(self):
        notif = JSONRPCNotification(method="test", params={"foo": "bar"})
        data = notif.model_dump(exclude_none=True)
        assert data["params"] == {"foo": "bar"}


class TestJSONRPCResponse:
    """JSON-RPC 响应序列化测试"""

    def test_success_response(self):
        resp = JSONRPCResponse(id=1, result={"status": "ok"})
        assert resp.error is None
        assert resp.result == {"status": "ok"}

    def test_error_response(self):
        error = JSONRPCError(code=-32600, message="Invalid Request")
        resp = JSONRPCResponse(id=1, error=error)
        assert resp.result is None
        assert resp.error.code == -32600
        assert resp.error.message == "Invalid Request"

    def test_error_with_data(self):
        error = JSONRPCError(code=-32000, message="Server error", data={"detail": "info"})
        assert error.data == {"detail": "info"}

    def test_response_json_roundtrip(self):
        resp = JSONRPCResponse(id=1, result={"tools": []})
        json_str = resp.model_dump_json(exclude_none=True)
        parsed = json.loads(json_str)
        restored = JSONRPCResponse(**parsed)
        assert restored.id == resp.id
        assert restored.result == resp.result


class TestMCPProtocolTypes:
    """MCP 协议类型测试"""

    def test_implementation(self):
        impl = Implementation(name="xiaotie", version="0.5.0")
        assert impl.name == "xiaotie"
        assert impl.version == "0.5.0"

    def test_initialize_params(self):
        params = InitializeParams(
            clientInfo=Implementation(name="test", version="1.0"),
        )
        assert params.protocolVersion == LATEST_PROTOCOL_VERSION
        assert params.clientInfo.name == "test"

    def test_initialize_result(self):
        result = InitializeResult(
            protocolVersion=LATEST_PROTOCOL_VERSION,
            capabilities=ServerCapabilities(tools=ToolsCapability(listChanged=True)),
            serverInfo=Implementation(name="test-server", version="1.0"),
            instructions="Use this server for file operations.",
        )
        assert result.serverInfo.name == "test-server"
        assert result.capabilities.tools.listChanged is True
        assert result.instructions is not None

    def test_mcp_tool(self):
        tool = MCPTool(
            name="read_file",
            description="Read a file",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        assert tool.name == "read_file"
        assert "path" in tool.inputSchema["properties"]

    def test_mcp_tool_defaults(self):
        tool = MCPTool(name="simple")
        assert tool.description is None
        assert tool.inputSchema == {"type": "object", "properties": {}}

    def test_list_tools_result(self):
        tools = [MCPTool(name="a"), MCPTool(name="b")]
        result = ListToolsResult(tools=tools)
        assert len(result.tools) == 2
        assert result.nextCursor is None

    def test_mcp_tool_call(self):
        call = MCPToolCall(name="read_file", arguments={"path": "/tmp/test.txt"})
        assert call.name == "read_file"
        assert call.arguments["path"] == "/tmp/test.txt"

    def test_text_content(self):
        content = TextContent(text="hello world")
        assert content.type == "text"
        assert content.text == "hello world"

    def test_image_content(self):
        content = ImageContent(data="base64data", mimeType="image/png")
        assert content.type == "image"

    def test_resource_content(self):
        content = ResourceContent(resource={"uri": "file:///test"})
        assert content.type == "resource"

    def test_mcp_tool_result_success(self):
        result = MCPToolResult(
            content=[TextContent(text="file content")],
            isError=False,
        )
        assert not result.isError
        assert len(result.content) == 1

    def test_mcp_tool_result_error(self):
        result = MCPToolResult(
            content=[TextContent(text="file not found")],
            isError=True,
        )
        assert result.isError


# =============================================================================
# 客户端连接/断开
# =============================================================================


class TestMCPClientConnection:
    """MCP 客户端连接测试"""

    def test_client_init(self):
        client = MCPClient(command="echo", args=["hello"])
        assert not client.is_connected
        assert not client.is_initialized
        assert client.server_info is None
        assert client.tools == {}

    def test_client_request_id_increment(self):
        client = MCPClient(command="echo")
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        client = MCPClient(command="echo")
        with patch.object(client._transport, "connect", new_callable=AsyncMock) as mock_conn:
            await client.connect()
            mock_conn.assert_called_once()

        with patch.object(client._transport, "disconnect", new_callable=AsyncMock) as mock_disc:
            await client.disconnect()
            mock_disc.assert_called_once()
            assert not client.is_initialized

    @pytest.mark.asyncio
    async def test_initialize_not_connected(self):
        client = MCPClient(command="echo")
        with pytest.raises(MCPClientError, match="未连接"):
            await client.initialize()

    @pytest.mark.asyncio
    async def test_list_tools_not_initialized(self):
        client = MCPClient(command="echo")
        with pytest.raises(MCPClientError, match="未初始化"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self):
        client = MCPClient(command="echo")
        with pytest.raises(MCPClientError, match="未初始化"):
            await client.call_tool("test")

    @pytest.mark.asyncio
    async def test_send_request_response_id_mismatch(self):
        client = MCPClient(command="echo")
        client._transport = MagicMock()
        client._transport.is_connected = True
        client._transport.send = AsyncMock()
        client._transport.receive = AsyncMock(
            return_value=JSONRPCResponse(id=999, result={})
        )
        with pytest.raises(MCPClientError, match="响应 ID 不匹配"):
            await client._send_request("test")

    @pytest.mark.asyncio
    async def test_send_request_server_error(self):
        client = MCPClient(command="echo")
        client._transport = MagicMock()
        client._transport.is_connected = True
        client._transport.send = AsyncMock()
        error = JSONRPCError(code=-32000, message="Server error")
        client._transport.receive = AsyncMock(
            return_value=JSONRPCResponse(id=1, error=error)
        )
        with pytest.raises(MCPClientError, match="服务器错误"):
            await client._send_request("test")


# =============================================================================
# 工具发现和调用
# =============================================================================


class TestMCPToolDiscovery:
    """MCP 工具发现测试"""

    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        client = MCPClient(command="echo")
        client._initialized = True
        tools_data = {
            "tools": [
                {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object", "properties": {}}},
                {"name": "write_file", "description": "Write a file", "inputSchema": {"type": "object", "properties": {}}},
            ]
        }
        with patch.object(client, "_send_request", new_callable=AsyncMock, return_value=tools_data):
            tools = await client.list_tools()
            assert len(tools) == 2
            assert "read_file" in client.tools
            assert "write_file" in client.tools

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        client = MCPClient(command="echo")
        client._initialized = True
        result_data = {
            "content": [{"type": "text", "text": "file content here"}],
            "isError": False,
        }
        with patch.object(client, "_send_request", new_callable=AsyncMock, return_value=result_data):
            result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})
            assert not result.isError
            assert len(result.content) == 1


class TestMCPToolWrapper:
    """MCP 工具包装器测试"""

    def _make_wrapper(self):
        mcp_tool = MCPTool(
            name="read_file",
            description="Read a file",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        client = MagicMock(spec=MCPClient)
        return MCPToolWrapper(mcp_tool=mcp_tool, client=client, server_name="fs")

    def test_wrapper_name(self):
        wrapper = self._make_wrapper()
        assert wrapper.name == "mcp_fs_read_file"

    def test_wrapper_description(self):
        wrapper = self._make_wrapper()
        assert "[MCP:fs]" in wrapper.description
        assert "Read a file" in wrapper.description

    def test_wrapper_parameters(self):
        wrapper = self._make_wrapper()
        assert "path" in wrapper.parameters["properties"]

    @pytest.mark.asyncio
    async def test_wrapper_execute_success(self):
        wrapper = self._make_wrapper()
        mcp_result = MCPToolResult(
            content=[TextContent(text="hello")],
            isError=False,
        )
        wrapper._client.call_tool = AsyncMock(return_value=mcp_result)
        result = await wrapper.execute(path="/tmp/test.txt")
        assert result.success
        assert result.content == "hello"

    @pytest.mark.asyncio
    async def test_wrapper_execute_error_result(self):
        wrapper = self._make_wrapper()
        mcp_result = MCPToolResult(
            content=[TextContent(text="not found")],
            isError=True,
        )
        wrapper._client.call_tool = AsyncMock(return_value=mcp_result)
        result = await wrapper.execute(path="/nonexistent")
        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_wrapper_execute_client_error(self):
        wrapper = self._make_wrapper()
        wrapper._client.call_tool = AsyncMock(side_effect=MCPClientError("connection lost"))
        result = await wrapper.execute(path="/tmp/test.txt")
        assert not result.success
        assert "connection lost" in result.error

    @pytest.mark.asyncio
    async def test_wrapper_execute_unexpected_error(self):
        wrapper = self._make_wrapper()
        wrapper._client.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
        result = await wrapper.execute(path="/tmp/test.txt")
        assert not result.success
        assert "boom" in result.error


class TestCreateMCPTools:
    """create_mcp_tools 测试"""

    def test_create_tools_from_client(self):
        client = MagicMock(spec=MCPClient)
        client.tools = {
            "read_file": MCPTool(name="read_file", description="Read"),
            "write_file": MCPTool(name="write_file", description="Write"),
        }
        tools = create_mcp_tools(client, server_name="fs")
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "mcp_fs_read_file" in names
        assert "mcp_fs_write_file" in names


# =============================================================================
# 传输层测试
# =============================================================================


class TestStdioTransport:
    """Stdio 传输层测试"""

    def test_transport_init(self):
        transport = StdioTransport(command="echo", args=["hello"])
        assert transport.command == "echo"
        assert transport.args == ["hello"]
        assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_send_not_connected(self):
        transport = StdioTransport(command="echo")
        req = JSONRPCRequest(id=1, method="test")
        with pytest.raises(TransportError, match="未连接"):
            await transport.send(req)

    @pytest.mark.asyncio
    async def test_receive_not_connected(self):
        transport = StdioTransport(command="echo")
        with pytest.raises(TransportError, match="未连接"):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_connect_command_not_found(self):
        transport = StdioTransport(command="nonexistent_command_xyz_12345")
        with pytest.raises(TransportError, match="找不到命令"):
            await transport.connect()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        transport = StdioTransport(command="echo")
        # Should not raise
        await transport.disconnect()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        transport = StdioTransport(command="echo")
        with patch.object(transport, "connect", new_callable=AsyncMock) as mock_conn, \
             patch.object(transport, "disconnect", new_callable=AsyncMock) as mock_disc:
            async with transport as t:
                assert t is transport
                mock_conn.assert_called_once()
            mock_disc.assert_called_once()


# =============================================================================
# MCPClientManager 测试
# =============================================================================


class TestMCPClientManager:
    """MCP 客户端管理器测试"""

    def test_manager_init(self):
        manager = MCPClientManager()
        assert manager.clients == {}

    def test_get_all_tools_empty(self):
        manager = MCPClientManager()
        assert manager.get_all_tools() == {}

    @pytest.mark.asyncio
    async def test_remove_nonexistent_server(self):
        manager = MCPClientManager()
        # Should not raise
        await manager.remove_server("nonexistent")

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self):
        manager = MCPClientManager()
        with pytest.raises(MCPClientError, match="不存在"):
            await manager.call_tool("nonexistent", "tool_name")

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        manager = MCPClientManager()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.disconnect = AsyncMock()
        manager._clients["test"] = mock_client
        await manager.disconnect_all()
        assert len(manager.clients) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        manager = MCPClientManager()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.disconnect = AsyncMock()
        manager._clients["test"] = mock_client
        async with manager:
            pass
        assert len(manager.clients) == 0

    def test_get_all_tools_with_clients(self):
        manager = MCPClientManager()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.tools = {
            "read": MCPTool(name="read"),
            "write": MCPTool(name="write"),
        }
        manager._clients["fs"] = mock_client
        all_tools = manager.get_all_tools()
        assert "fs:read" in all_tools
        assert "fs:write" in all_tools
