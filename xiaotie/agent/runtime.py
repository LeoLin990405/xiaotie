"""
AgentRuntime - 状态机驱动的 Agent 运行时

将 Agent god class 重构为清晰的状态机:
IDLE → THINKING → ACTING → OBSERVING → REFLECTING → IDLE/THINKING

组合使用 ToolExecutor 和 ResponseHandler，支持 ContextEngine 和 RepoMapEngine 集成。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from xiaotie.events import (
    AgentStartEvent,
    AgentStepEvent,
    Event,
    EventType,
    get_event_broker,
)
from xiaotie.llm import LLMClient
from xiaotie.permissions import PermissionManager
from xiaotie.schema import Message
from xiaotie.telemetry import AgentTelemetry
from xiaotie.tools import Tool

from .config import AgentConfig
from .executor import ToolExecutor, ToolResult
from .response import ResponseHandler
from .state import _session_state

logger = logging.getLogger(__name__)


class RuntimeState(Enum):
    """Agent 运行时状态"""
    IDLE = "idle"
    THINKING = "thinking"       # 等待 LLM 响应
    ACTING = "acting"           # 执行工具调用
    OBSERVING = "observing"     # 处理工具结果
    REFLECTING = "reflecting"   # 检查是否需要继续


@dataclass
class RuntimeStats:
    """运行时统计"""
    steps: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    start_time: float = 0.0
    state_transitions: list = field(default_factory=list)


class AgentRuntime:
    """状态机驱动的 Agent 运行时

    将 Agent 的执行循环建模为显式状态机，每个状态有清晰的
    入口条件、执行逻辑和转移规则。

    组件:
    - ToolExecutor: 工具执行（权限、审计、并行）
    - ResponseHandler: LLM 响应（流式、token 管理、摘要）

    用法:
        runtime = AgentRuntime(llm, system_prompt, tools)
        result = await runtime.run("implement auth feature")
    """

    # 合法状态转移
    _VALID_TRANSITIONS = {
        RuntimeState.IDLE: {RuntimeState.THINKING},
        RuntimeState.THINKING: {RuntimeState.ACTING, RuntimeState.IDLE},  # IDLE = 完成
        RuntimeState.ACTING: {RuntimeState.OBSERVING},
        RuntimeState.OBSERVING: {RuntimeState.REFLECTING},
        RuntimeState.REFLECTING: {RuntimeState.THINKING, RuntimeState.IDLE},
    }

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[Tool],
        config: Optional[AgentConfig] = None,
        workspace_dir: str = ".",
        session_id: Optional[str] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.config = config or AgentConfig()
        self.workspace_dir = workspace_dir

        # 消息历史
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]

        # 状态
        self._state = RuntimeState.IDLE
        self._stats = RuntimeStats()
        self._cancelled = False
        self.cancel_event: Optional[asyncio.Event] = None

        # 事件
        self._event_broker = get_event_broker()

        # 遥测
        self.telemetry = AgentTelemetry(session_id=self.session_id)

        # 权限管理
        self.permission_manager = PermissionManager(
            auto_approve_low_risk=True,
            auto_approve_medium_risk=True,
            interactive=not self.config.quiet,
            require_double_confirm_high_risk=True,
        )

        # 工具表
        tools_dict = {t.name: t for t in tools}

        # 组件
        self.executor = ToolExecutor(
            tools=tools_dict,
            permission_manager=self.permission_manager,
            telemetry=self.telemetry,
            session_id=self.session_id,
            quiet=self.config.quiet,
        )
        self.response_handler = ResponseHandler(
            llm=llm_client,
            telemetry=self.telemetry,
            session_id=self.session_id,
            token_limit=self.config.token_limit,
            summary_threshold=self.config.summary_threshold,
            summary_keep_recent=self.config.summary_keep_recent,
            enable_thinking=self.config.enable_thinking,
            quiet=self.config.quiet,
        )

        # 设置 LLM 信息 (供审计)
        provider = getattr(llm_client, "provider", "unknown")
        self.executor.provider_name = getattr(provider, "value", str(provider))
        self.executor.model_name = getattr(
            getattr(llm_client, "_client", None), "model", None
        ) or getattr(llm_client, "model", "unknown")

        # 可选集成
        self._context_engine = None
        self._repomap_engine = None

    @property
    def state(self) -> RuntimeState:
        return self._state

    def set_context_engine(self, engine):
        """集成 ContextEngine (可选)"""
        self._context_engine = engine

    def set_repomap_engine(self, engine):
        """集成 RepoMapEngine (可选)"""
        self._repomap_engine = engine

    def _transition(self, new_state: RuntimeState):
        """执行状态转移，检查合法性"""
        valid = self._VALID_TRANSITIONS.get(self._state, set())
        if new_state not in valid:
            raise RuntimeError(
                f"非法状态转移: {self._state.value} → {new_state.value}. "
                f"合法目标: {[s.value for s in valid]}"
            )
        old = self._state
        self._state = new_state
        self._stats.state_transitions.append((old.value, new_state.value, time.time()))
        logger.debug("状态转移: %s → %s", old.value, new_state.value)

    def _check_cancelled(self) -> bool:
        if self._cancelled:
            return True
        if self.cancel_event is not None and self.cancel_event.is_set():
            self._cancelled = True
            return True
        return False

    async def run(self, prompt: str) -> str:
        """运行 Agent 主循环

        Args:
            prompt: 用户输入

        Returns:
            最终响应文本
        """
        if _session_state.is_busy(self.session_id):
            return "⚠️ 会话正在处理中，请稍候"

        if not await _session_state.acquire(self.session_id):
            return "⚠️ 无法获取会话锁"

        self._cancelled = False
        self._stats = RuntimeStats(start_time=time.time())
        self.telemetry.record_run_start()

        try:
            # 添加用户消息
            self.messages.append(Message(role="user", content=prompt))
            await self._publish_event(AgentStartEvent(
                user_input=prompt,
                data={"message_count": len(self.messages)},
            ))

            return await self._loop()
        finally:
            self._state = RuntimeState.IDLE
            await _session_state.release(self.session_id)

    async def _build_context_messages(self) -> list[Message]:
        """使用 ContextEngine + RepoMap 构建优化后的消息列表

        如果未设置 ContextEngine，直接返回原始消息。
        """
        if self._context_engine is None:
            return self.messages

        # 提取系统提示和用户查询
        system_prompt = ""
        query = ""
        for msg in self.messages:
            if msg.role == "system":
                system_prompt = msg.content or ""
            elif msg.role == "user":
                query = msg.content or ""  # 使用最后一条用户消息

        # 生成 repo map (如果可用)
        repo_map_str = None
        if self._repomap_engine is not None:
            try:
                # 从对话中提取提到的文件路径作为 chat_files
                chat_files = self._extract_mentioned_files()
                repo_map_str = self._repomap_engine.get_ranked_map(
                    chat_fnames=chat_files,
                    other_fnames=[],
                    max_map_tokens=int(self.config.token_limit * 0.15),
                )
            except Exception as e:
                logger.warning("RepoMap 生成失败，跳过: %s", e)

        # 使用 ContextEngine 组装上下文
        try:
            bundle = await self._context_engine.compose_context(
                query=query,
                conversation=self.messages,
                repo_map=repo_map_str,
                system_prompt=system_prompt,
            )
            return bundle.to_messages(system_prompt)
        except Exception as e:
            logger.warning("ContextEngine 组装失败，使用原始消息: %s", e)
            return self.messages

    def _extract_mentioned_files(self) -> list[str]:
        """从对话历史中提取提到的文件路径"""
        import re
        files = set()
        pattern = re.compile(r'[\w./\\-]+\.(?:py|js|ts|go|rs|java|c|cpp|h)')
        for msg in self.messages:
            if msg.content:
                matches = pattern.findall(msg.content)
                files.update(matches)
        return list(files)[:20]  # 限制数量避免过载

    async def _loop(self) -> str:
        """状态机主循环"""
        for step in range(self.config.max_steps):
            self._stats.steps = step + 1

            # === THINKING ===
            self._transition(RuntimeState.THINKING)

            if self._check_cancelled():
                self.telemetry.record_run_end("cancelled")
                self._transition(RuntimeState.IDLE)
                return "⚠️ 任务已取消"

            await self._publish_event(AgentStepEvent(
                step=step + 1, total_steps=self.config.max_steps,
            ))

            # Token 管理
            self.messages = await self.response_handler.maybe_summarize(self.messages)

            # 构建上下文优化后的消息 (ContextEngine + RepoMap)
            context_messages = await self._build_context_messages()

            # 调用 LLM
            tool_schemas = [t.to_schema() for t in self.executor.tools.values()]
            llm_start = time.perf_counter()
            try:
                response = await self.response_handler.generate(
                    messages=context_messages,
                    tool_schemas=tool_schemas,
                    stream=self.config.stream,
                )
            except Exception as e:
                await self._publish_event(Event(type=EventType.AGENT_ERROR, data={"error": str(e)}))
                self.telemetry.record_run_end("error")
                self._transition(RuntimeState.IDLE)
                return f"❌ LLM 调用失败: {e}"

            self._stats.total_llm_calls += 1

            # 添加 assistant 消息
            self.messages.append(Message(
                role="assistant",
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
            ))

            # 无工具调用 → 完成
            if not response.tool_calls:
                await self._publish_event(Event(
                    type=EventType.AGENT_COMPLETE,
                    data={"content": response.content},
                ))
                self.telemetry.record_run_end("success")
                self._transition(RuntimeState.IDLE)
                return response.content

            # === ACTING ===
            self._transition(RuntimeState.ACTING)
            tool_results = await self.executor.execute(
                response.tool_calls,
                parallel=self.config.parallel_tools,
            )
            self._stats.total_tool_calls += len(tool_results)

            # === OBSERVING ===
            self._transition(RuntimeState.OBSERVING)
            for tr in tool_results:
                self.messages.append(Message(
                    role="tool",
                    content=tr.content,
                    tool_call_id=tr.tool_call_id,
                    name=tr.function_name,
                ))

            # === REFLECTING ===
            self._transition(RuntimeState.REFLECTING)

            if self._check_cancelled():
                self.telemetry.record_run_end("cancelled")
                self._transition(RuntimeState.IDLE)
                return "⚠️ 任务已取消"

            # 继续下一轮 → THINKING (由循环顶部执行)

        self.telemetry.record_run_end("error")
        self._transition(RuntimeState.IDLE)
        return "⚠️ 达到最大步数限制"

    async def step(self, prompt: Optional[str] = None) -> tuple[RuntimeState, str]:
        """单步执行 (用于外部控制循环)

        Returns:
            (new_state, content)
        """
        if prompt:
            self.messages.append(Message(role="user", content=prompt))

        if self._state == RuntimeState.IDLE:
            self._transition(RuntimeState.THINKING)

        tool_schemas = [t.to_schema() for t in self.executor.tools.values()]
        response = await self.response_handler.generate(
            messages=self.messages,
            tool_schemas=tool_schemas,
            stream=self.config.stream,
        )

        self.messages.append(Message(
            role="assistant",
            content=response.content,
            thinking=response.thinking,
            tool_calls=response.tool_calls,
        ))

        if not response.tool_calls:
            self._transition(RuntimeState.IDLE)
            return RuntimeState.IDLE, response.content

        self._transition(RuntimeState.ACTING)
        results = await self.executor.execute(response.tool_calls, parallel=self.config.parallel_tools)

        self._transition(RuntimeState.OBSERVING)
        for tr in results:
            self.messages.append(Message(
                role="tool", content=tr.content,
                tool_call_id=tr.tool_call_id, name=tr.function_name,
            ))

        self._transition(RuntimeState.REFLECTING)
        return RuntimeState.REFLECTING, response.content

    # ── Compatibility shims for Commands / CLI / TUI ──────────────────
    # These properties let code that was written for the old Agent class
    # work unchanged with AgentRuntime.

    @property
    def tools(self) -> dict:
        return self.executor.tools

    @property
    def llm(self) -> LLMClient:
        return self.response_handler.llm

    @property
    def stream(self) -> bool:
        return self.config.stream

    @stream.setter
    def stream(self, value: bool):
        self.config.stream = value

    @property
    def enable_thinking(self) -> bool:
        return self.config.enable_thinking

    @enable_thinking.setter
    def enable_thinking(self, value: bool):
        self.config.enable_thinking = value

    @property
    def parallel_tools(self) -> bool:
        return self.config.parallel_tools

    @parallel_tools.setter
    def parallel_tools(self, value: bool):
        self.config.parallel_tools = value

    @property
    def max_steps(self) -> int:
        return self.config.max_steps

    @property
    def token_limit(self) -> int:
        return self.config.token_limit

    @property
    def quiet(self) -> bool:
        return self.config.quiet

    @property
    def api_total_tokens(self) -> int:
        return self.response_handler.api_total_tokens

    @property
    def api_input_tokens(self) -> int:
        return self.response_handler.api_input_tokens

    @property
    def api_output_tokens(self) -> int:
        return self.response_handler.api_output_tokens

    @property
    def on_thinking(self):
        return self.response_handler.on_thinking

    @on_thinking.setter
    def on_thinking(self, value):
        self.response_handler.on_thinking = value

    @property
    def on_content(self):
        return self.response_handler.on_content

    @on_content.setter
    def on_content(self, value):
        self.response_handler.on_content = value

    def _estimate_tokens(self) -> int:
        """Compatibility: estimate tokens for current messages."""
        return self.response_handler.estimate_tokens(self.messages)

    def reset(self):
        """重置运行时"""
        system_msg = self.messages[0] if self.messages and self.messages[0].role == "system" else None
        self.messages = [system_msg] if system_msg else []
        self._state = RuntimeState.IDLE
        self._cancelled = False
        self._stats = RuntimeStats()
        self.response_handler.api_total_tokens = 0
        self.response_handler.api_input_tokens = 0
        self.response_handler.api_output_tokens = 0
        self.response_handler._cached_token_count = 0
        self.response_handler._cached_message_count = 0

    def get_stats(self) -> dict:
        """获取运行时统计"""
        return {
            "session_id": self.session_id,
            "state": self._state.value,
            "message_count": len(self.messages),
            "steps": self._stats.steps,
            "total_tool_calls": self._stats.total_tool_calls,
            "total_llm_calls": self._stats.total_llm_calls,
            "estimated_tokens": self.response_handler.estimate_tokens(self.messages),
            "api_total_tokens": self.response_handler.api_total_tokens,
            "tool_count": len(self.executor.tools),
            "telemetry": self.telemetry.snapshot(),
            "permission": self.permission_manager.get_stats(),
        }

    async def _publish_event(self, event: Event):
        event.session_id = self.session_id
        await self._event_broker.publish(event)
