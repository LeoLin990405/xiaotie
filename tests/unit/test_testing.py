"""LLM 响应录制模块测试"""

import tempfile
from pathlib import Path

import pytest

from xiaotie.testing import (
    Cassette,
    CassetteRecord,
    LLMCassette,
    MockLLMClient,
    MockLLMResponse,
    RecordedRequest,
    RecordedResponse,
    get_mock_response,
    MOCK_RESPONSES,
)


class TestRecordedRequest:
    """RecordedRequest 测试"""

    def test_create_request(self):
        """测试创建请求"""
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert request.provider == "anthropic"
        assert request.model == "claude-sonnet-4"
        assert len(request.messages) == 1

    def test_fingerprint_deterministic(self):
        """测试指纹是确定性的"""
        request1 = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        request2 = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert request1.fingerprint == request2.fingerprint

    def test_fingerprint_different_for_different_requests(self):
        """测试不同请求有不同指纹"""
        request1 = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        request2 = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert request1.fingerprint != request2.fingerprint

    def test_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[],
        )
        assert request.timestamp != ""


class TestRecordedResponse:
    """RecordedResponse 测试"""

    def test_create_response(self):
        """测试创建响应"""
        response = RecordedResponse(
            content="Hello!",
            model="claude-sonnet-4",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.content == "Hello!"
        assert response.model == "claude-sonnet-4"
        assert response.usage["input_tokens"] == 10

    def test_response_with_thinking(self):
        """测试带思考的响应"""
        response = RecordedResponse(
            content="Answer",
            thinking="Let me think...",
        )
        assert response.thinking == "Let me think..."

    def test_response_with_tool_calls(self):
        """测试带工具调用的响应"""
        response = RecordedResponse(
            content="",
            tool_calls=[{"id": "1", "name": "read_file", "arguments": {}}],
        )
        assert len(response.tool_calls) == 1


class TestCassette:
    """Cassette 测试"""

    def test_create_cassette(self):
        """测试创建 cassette"""
        cassette = Cassette(name="test")
        assert cassette.name == "test"
        assert len(cassette.records) == 0

    def test_add_record(self):
        """测试添加记录"""
        cassette = Cassette(name="test")
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = RecordedResponse(content="Hi!")

        cassette.add_record(request, response)
        assert len(cassette.records) == 1

    def test_find_response(self):
        """测试查找响应"""
        cassette = Cassette(name="test")
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = RecordedResponse(content="Hi!")
        cassette.add_record(request, response)

        # 使用相同请求查找
        found = cassette.find_response(request)
        assert found is not None
        assert found.content == "Hi!"

    def test_find_response_not_found(self):
        """测试查找不存在的响应"""
        cassette = Cassette(name="test")
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        found = cassette.find_response(request)
        assert found is None

    def test_save_and_load(self):
        """测试保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"

            # 创建并保存
            cassette = Cassette(name="test")
            request = RecordedRequest(
                provider="anthropic",
                model="claude-sonnet-4",
                messages=[{"role": "user", "content": "Hello"}],
            )
            response = RecordedResponse(content="Hi!")
            cassette.add_record(request, response)
            cassette.save(path)

            # 加载
            loaded = Cassette.load(path)
            assert loaded.name == "test"
            assert len(loaded.records) == 1
            assert loaded.records[0].response.content == "Hi!"

    def test_load_nonexistent(self):
        """测试加载不存在的文件"""
        cassette = Cassette.load("/nonexistent/path.yaml")
        assert cassette.name == "path"
        assert len(cassette.records) == 0

    def test_to_dict_and_from_dict(self):
        """测试字典转换"""
        cassette = Cassette(name="test")
        request = RecordedRequest(
            provider="anthropic",
            model="claude-sonnet-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = RecordedResponse(content="Hi!", thinking="Thinking...")
        cassette.add_record(request, response)

        # 转换为字典再转回来
        data = cassette.to_dict()
        restored = Cassette.from_dict(data)

        assert restored.name == cassette.name
        assert len(restored.records) == 1
        assert restored.records[0].response.content == "Hi!"
        assert restored.records[0].response.thinking == "Thinking..."


class TestLLMCassette:
    """LLMCassette 上下文管理器测试"""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试上下文管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"

            async with LLMCassette(path) as cassette:
                assert cassette.cassette is not None

    @pytest.mark.asyncio
    async def test_record_and_get(self):
        """测试录制和获取"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.yaml"

            async with LLMCassette(path) as cassette:
                request = RecordedRequest(
                    provider="anthropic",
                    model="claude-sonnet-4",
                    messages=[{"role": "user", "content": "Hello"}],
                )
                response = RecordedResponse(content="Hi!")

                cassette.record(request, response)
                found = cassette.get_response(request)

                assert found is not None
                assert found.content == "Hi!"


class TestMockLLMClient:
    """MockLLMClient 测试"""

    @pytest.mark.asyncio
    async def test_default_response(self):
        """测试默认响应"""
        client = MockLLMClient()
        response = await client.generate([])

        assert response.content == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_custom_responses(self):
        """测试自定义响应序列"""
        responses = [
            RecordedResponse(content="First"),
            RecordedResponse(content="Second"),
        ]
        client = MockLLMClient(responses=responses)

        r1 = await client.generate([])
        r2 = await client.generate([])
        r3 = await client.generate([])  # 超出范围，使用默认

        assert r1.content == "First"
        assert r2.content == "Second"
        assert r3.content == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_call_history(self):
        """测试调用历史"""
        client = MockLLMClient()
        await client.generate([{"role": "user", "content": "Hello"}])
        await client.generate([{"role": "user", "content": "Hi"}])

        assert client.call_count == 2
        assert len(client.call_history) == 2

    @pytest.mark.asyncio
    async def test_custom_default_response(self):
        """测试自定义默认响应"""
        default = RecordedResponse(content="Custom default")
        client = MockLLMClient(default_response=default)

        response = await client.generate([])
        assert response.content == "Custom default"


class TestMockLLMResponse:
    """MockLLMResponse 测试"""

    def test_has_tool_calls_false(self):
        """测试无工具调用"""
        response = MockLLMResponse(content="Hello")
        assert response.has_tool_calls is False

    def test_has_tool_calls_true(self):
        """测试有工具调用"""
        response = MockLLMResponse(
            content="",
            tool_calls=[{"id": "1", "name": "test", "arguments": {}}],
        )
        assert response.has_tool_calls is True


class TestMockResponses:
    """预定义响应测试"""

    def test_hello_response(self):
        """测试 hello 响应"""
        response = get_mock_response("hello")
        assert "Hello" in response.content

    def test_code_response(self):
        """测试 code 响应"""
        response = get_mock_response("code")
        assert "```python" in response.content

    def test_tool_call_response(self):
        """测试 tool_call 响应"""
        response = get_mock_response("tool_call")
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1

    def test_thinking_response(self):
        """测试 thinking 响应"""
        response = get_mock_response("thinking")
        assert response.thinking is not None

    def test_unknown_key_returns_hello(self):
        """测试未知 key 返回 hello"""
        response = get_mock_response("unknown_key")
        assert response == MOCK_RESPONSES["hello"]
