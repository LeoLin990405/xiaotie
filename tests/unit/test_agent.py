"""Agent 核心模块测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent import Agent, AgentConfig, SessionState
from xiaotie.schema import LLMResponse, Message, TokenUsage, ToolResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=LLMResponse(content="你好！", tool_calls=None)
    )
    llm.generate_stream = AsyncMock(
        return_value=LLMResponse(content="你好！", tool_calls=None)
    )
    return llm


@pytest.fixture
def dummy_tool():
    """创建一个简单的 mock Tool"""
    tool = MagicMock()
    tool.name = "dummy"
    tool.description = "dummy tool"
    tool.parameters = {"type": "object", "properties": {}}
    tool.to_schema.return_value = {
        "type": "function",
        "function": {
            "name": "dummy",
            "description": "dummy tool",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    tool.execute = AsyncMock(
        return_value=ToolResult(success=True, content="ok")
    )
    return tool


@pytest.fixture
def agent(mock_llm, dummy_tool):
    return Agent(
        llm_client=mock_llm,
        system_prompt="你是小铁",
        tools=[dummy_tool],
        max_steps=5,
        stream=False,
        quiet=True,
    )


# ---------------------------------------------------------------------------
# 简单对话
# ---------------------------------------------------------------------------

class TestAgentConversation:
    async def test_simple_reply(self, agent, mock_llm):
        """Agent 应返回 LLM 的文本回复"""
        result = await agent.run("你好")
        assert result == "你好！"
        mock_llm.generate.assert_awaited()

    async def test_user_message_appended(self, agent):
        """用户输入应被追加到消息历史"""
        await agent.run("测试消息")
        roles = [m.role for m in agent.messages]
        assert "user" in roles

    async def test_assistant_message_appended(self, agent):
        """LLM 回复应被追加到消息历史"""
        await agent.run("测试")
        roles = [m.role for m in agent.messages]
        assert "assistant" in roles

    async def test_stats_after_run(self, agent):
        """运行后统计信息应正确"""
        await agent.run("hi")
        stats = agent.get_stats()
        assert stats["message_count"] >= 3  # system + user + assistant


# ---------------------------------------------------------------------------
# 最大步数限制
# ---------------------------------------------------------------------------

class TestAgentMaxSteps:
    async def test_max_steps_reached(self, mock_llm, dummy_tool):
        """达到最大步数时应返回警告"""
        # 让 LLM 每次都返回工具调用，永不停止
        from xiaotie.schema import ToolCall, FunctionCall

        tool_response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc_1",
                    function=FunctionCall(name="dummy", arguments={}),
                )
            ],
        )
        mock_llm.generate = AsyncMock(return_value=tool_response)

        agent = Agent(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            max_steps=3,
            stream=False,
            quiet=True,
        )
        result = await agent.run("loop forever")
        assert "最大步数" in result


# ---------------------------------------------------------------------------
# 取消
# ---------------------------------------------------------------------------

class TestAgentCancel:
    async def test_cancel_via_event(self, mock_llm, dummy_tool):
        """通过 cancel_event 取消应返回取消消息"""
        agent = Agent(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            max_steps=10,
            stream=False,
            quiet=True,
        )
        cancel = asyncio.Event()
        agent.cancel_event = cancel
        cancel.set()  # 立即取消

        result = await agent.run("do something")
        assert "取消" in result

    async def test_cancel_flag_during_loop(self, mock_llm, dummy_tool):
        """_cancelled 在循环中被设置应取消执行"""
        from xiaotie.schema import ToolCall, FunctionCall

        call_count = 0

        async def generate_with_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                # 第二次调用时设置取消
                agent._cancelled = True
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id=f"tc_{call_count}",
                        function=FunctionCall(name="dummy", arguments={}),
                    )
                ],
            )

        mock_llm.generate = AsyncMock(side_effect=generate_with_cancel)
        agent = Agent(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            max_steps=10,
            stream=False,
            quiet=True,
        )
        result = await agent.run("test")
        assert "取消" in result


# ---------------------------------------------------------------------------
# 重置
# ---------------------------------------------------------------------------

class TestAgentReset:
    async def test_reset_clears_history(self, agent):
        """reset 应清除消息历史（保留 system）"""
        await agent.run("hello")
        agent.reset()
        assert len(agent.messages) == 1
        assert agent.messages[0].role == "system"

    async def test_reset_clears_tokens(self, agent):
        """reset 应清零 token 统计"""
        agent.api_total_tokens = 100
        agent.reset()
        assert agent.api_total_tokens == 0


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

class TestSessionState:
    async def test_acquire_and_release(self):
        state = SessionState()
        assert await state.acquire("s1")
        assert state.is_busy("s1")
        await state.release("s1")
        assert not state.is_busy("s1")

    async def test_double_acquire_fails(self):
        state = SessionState()
        assert await state.acquire("s1")
        assert not await state.acquire("s1")
        await state.release("s1")
