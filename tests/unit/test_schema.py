"""Schema 单元测试"""

import pytest
from xiaotie.schema import Message, ToolCall, ToolResult, LLMResponse, FunctionCall, TokenUsage


class TestMessage:
    """Message 类测试"""

    def test_create_user_message(self):
        """测试创建用户消息"""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None

    def test_create_assistant_message(self):
        """测试创建助手消息"""
        msg = Message(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_create_tool_message(self):
        """测试创建工具消息"""
        msg = Message(role="tool", content="Result", tool_call_id="call_123")
        assert msg.role == "tool"
        assert msg.content == "Result"
        assert msg.tool_call_id == "call_123"

    def test_message_model_dump(self):
        """测试消息转字典"""
        msg = Message(role="user", content="Test")
        d = msg.model_dump()
        assert d["role"] == "user"
        assert d["content"] == "Test"


class TestToolCall:
    """ToolCall 类测试"""

    def test_create_tool_call(self):
        """测试创建工具调用"""
        tc = ToolCall(
            id="call_123",
            function=FunctionCall(
                name="read_file",
                arguments={"path": "/tmp/test.txt"},
            ),
        )
        assert tc.id == "call_123"
        assert tc.function.name == "read_file"
        assert tc.function.arguments["path"] == "/tmp/test.txt"

    def test_tool_call_model_dump(self):
        """测试工具调用转字典"""
        tc = ToolCall(
            id="call_456",
            function=FunctionCall(
                name="bash",
                arguments={"command": "ls"},
            ),
        )
        d = tc.model_dump()
        assert d["id"] == "call_456"
        assert d["function"]["name"] == "bash"


class TestToolResult:
    """ToolResult 类测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolResult(success=True, content="Done")
        assert result.success is True
        assert result.content == "Done"

    def test_failure_result(self):
        """测试失败结果"""
        result = ToolResult(success=False, content="", error="Error occurred")
        assert result.success is False
        assert "Error" in result.error

    def test_result_with_error(self):
        """测试带错误的结果"""
        result = ToolResult(
            success=False,
            content="",
            error="Something went wrong",
        )
        assert result.error == "Something went wrong"


class TestLLMResponse:
    """LLMResponse 类测试"""

    def test_simple_response(self):
        """测试简单响应"""
        resp = LLMResponse(content="Hello")
        assert resp.content == "Hello"
        assert resp.tool_calls is None

    def test_response_with_tool_calls(self):
        """测试带工具调用的响应"""
        tc = ToolCall(
            id="call_1",
            function=FunctionCall(name="bash", arguments={"command": "pwd"}),
        )
        resp = LLMResponse(content="", tool_calls=[tc])
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].function.name == "bash"

    def test_response_with_thinking(self):
        """测试带思考的响应"""
        resp = LLMResponse(
            content="Answer",
            thinking="Let me think about this...",
        )
        assert resp.thinking is not None
        assert "think" in resp.thinking.lower()

    def test_response_with_usage(self):
        """测试带使用统计的响应"""
        resp = LLMResponse(
            content="Test",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        assert resp.usage.prompt_tokens == 100
        assert resp.usage.completion_tokens == 50
