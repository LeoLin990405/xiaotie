"""AgentRuntime 单元测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.agent.config import AgentConfig
from xiaotie.agent.runtime import AgentRuntime, RuntimeState, RuntimeStats
from xiaotie.schema import FunctionCall, LLMResponse, Message, ToolCall, ToolResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.provider = "test"
    llm.model = "test-model"
    llm.generate = AsyncMock(
        return_value=LLMResponse(content="你好！", tool_calls=None)
    )
    llm.generate_stream = AsyncMock(
        return_value=LLMResponse(content="你好！", tool_calls=None)
    )
    return llm


@pytest.fixture
def dummy_tool():
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
def runtime(mock_llm, dummy_tool):
    config = AgentConfig(max_steps=5, stream=False, quiet=True)
    return AgentRuntime(
        llm_client=mock_llm,
        system_prompt="你是小铁",
        tools=[dummy_tool],
        config=config,
        session_id="test-session",
    )


# ---------------------------------------------------------------------------
# RuntimeState enum
# ---------------------------------------------------------------------------

class TestRuntimeState:
    def test_enum_values(self):
        assert RuntimeState.IDLE.value == "idle"
        assert RuntimeState.THINKING.value == "thinking"
        assert RuntimeState.ACTING.value == "acting"
        assert RuntimeState.OBSERVING.value == "observing"
        assert RuntimeState.REFLECTING.value == "reflecting"

    def test_all_states_count(self):
        assert len(RuntimeState) == 5


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

class TestTransitions:
    def test_valid_transitions_completeness(self, runtime):
        """All states should have entries in _VALID_TRANSITIONS"""
        for state in RuntimeState:
            assert state in AgentRuntime._VALID_TRANSITIONS

    def test_idle_to_thinking(self, runtime):
        runtime._state = RuntimeState.IDLE
        runtime._transition(RuntimeState.THINKING)
        assert runtime.state == RuntimeState.THINKING

    def test_thinking_to_acting(self, runtime):
        runtime._state = RuntimeState.THINKING
        runtime._transition(RuntimeState.ACTING)
        assert runtime.state == RuntimeState.ACTING

    def test_thinking_to_idle(self, runtime):
        runtime._state = RuntimeState.THINKING
        runtime._transition(RuntimeState.IDLE)
        assert runtime.state == RuntimeState.IDLE

    def test_acting_to_observing(self, runtime):
        runtime._state = RuntimeState.ACTING
        runtime._transition(RuntimeState.OBSERVING)
        assert runtime.state == RuntimeState.OBSERVING

    def test_observing_to_reflecting(self, runtime):
        runtime._state = RuntimeState.OBSERVING
        runtime._transition(RuntimeState.REFLECTING)
        assert runtime.state == RuntimeState.REFLECTING

    def test_reflecting_to_thinking(self, runtime):
        runtime._state = RuntimeState.REFLECTING
        runtime._transition(RuntimeState.THINKING)
        assert runtime.state == RuntimeState.THINKING

    def test_reflecting_to_idle(self, runtime):
        runtime._state = RuntimeState.REFLECTING
        runtime._transition(RuntimeState.IDLE)
        assert runtime.state == RuntimeState.IDLE

    def test_invalid_idle_to_acting_raises(self, runtime):
        runtime._state = RuntimeState.IDLE
        with pytest.raises(RuntimeError, match="非法状态转移"):
            runtime._transition(RuntimeState.ACTING)

    def test_invalid_acting_to_thinking_raises(self, runtime):
        runtime._state = RuntimeState.ACTING
        with pytest.raises(RuntimeError, match="非法状态转移"):
            runtime._transition(RuntimeState.THINKING)

    def test_invalid_observing_to_idle_raises(self, runtime):
        runtime._state = RuntimeState.OBSERVING
        with pytest.raises(RuntimeError, match="非法状态转移"):
            runtime._transition(RuntimeState.IDLE)

    def test_transition_records_stats(self, runtime):
        runtime._state = RuntimeState.IDLE
        runtime._transition(RuntimeState.THINKING)
        assert len(runtime._stats.state_transitions) == 1
        old, new, ts = runtime._stats.state_transitions[0]
        assert old == "idle"
        assert new == "thinking"


# ---------------------------------------------------------------------------
# run() - direct completion (no tool calls)
# ---------------------------------------------------------------------------

class TestRunDirectCompletion:
    async def test_run_returns_content(self, runtime, mock_llm):
        result = await runtime.run("你好")
        assert result == "你好！"
        mock_llm.generate.assert_awaited()

    async def test_run_appends_user_message(self, runtime):
        await runtime.run("测试")
        roles = [m.role for m in runtime.messages]
        assert "user" in roles

    async def test_run_appends_assistant_message(self, runtime):
        await runtime.run("测试")
        roles = [m.role for m in runtime.messages]
        assert "assistant" in roles

    async def test_run_state_returns_to_idle(self, runtime):
        await runtime.run("测试")
        assert runtime.state == RuntimeState.IDLE


# ---------------------------------------------------------------------------
# run() - with tool calls then completion
# ---------------------------------------------------------------------------

class TestRunWithToolCalls:
    async def test_tool_call_then_complete(self, runtime, mock_llm, dummy_tool):
        call_count = 0

        async def generate_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="tc_1",
                            function=FunctionCall(name="dummy", arguments={}),
                        )
                    ],
                )
            return LLMResponse(content="完成", tool_calls=None)

        mock_llm.generate = AsyncMock(side_effect=generate_side_effect)
        result = await runtime.run("do something")
        assert result == "完成"
        assert dummy_tool.execute.call_count == 1
        assert runtime._stats.total_tool_calls >= 1
        assert runtime._stats.total_llm_calls == 2

    async def test_max_steps_reached(self, mock_llm, dummy_tool):
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

        config = AgentConfig(max_steps=3, stream=False, quiet=True)
        rt = AgentRuntime(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            config=config,
            session_id="test-max",
        )
        result = await rt.run("loop")
        assert "最大步数" in result


# ---------------------------------------------------------------------------
# Cancel mechanism
# ---------------------------------------------------------------------------

class TestCancel:
    async def test_cancel_via_event(self, mock_llm, dummy_tool):
        config = AgentConfig(max_steps=10, stream=False, quiet=True)
        rt = AgentRuntime(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            config=config,
            session_id="test-cancel",
        )
        cancel = asyncio.Event()
        rt.cancel_event = cancel
        cancel.set()

        result = await rt.run("do something")
        assert "取消" in result

    async def test_cancel_flag_during_loop(self, mock_llm, dummy_tool):
        call_count = 0
        config = AgentConfig(max_steps=10, stream=False, quiet=True)
        rt = AgentRuntime(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            config=config,
            session_id="test-cancel2",
        )

        async def generate_with_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                rt._cancelled = True
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
        result = await rt.run("test")
        assert "取消" in result


# ---------------------------------------------------------------------------
# Session lock
# ---------------------------------------------------------------------------

class TestSessionLock:
    async def test_busy_session_returns_warning(self, mock_llm, dummy_tool):
        config = AgentConfig(max_steps=5, stream=False, quiet=True)
        rt = AgentRuntime(
            llm_client=mock_llm,
            system_prompt="test",
            tools=[dummy_tool],
            config=config,
            session_id="test-busy",
        )
        # Manually acquire the session lock
        from xiaotie.agent.state import _session_state
        acquired = await _session_state.acquire("test-busy")
        assert acquired
        try:
            result = await rt.run("test")
            assert "会话正在处理中" in result or "无法获取会话锁" in result
        finally:
            await _session_state.release("test-busy")


# ---------------------------------------------------------------------------
# step() - single step execution
# ---------------------------------------------------------------------------

class TestStep:
    async def test_step_no_tool_calls(self, runtime, mock_llm):
        state, content = await runtime.step("hello")
        assert state == RuntimeState.IDLE
        assert content == "你好！"

    async def test_step_with_tool_calls(self, runtime, mock_llm, dummy_tool):
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            content="thinking",
            tool_calls=[
                ToolCall(
                    id="tc_step",
                    function=FunctionCall(name="dummy", arguments={}),
                )
            ],
        ))
        state, content = await runtime.step("do something")
        assert state == RuntimeState.REFLECTING
        assert dummy_tool.execute.call_count == 1


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------

class TestReset:
    async def test_reset_clears_history(self, runtime):
        await runtime.run("hello")
        runtime.reset()
        assert len(runtime.messages) == 1
        assert runtime.messages[0].role == "system"

    async def test_reset_state_to_idle(self, runtime):
        await runtime.run("hello")
        runtime.reset()
        assert runtime.state == RuntimeState.IDLE

    def test_reset_clears_stats(self, runtime):
        runtime._stats.steps = 5
        runtime._stats.total_tool_calls = 10
        runtime.reset()
        assert runtime._stats.steps == 0
        assert runtime._stats.total_tool_calls == 0

    def test_reset_clears_token_stats(self, runtime):
        runtime.response_handler.api_total_tokens = 100
        runtime.reset()
        assert runtime.response_handler.api_total_tokens == 0


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:
    async def test_stats_after_run(self, runtime):
        await runtime.run("hi")
        stats = runtime.get_stats()
        assert stats["session_id"] == "test-session"
        assert stats["state"] == "idle"
        assert stats["message_count"] >= 3
        assert stats["steps"] >= 1
        assert stats["total_llm_calls"] >= 1
        assert "telemetry" in stats
        assert "permission" in stats

    def test_stats_initial(self, runtime):
        stats = runtime.get_stats()
        assert stats["state"] == "idle"
        assert stats["steps"] == 0


# ---------------------------------------------------------------------------
# _build_context_messages() - ContextEngine + RepoMap integration
# ---------------------------------------------------------------------------

class TestBuildContextMessages:
    async def test_no_context_engine_returns_raw_messages(self, runtime):
        """Without ContextEngine, _build_context_messages returns self.messages as-is."""
        runtime.messages.append(Message(role="user", content="hello"))
        result = await runtime._build_context_messages()
        assert result is runtime.messages

    async def test_with_context_engine(self, runtime):
        """With ContextEngine, compose_context is called and to_messages returns optimized list."""
        mock_bundle = MagicMock()
        optimized = [Message(role="system", content="optimized")]
        mock_bundle.to_messages.return_value = optimized

        mock_engine = AsyncMock()
        mock_engine.compose_context = AsyncMock(return_value=mock_bundle)

        runtime.set_context_engine(mock_engine)
        runtime.messages.append(Message(role="user", content="test query"))

        result = await runtime._build_context_messages()

        assert result == optimized
        mock_engine.compose_context.assert_called_once()
        call_kwargs = mock_engine.compose_context.call_args
        assert call_kwargs.kwargs.get("query") == "test query"

    async def test_with_repomap_engine(self, runtime):
        """RepoMap is called and its output passed to compose_context."""
        mock_bundle = MagicMock()
        mock_bundle.to_messages.return_value = [Message(role="system", content="ok")]

        mock_context = AsyncMock()
        mock_context.compose_context = AsyncMock(return_value=mock_bundle)

        mock_repomap = MagicMock()
        mock_repomap.get_ranked_map.return_value = "src/main.py:\n  main (L1)"

        runtime.set_context_engine(mock_context)
        runtime.set_repomap_engine(mock_repomap)
        runtime.messages.append(Message(role="user", content="show me the code"))

        result = await runtime._build_context_messages()

        mock_repomap.get_ranked_map.assert_called_once()
        compose_kwargs = mock_context.compose_context.call_args.kwargs
        assert compose_kwargs.get("repo_map") == "src/main.py:\n  main (L1)"

    async def test_context_engine_failure_falls_back(self, runtime):
        """If ContextEngine raises, fallback to raw messages."""
        mock_engine = AsyncMock()
        mock_engine.compose_context = AsyncMock(side_effect=RuntimeError("boom"))

        runtime.set_context_engine(mock_engine)
        runtime.messages.append(Message(role="user", content="test"))

        result = await runtime._build_context_messages()
        assert result is runtime.messages

    async def test_repomap_failure_still_composes(self, runtime):
        """If RepoMap fails, compose_context is still called with repo_map=None."""
        mock_bundle = MagicMock()
        mock_bundle.to_messages.return_value = [Message(role="system", content="ok")]

        mock_context = AsyncMock()
        mock_context.compose_context = AsyncMock(return_value=mock_bundle)

        mock_repomap = MagicMock()
        mock_repomap.get_ranked_map.side_effect = Exception("tree-sitter fail")

        runtime.set_context_engine(mock_context)
        runtime.set_repomap_engine(mock_repomap)
        runtime.messages.append(Message(role="user", content="test"))

        result = await runtime._build_context_messages()
        compose_kwargs = mock_context.compose_context.call_args.kwargs
        assert compose_kwargs.get("repo_map") is None


# ---------------------------------------------------------------------------
# _extract_mentioned_files()
# ---------------------------------------------------------------------------

class TestExtractMentionedFiles:
    def test_extracts_python_files(self, runtime):
        runtime.messages.append(Message(role="user", content="edit src/main.py and utils/helper.py"))
        files = runtime._extract_mentioned_files()
        assert "src/main.py" in files
        assert "utils/helper.py" in files

    def test_extracts_multiple_languages(self, runtime):
        runtime.messages.append(Message(role="user", content="check app.ts and lib.go and main.rs"))
        files = runtime._extract_mentioned_files()
        assert "app.ts" in files
        assert "lib.go" in files
        assert "main.rs" in files

    def test_limits_to_20(self, runtime):
        many_files = " ".join([f"file{i}.py" for i in range(30)])
        runtime.messages.append(Message(role="user", content=many_files))
        files = runtime._extract_mentioned_files()
        assert len(files) <= 20

    def test_no_files_returns_empty(self, runtime):
        runtime.messages.append(Message(role="user", content="hello world"))
        files = runtime._extract_mentioned_files()
        assert files == []


# ---------------------------------------------------------------------------
# Compatibility shims
# ---------------------------------------------------------------------------

class TestCompatibilityShims:
    def test_tools_property(self, runtime):
        assert isinstance(runtime.tools, dict)
        assert "dummy" in runtime.tools

    def test_llm_property(self, runtime, mock_llm):
        assert runtime.llm is mock_llm

    def test_stream_property(self, runtime):
        assert runtime.stream is False  # config.stream = False
        runtime.stream = True
        assert runtime.config.stream is True

    def test_enable_thinking_property(self, runtime):
        original = runtime.enable_thinking
        runtime.enable_thinking = not original
        assert runtime.config.enable_thinking is not original

    def test_parallel_tools_property(self, runtime):
        original = runtime.parallel_tools
        runtime.parallel_tools = not original
        assert runtime.config.parallel_tools is not original

    def test_max_steps_property(self, runtime):
        assert runtime.max_steps == 5

    def test_token_limit_property(self, runtime):
        assert runtime.token_limit == runtime.config.token_limit

    def test_quiet_property(self, runtime):
        assert runtime.quiet is True

    def test_token_counters(self, runtime):
        assert runtime.api_total_tokens == 0
        assert runtime.api_input_tokens == 0
        assert runtime.api_output_tokens == 0

    def test_on_thinking_callback(self, runtime):
        cb = lambda x: x
        runtime.on_thinking = cb
        assert runtime.response_handler.on_thinking is cb

    def test_on_content_callback(self, runtime):
        cb = lambda x: x
        runtime.on_content = cb
        assert runtime.response_handler.on_content is cb

    def test_estimate_tokens(self, runtime):
        tokens = runtime._estimate_tokens()
        assert isinstance(tokens, int)
        assert tokens >= 0


# ---------------------------------------------------------------------------
# set_context_engine / set_repomap_engine
# ---------------------------------------------------------------------------

class TestOptionalEngines:
    def test_set_context_engine(self, runtime):
        engine = MagicMock()
        runtime.set_context_engine(engine)
        assert runtime._context_engine is engine

    def test_set_repomap_engine(self, runtime):
        engine = MagicMock()
        runtime.set_repomap_engine(engine)
        assert runtime._repomap_engine is engine
