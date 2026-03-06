"""
工具执行器 - 从 Agent god class 中提取的工具执行逻辑

支持顺序和并行执行，集成权限检查和审计日志。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional, Protocol

from xiaotie.events import (
    Event,
    EventType,
    ToolCompleteEvent,
    ToolStartEvent,
    get_event_broker,
)
from xiaotie.permissions import PermissionManager
from xiaotie.telemetry import AgentTelemetry
from xiaotie.tools import Tool

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    function_name: str
    content: str
    success: bool = True
    elapsed: float = 0.0


# 高特异性敏感信息模式
_SENSITIVE_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "检测到疑似 AWS Access Key"),
    (re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----"), "检测到私钥内容"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "检测到疑似 GitHub Token"),
    (re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"), "检测到疑似 GitLab Token"),
    (re.compile(
        r'(?i)(?:api[_-]?key|secret[_-]?key|api[_-]?secret|password|passwd|private[_-]?key)'
        r'\s*[:=]\s*["\']?([A-Za-z0-9+/=_\-]{16,})["\']?'
    ), "检测到疑似凭据赋值"),
]


class ToolExecutor:
    """工具执行器

    负责工具的查找、权限检查、执行和结果处理。
    从 Agent._execute_single_tool / _execute_tools_parallel 提取。
    """

    def __init__(
        self,
        tools: dict[str, Tool],
        permission_manager: PermissionManager,
        telemetry: AgentTelemetry,
        session_id: str,
        quiet: bool = False,
    ):
        self.tools = tools
        self.permission_manager = permission_manager
        self.telemetry = telemetry
        self.session_id = session_id
        self.quiet = quiet
        self._event_broker = get_event_broker()

        # LLM info for audit (set by runtime)
        self.provider_name: str = "unknown"
        self.model_name: str = "unknown"

    async def execute(
        self,
        tool_calls: list,
        parallel: bool = True,
    ) -> list[ToolResult]:
        """执行一批工具调用

        Args:
            tool_calls: LLM 返回的工具调用列表
            parallel: 是否并行执行

        Returns:
            ToolResult 列表
        """
        if not tool_calls:
            return []

        if parallel and len(tool_calls) > 1:
            return await self._execute_parallel(tool_calls)
        return await self._execute_sequential(tool_calls)

    async def _execute_sequential(self, tool_calls: list) -> list[ToolResult]:
        """顺序执行"""
        results = []
        for tc in tool_calls:
            result = await self._execute_one(tc)
            results.append(result)
        return results

    async def _execute_parallel(self, tool_calls: list) -> list[ToolResult]:
        """并行执行"""
        if not self.quiet:
            logger.info("并行执行 %d 个工具...", len(tool_calls))

        start = time.perf_counter()
        tasks = [self._execute_one(tc) for tc in tool_calls]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - start

        if not self.quiet:
            logger.info("并行执行完成, 耗时 %.2fs", elapsed)

        results = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                tc = tool_calls[i]
                results.append(ToolResult(
                    tool_call_id=tc.id,
                    function_name=tc.function.name,
                    content=f"执行异常: {r}",
                    success=False,
                ))
            else:
                results.append(r)
        return results

    async def _execute_one(self, tool_call) -> ToolResult:
        """执行单个工具调用"""
        tool_call_id = tool_call.id
        function_name = tool_call.function.name
        arguments = tool_call.function.arguments

        risk_level = self.permission_manager.get_risk_level(function_name, arguments).value
        tool_origin = self._resolve_tool_origin(function_name)
        audit_data = self._make_audit_data(tool_origin, risk_level,
                                            arguments_summary=_summarize_arguments(arguments))

        # 发布开始事件
        await self._publish_event(ToolStartEvent(
            tool_name=function_name,
            tool_id=tool_call_id,
            arguments=arguments,
            data=audit_data,
        ))

        if not self.quiet:
            args_display = ", ".join(f"{k}={repr(v)[:50]}" for k, v in arguments.items())
            logger.info("工具调用: %s(%s)", function_name, args_display)

        # 查找工具
        tool = self.tools.get(function_name)
        if not tool:
            available = ", ".join(sorted(self.tools.keys())[:5])
            error_msg = f"错误: 未知工具 '{function_name}'\n  → 可用工具: {available}..."
            await self._publish_tool_complete(function_name, tool_call_id, False, 0.0, {}, error=error_msg)
            return ToolResult(tool_call_id, function_name, error_msg, success=False)

        # 权限检查
        allowed, reason = await self.permission_manager.check_permission(function_name, arguments)
        if not allowed:
            error_msg = f"权限拒绝: {reason}\n  → 当前风险等级: {risk_level.upper()}"
            await self._publish_tool_complete(function_name, tool_call_id, False, 0.0, {}, error=error_msg)
            return ToolResult(tool_call_id, function_name, error_msg, success=False)

        # 执行
        start_time = time.perf_counter()
        try:
            result = await tool.execute(**arguments)
            elapsed = time.perf_counter() - start_time

            if result.success:
                content = result.content
                content, blocked, block_reason = _filter_sensitive_output(content)
                if blocked:
                    content = f"⚠️ 敏感内容已脱敏 ({block_reason}):\n{content}"

                if not self.quiet:
                    preview = content[:100].replace("\n", " ")
                    logger.info("工具 %s OK (%.1fs): %s", function_name, elapsed, preview)

                await self._publish_tool_complete(
                    function_name, tool_call_id, not blocked, elapsed, audit_data,
                    result=content, error=block_reason if blocked else "",
                )
                return ToolResult(tool_call_id, function_name, content, success=True, elapsed=elapsed)
            else:
                error_content = f"错误: {result.error}"
                await self._publish_tool_complete(
                    function_name, tool_call_id, False, elapsed, audit_data, error=result.error or "",
                )
                return ToolResult(tool_call_id, function_name, error_content, success=False, elapsed=elapsed)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            error_content = f"执行异常: {e}"
            logger.error("工具 %s 异常: %s", function_name, e)
            await self._publish_tool_complete(
                function_name, tool_call_id, False, elapsed, audit_data, error=str(e),
            )
            return ToolResult(tool_call_id, function_name, error_content, success=False, elapsed=elapsed)

    def _resolve_tool_origin(self, function_name: str) -> str:
        tool = self.tools.get(function_name)
        if tool is None:
            return "unknown"
        module = tool.__class__.__module__
        if module.startswith("xiaotie.mcp."):
            return "mcp"
        if function_name in {"web_search", "web_fetch"}:
            return "external_api"
        return "internal"

    def _make_audit_data(self, tool_origin: str, risk_level: str, **extra) -> dict:
        audit = {
            "caller": "agent",
            "provider": self.provider_name,
            "model": self.model_name,
            "tool_origin": tool_origin,
            "risk_level": risk_level,
        }
        audit.update(extra)
        return {"audit": audit}

    async def _publish_event(self, event):
        event.session_id = self.session_id
        await self._event_broker.publish(event)

    async def _publish_tool_complete(self, function_name, tool_call_id, success, elapsed, audit_data, *, result="", error=""):
        await self._publish_event(ToolCompleteEvent(
            tool_name=function_name,
            tool_id=tool_call_id,
            success=success,
            result=result[:500] if result else "",
            error=error or None,
            duration=elapsed,
            data=audit_data,
        ))
        self.telemetry.record_tool_call(tool_name=function_name, latency_sec=elapsed, success=success)


def _filter_sensitive_output(output: str) -> tuple[str, bool, str]:
    """过滤敏感输出"""
    if not isinstance(output, str) or not output:
        return output, False, ""
    reasons = []
    filtered = output
    for pattern, reason in _SENSITIVE_PATTERNS:
        if pattern.search(filtered):
            filtered = pattern.sub("[REDACTED]", filtered)
            if reason not in reasons:
                reasons.append(reason)
    if reasons:
        return filtered, True, "; ".join(reasons)
    return output, False, ""


def _summarize_arguments(arguments: Dict) -> Dict:
    """摘要参数用于审计"""
    summary = {}
    for key, value in arguments.items():
        value_str = str(value)
        summary[key] = value_str[:120] + "..." if len(value_str) > 120 else value_str
    return summary
