"""集成测试"""

import pytest


class TestAgentIntegration:
    """Agent 集成测试"""

    @pytest.fixture
    def agent_config(self, workspace_dir):
        """创建 Agent 配置"""
        return {
            "workspace_dir": workspace_dir,
            "model": "test-model",
            "provider": "openai",
        }

    def test_agent_import(self):
        """测试 Agent 导入"""
        from xiaotie.agent import Agent
        assert Agent is not None

    def test_tools_import(self):
        """测试工具导入"""
        from xiaotie.tools import BashTool, ReadTool, WriteTool
        assert ReadTool is not None
        assert WriteTool is not None
        assert BashTool is not None

    def test_schema_import(self):
        """测试 Schema 导入"""
        from xiaotie.schema import LLMResponse, Message, ToolCall, ToolResult
        assert Message is not None
        assert ToolCall is not None
        assert ToolResult is not None
        assert LLMResponse is not None


class TestMCPIntegration:
    """MCP 集成测试"""

    def test_mcp_import(self):
        """测试 MCP 模块导入"""
        from xiaotie.mcp import MCPClient, MCPTool
        assert MCPClient is not None
        assert MCPTool is not None

    def test_mcp_protocol_import(self):
        """测试 MCP 协议导入"""
        from xiaotie.mcp.protocol import (
            JSONRPCNotification,
            JSONRPCRequest,
            JSONRPCResponse,
        )
        assert JSONRPCRequest is not None
        assert JSONRPCResponse is not None
        assert JSONRPCNotification is not None


class TestLSPIntegration:
    """LSP 集成测试"""

    def test_lsp_import(self):
        """测试 LSP 模块导入"""
        from xiaotie.lsp import DiagnosticsTool, LSPClient, LSPManager
        assert LSPClient is not None
        assert LSPManager is not None
        assert DiagnosticsTool is not None

    def test_lsp_protocol_import(self):
        """测试 LSP 协议导入"""
        from xiaotie.lsp.protocol import (
            Diagnostic,
            DiagnosticSeverity,
            Location,
            Position,
            Range,
        )
        assert Position is not None
        assert Range is not None
        assert Location is not None
        assert Diagnostic is not None
        assert DiagnosticSeverity is not None


class TestCustomCommandsIntegration:
    """自定义命令集成测试"""

    def test_custom_commands_import(self):
        """测试自定义命令导入"""
        from xiaotie.custom_commands import CustomCommandExecutor, CustomCommandManager
        assert CustomCommandManager is not None
        assert CustomCommandExecutor is not None

    def test_custom_command_manager_init(self, workspace_dir):
        """测试命令管理器初始化"""
        from xiaotie.custom_commands import CustomCommandManager
        manager = CustomCommandManager(workspace_dir=workspace_dir)
        assert manager is not None
        # workspace_dir 是 Path 对象
        assert str(manager.workspace_dir) == workspace_dir
