"""Agent 核心模块测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent import Agent, AgentConfig, SessionState
from xiaotie.schema import FunctionCall, LLMResponse, Message, TokenUsage, ToolCall, ToolResult


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
        assert "telemetry" in stats
        assert stats["telemetry"]["runs_total"] >= 1


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


class TestAgentSecurity:
    async def test_sensitive_tool_output_blocked(self, mock_llm):
        tool = MagicMock()
        tool.name = "dummy"
        tool.description = "dummy tool"
        tool.parameters = {"type": "object", "properties": {}}
        tool.to_schema.return_value = {
            "type": "function",
            "function": {"name": "dummy", "description": "dummy", "parameters": {}},
        }
        tool.execute = AsyncMock(return_value=ToolResult(
            success=True, content="api_key=sk-abc123def456ghi789jkl012mno345"
        ))

        agent = Agent(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[tool],
            max_steps=3,
            stream=False,
            quiet=True,
        )
        tc = ToolCall(id="tc1", function=FunctionCall(name="dummy", arguments={}))
        _, _, result = await agent._execute_single_tool(tc)
        assert "REDACTED" in result
        assert "敏感内容已脱敏" in result

    async def test_sensitive_filter_aws_key(self, mock_llm):
        """AWS Access Key ID should be redacted"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        output, blocked, reason = agent._filter_sensitive_output("key is AKIAIOSFODNN7EXAMPLE")
        assert blocked is True
        assert "REDACTED" in output
        assert "AWS" in reason

    async def test_sensitive_filter_private_key(self, mock_llm):
        """PEM private keys should be redacted"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        output, blocked, reason = agent._filter_sensitive_output(pem)
        assert blocked is True
        assert "REDACTED" in output

    async def test_sensitive_filter_github_token(self, mock_llm):
        """GitHub tokens (ghp_) should be redacted"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        output, blocked, reason = agent._filter_sensitive_output(
            "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh1234"
        )
        assert blocked is True
        assert "REDACTED" in output
        assert "GitHub" in reason

    async def test_sensitive_filter_no_false_positive_on_word_token(self, mock_llm):
        """The word 'token' in normal code should NOT trigger a block"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        output, blocked, _ = agent._filter_sensitive_output(
            "def get_token(self):\n    return self.token"
        )
        assert blocked is False
        assert output == "def get_token(self):\n    return self.token"

    async def test_sensitive_filter_no_false_positive_on_short_value(self, mock_llm):
        """Short values like password=test should NOT trigger"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        output, blocked, _ = agent._filter_sensitive_output("password = test")
        assert blocked is False

    async def test_sensitive_filter_empty_and_none(self, mock_llm):
        """Empty/None inputs should pass through"""
        agent = Agent(llm_client=mock_llm, system_prompt="t", tools=[], quiet=True, stream=False)
        output, blocked, _ = agent._filter_sensitive_output("")
        assert blocked is False
        output2, blocked2, _ = agent._filter_sensitive_output(None)
        assert blocked2 is False

    async def test_high_risk_tool_denied_in_non_interactive(self, mock_llm):
        tool = MagicMock()
        tool.name = "bash"
        tool.description = "bash tool"
        tool.parameters = {"type": "object", "properties": {}}
        tool.to_schema.return_value = {
            "type": "function",
            "function": {"name": "bash", "description": "bash", "parameters": {}},
        }
        tool.execute = AsyncMock(return_value=ToolResult(success=True, content="ok"))

        agent = Agent(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[tool],
            max_steps=3,
            stream=False,
            quiet=True,
        )
        agent.permission_manager.interactive = False
        tc = ToolCall(id="tc1", function=FunctionCall(name="bash", arguments={"command": "python script.py"}))
        _, _, result = await agent._execute_single_tool(tc)
        assert "权限拒绝" in result


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


# ---------------------------------------------------------------------------
# Tool Execution and Utility
# ---------------------------------------------------------------------------

class TestToolExecution:
    @pytest.mark.asyncio
    async def test_execute_tools_sequential(self, agent, dummy_tool):
        from xiaotie.schema import ToolCall, FunctionCall
        tc1 = ToolCall(id="tc1", function=FunctionCall(name="dummy", arguments={"arg": 1}))
        tc2 = ToolCall(id="tc2", function=FunctionCall(name="dummy", arguments={"arg": 2}))
        
        results = await agent._execute_tools_sequential([tc1, tc2])
        assert len(results) == 2
        assert results[0][0] == "tc1"
        assert results[1][0] == "tc2"
        assert dummy_tool.execute.call_count == 2
        
    @pytest.mark.asyncio
    async def test_execute_tools_parallel(self, agent, dummy_tool):
        from xiaotie.schema import ToolCall, FunctionCall
        tc1 = ToolCall(id="tc3", function=FunctionCall(name="dummy", arguments={"arg": 1}))
        tc2 = ToolCall(id="tc4", function=FunctionCall(name="dummy", arguments={"arg": 2}))
        
        results = await agent._execute_tools_parallel([tc1, tc2])
        assert len(results) == 2
        assert dummy_tool.execute.call_count == 2
        assert set(r[0] for r in results) == {"tc3", "tc4"}

    @pytest.mark.asyncio
    async def test_summarize_messages(self, agent, mock_llm):
        # We need mock_llm to return a summary
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="System Summary", tool_calls=None))
        
        # Add 10 messages
        for i in range(10):
            agent.messages.append(Message(role="user", content=f"msg {i}"))
            
        # Force the condition to be true
        agent.config.token_limit = 10
        agent._estimate_tokens = MagicMock(return_value=100)
        
        await agent._summarize_messages()
        
        # summary should replace inner messages. 
        # system message (1) + summary (1) + recent messages (depends on config, default 5)
        assert len(agent.messages) <= 7 
        roles = [m.role for m in agent.messages]
        assert "system" in roles
        # check if it added the assistant summary
        assert any(m.role == "assistant" and "System Summary" in str(m.content) for m in agent.messages)
