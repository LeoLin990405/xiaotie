"""Agent 工作流集成测试

测试 Agent 完整对话流程、工具链调用、MCP/LSP 协议交互。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent import Agent, AgentConfig, SessionState
from xiaotie.schema import LLMResponse, Message, ToolCall, FunctionCall, ToolResult
from xiaotie.mcp.client import MCPClient, MCPClientError, MCPClientManager
from xiaotie.mcp.protocol import (
    MCPTool,
    MCPToolResult,
    TextContent,
    JSONRPCResponse,
)
from xiaotie.mcp.tools import MCPToolWrapper, create_mcp_tools
from xiaotie.lsp.client import LSPClient, LSPConfig
from xiaotie.lsp.manager import LSPManager
from xiaotie.lsp.protocol import (
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
)
from xiaotie.lsp.diagnostics import DiagnosticsTool


# =============================================================================
# Helper: 创建 mock LLM 客户端
# =============================================================================


def make_mock_llm(responses: list[LLMResponse]):
    """创建返回预设响应序列的 mock LLM 客户端"""
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=responses)
    llm.stream_chat = AsyncMock(side_effect=responses)
    return llm


def make_simple_response(content: str) -> LLMResponse:
    """创建简单文本响应"""
    return LLMResponse(content=content, finish_reason="stop")


def make_tool_call_response(tool_name: str, arguments: dict) -> LLMResponse:
    """创建包含工具调用的响应"""
    return LLMResponse(
        content="",
        tool_calls=[
            ToolCall(
                id=f"call_{tool_name}",
                type="function",
                function=FunctionCall(name=tool_name, arguments=arguments),
            )
        ],
        finish_reason="tool_calls",
    )


# =============================================================================
# SessionState 测试
# =============================================================================


class TestSessionState:
    """会话状态管理测试"""

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        state = SessionState()
        assert await state.acquire("s1")
        assert state.is_busy("s1")
        await state.release("s1")
        assert not state.is_busy("s1")

    @pytest.mark.asyncio
    async def test_acquire_twice_fails(self):
        state = SessionState()
        assert await state.acquire("s1")
        assert not await state.acquire("s1")
        await state.release("s1")

    @pytest.mark.asyncio
    async def test_release_nonexistent(self):
        state = SessionState()
        # Should not raise
        await state.release("nonexistent")

    @pytest.mark.asyncio
    async def test_wait_for_release(self):
        state = SessionState()
        assert await state.acquire("s1")

        async def release_later():
            await asyncio.sleep(0.05)
            await state.release("s1")

        asyncio.create_task(release_later())
        result = await state.wait_for_release("s1", timeout=2.0)
        assert result

    @pytest.mark.asyncio
    async def test_wait_for_release_timeout(self):
        state = SessionState()
        assert await state.acquire("s1")
        result = await state.wait_for_release("s1", timeout=0.05)
        assert not result
        await state.release("s1")

    @pytest.mark.asyncio
    async def test_wait_for_release_not_busy(self):
        state = SessionState()
        result = await state.wait_for_release("s1")
        assert result


# =============================================================================
# Agent 初始化和配置测试
# =============================================================================


class TestAgentConfig:
    """Agent 配置测试"""

    def test_default_config(self):
        config = AgentConfig()
        assert config.max_steps == 50
        assert config.token_limit == 100000
        assert config.parallel_tools is True
        assert config.enable_thinking is True
        assert config.stream is True

    def test_custom_config(self):
        config = AgentConfig(max_steps=10, token_limit=5000, parallel_tools=False)
        assert config.max_steps == 10
        assert config.token_limit == 5000
        assert not config.parallel_tools


class TestAgentInit:
    """Agent 初始化测试"""

    def test_basic_init(self):
        llm = MagicMock()
        agent = Agent(
            llm_client=llm,
            system_prompt="You are a test agent.",
            tools=[],
        )
        assert len(agent.messages) == 1
        assert agent.messages[0].role == "system"
        assert agent.tools == {}

    def test_init_with_tools(self):
        llm = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        agent = Agent(
            llm_client=llm,
            system_prompt="test",
            tools=[mock_tool],
        )
        assert "test_tool" in agent.tools

    def test_cancel_check(self):
        llm = MagicMock()
        agent = Agent(llm_client=llm, system_prompt="test", tools=[])
        assert not agent._check_cancelled()
        agent._cancelled = True
        assert agent._check_cancelled()

    def test_cancel_via_event(self):
        llm = MagicMock()
        agent = Agent(llm_client=llm, system_prompt="test", tools=[])
        agent.cancel_event = asyncio.Event()
        agent.cancel_event.set()
        assert agent._check_cancelled()


# =============================================================================
# MCP 工具链集成测试
# =============================================================================


class TestMCPToolChain:
    """MCP 工具链调用测试"""

    @pytest.mark.asyncio
    async def test_tool_wrapper_in_agent_context(self):
        """测试 MCP 工具包装器在 Agent 上下文中的使用"""
        mcp_tool = MCPTool(
            name="read_file",
            description="Read a file",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        mock_client = MagicMock(spec=MCPClient)
        mock_client.call_tool = AsyncMock(
            return_value=MCPToolResult(
                content=[TextContent(text="file content here")],
                isError=False,
            )
        )
        wrapper = MCPToolWrapper(mcp_tool=mcp_tool, client=mock_client, server_name="fs")

        # 模拟 Agent 使用工具
        result = await wrapper.execute(path="/tmp/test.txt")
        assert result.success
        assert result.content == "file content here"
        mock_client.call_tool.assert_called_once_with(
            name="read_file", arguments={"path": "/tmp/test.txt"}
        )

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_sequential(self):
        """测试顺序调用多个 MCP 工具"""
        tools = {}
        for name in ["read_file", "write_file", "list_dir"]:
            mcp_tool = MCPTool(name=name, description=f"Tool: {name}")
            mock_client = MagicMock(spec=MCPClient)
            mock_client.call_tool = AsyncMock(
                return_value=MCPToolResult(
                    content=[TextContent(text=f"result from {name}")],
                    isError=False,
                )
            )
            tools[name] = MCPToolWrapper(mcp_tool=mcp_tool, client=mock_client, server_name="fs")

        results = []
        for name, tool in tools.items():
            result = await tool.execute()
            results.append(result)

        assert all(r.success for r in results)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_tool_error_propagation(self):
        """测试工具错误传播"""
        mcp_tool = MCPTool(name="dangerous_tool")
        mock_client = MagicMock(spec=MCPClient)
        mock_client.call_tool = AsyncMock(
            side_effect=MCPClientError("permission denied")
        )
        wrapper = MCPToolWrapper(mcp_tool=mcp_tool, client=mock_client, server_name="fs")

        result = await wrapper.execute()
        assert not result.success
        assert "permission denied" in result.error


class TestMCPClientManagerIntegration:
    """MCPClientManager 集成测试"""

    @pytest.mark.asyncio
    async def test_manager_call_tool(self):
        """测试通过 Manager 调用工具"""
        manager = MCPClientManager()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.call_tool = AsyncMock(
            return_value=MCPToolResult(
                content=[TextContent(text="ok")],
                isError=False,
            )
        )
        mock_client.disconnect = AsyncMock()
        manager._clients["test_server"] = mock_client

        result = await manager.call_tool("test_server", "test_tool", {"arg": "value"})
        assert not result.isError
        mock_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})

        await manager.disconnect_all()

    @pytest.mark.asyncio
    async def test_manager_replace_server(self):
        """测试替换已存在的服务器"""
        manager = MCPClientManager()
        old_client = MagicMock(spec=MCPClient)
        old_client.disconnect = AsyncMock()
        manager._clients["server1"] = old_client

        new_client = MagicMock(spec=MCPClient)
        new_client.connect = AsyncMock()
        new_client.initialize = AsyncMock()
        new_client.list_tools = AsyncMock(return_value=[])
        new_client.disconnect = AsyncMock()

        with patch("xiaotie.mcp.client.MCPClient", return_value=new_client):
            await manager.add_server("server1", command="echo")

        old_client.disconnect.assert_called_once()
        assert manager._clients["server1"] is new_client

        await manager.disconnect_all()


# =============================================================================
# LSP 协议交互测试
# =============================================================================


class TestLSPProtocolInteraction:
    """LSP 协议交互测试"""

    def test_diagnostics_flow(self):
        """测试诊断信息流: 发布 -> 存储 -> 查询"""
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")

        # 模拟服务器发布诊断
        params = {
            "uri": "file:///tmp/workspace/test.py",
            "diagnostics": [
                {
                    "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 10}},
                    "message": "undefined name 'foo'",
                    "severity": 1,
                    "source": "pyflakes",
                    "code": "F821",
                },
                {
                    "range": {"start": {"line": 10, "character": 0}, "end": {"line": 10, "character": 5}},
                    "message": "unused import",
                    "severity": 2,
                    "source": "pyflakes",
                    "code": "F401",
                },
            ],
        }
        client._handle_diagnostics(params)

        # 查询诊断
        diags = client.get_diagnostics("/tmp/workspace/test.py")
        assert "/tmp/workspace/test.py" in diags
        file_diags = diags["/tmp/workspace/test.py"]
        assert len(file_diags) == 2
        assert file_diags[0].severity == DiagnosticSeverity.Error
        assert file_diags[1].severity == DiagnosticSeverity.Warning

    @pytest.mark.asyncio
    async def test_message_routing(self):
        """测试消息路由: 响应/错误/通知/服务器请求"""
        config = LSPConfig(command="pylsp")
        client = LSPClient(config, "/tmp/workspace")
        loop = asyncio.get_event_loop()

        # 1. 正常响应
        future1 = loop.create_future()
        client._pending_requests[1] = future1
        await client._handle_message({"id": 1, "result": {"ok": True}})
        assert future1.result() == {"ok": True}

        # 2. 错误响应
        future2 = loop.create_future()
        client._pending_requests[2] = future2
        await client._handle_message({"id": 2, "error": {"code": -1, "message": "fail"}})
        with pytest.raises(RuntimeError):
            future2.result()

        # 3. 通知
        await client._handle_message({
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file:///test.py", "diagnostics": []},
        })
        assert "file:///test.py" in client._diagnostics

    @pytest.mark.asyncio
    async def test_lsp_manager_get_client_disabled(self):
        """测试获取禁用语言的客户端"""
        configs = {"python": LSPConfig(command="pylsp", enabled=False)}
        manager = LSPManager("/tmp/workspace", configs=configs)
        client = await manager.get_client("python")
        assert client is None

    @pytest.mark.asyncio
    async def test_lsp_manager_get_client_command_missing(self):
        """测试命令不存在时的处理"""
        manager = LSPManager("/tmp/workspace")
        with patch.object(manager, "_command_exists", return_value=False):
            client = await manager.get_client("python")
            assert client is None


# =============================================================================
# MCP + LSP 联合测试
# =============================================================================


class TestMCPLSPCombined:
    """MCP 和 LSP 联合使用测试"""

    @pytest.mark.asyncio
    async def test_mcp_tool_with_lsp_diagnostics(self):
        """测试 MCP 工具执行后获取 LSP 诊断"""
        # 1. MCP 工具写入文件
        write_tool = MCPTool(name="write_file", description="Write a file")
        mock_mcp_client = MagicMock(spec=MCPClient)
        mock_mcp_client.call_tool = AsyncMock(
            return_value=MCPToolResult(
                content=[TextContent(text="File written successfully")],
                isError=False,
            )
        )
        wrapper = MCPToolWrapper(mcp_tool=write_tool, client=mock_mcp_client, server_name="fs")
        write_result = await wrapper.execute(path="/tmp/test.py", content="x = 1\n")
        assert write_result.success

        # 2. LSP 诊断检查
        config = LSPConfig(command="pylsp")
        lsp_client = LSPClient(config, "/tmp/workspace")
        lsp_client._handle_diagnostics({
            "uri": "file:///tmp/test.py",
            "diagnostics": [],
        })
        diags = lsp_client.get_diagnostics("/tmp/test.py")
        # 无诊断错误 = 文件正常
        assert diags.get("/tmp/test.py", []) == []

    @pytest.mark.asyncio
    async def test_diagnostics_tool_integration(self):
        """测试 DiagnosticsTool 作为 Agent 工具的集成"""
        tool = DiagnosticsTool("/tmp/workspace")
        assert tool.name == "diagnostics"

        # 模拟 LSP manager 返回诊断
        mock_manager = MagicMock()
        mock_manager.get_diagnostics = AsyncMock(return_value={})
        mock_manager.list_available_languages = MagicMock(return_value=["python"])
        tool._lsp_manager = mock_manager

        result = await tool.execute()
        assert result.success
        assert "LSP" in result.content or "没有" in result.content
