"""工具基类"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict

from ..schema import ToolResult


class Tool(ABC):
    """工具抽象基类"""

    def __init__(self):
        self.execution_stats = {
            "call_count": 0,
            "total_time": 0.0,
            "success_count": 0,
            "error_count": 0,
            "avg_time": 0.0,
        }
        self.agent = None  # Agent引用，用于访问token计数器等

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """参数 JSON Schema"""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""

    async def execute_with_monitoring(self, **kwargs) -> ToolResult:
        """执行工具并监控性能"""
        start_time = time.perf_counter()
        token_counter_before = getattr(self.agent, "token_counter", None) if self.agent else None

        try:
            result = await self.execute(**kwargs)

            execution_time = time.perf_counter() - start_time
            tokens_used = None
            if (
                token_counter_before is not None
                and self.agent
                and hasattr(self.agent, "token_counter")
            ):
                tokens_used = self.agent.token_counter - token_counter_before

            # 更新执行统计
            self._update_execution_stats(execution_time, success=True)

            # 异步记录执行指标（不阻塞主执行流程）
            if hasattr(self, "_record_execution_metrics"):
                try:
                    asyncio.create_task(
                        self._record_execution_metrics(
                            execution_time=execution_time, tokens_used=tokens_used, success=True
                        )
                    )
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning("记录执行指标失败", exc_info=e)

            return result
        except Exception as e:
            execution_time = time.perf_counter() - start_time  # 修复：使用正确的变量名

            # 更新执行统计
            self._update_execution_stats(execution_time, success=False)

            # 异步记录错误指标
            if hasattr(self, "_record_execution_metrics"):
                try:
                    asyncio.create_task(
                        self._record_execution_metrics(
                            execution_time=execution_time,
                            tokens_used=None,
                            success=False,
                            error=str(e),
                        )
                    )
                except Exception as metric_e:
                    import logging

                    logging.getLogger(__name__).warning("记录错误指标失败", exc_info=metric_e)

            raise

    def _update_execution_stats(self, execution_time: float, success: bool):
        """更新执行统计"""
        self.execution_stats["call_count"] += 1
        self.execution_stats["total_time"] += execution_time
        if success:
            self.execution_stats["success_count"] += 1
        else:
            self.execution_stats["error_count"] += 1

        # 计算平均时间
        if self.execution_stats["call_count"] > 0:
            self.execution_stats["avg_time"] = (
                self.execution_stats["total_time"] / self.execution_stats["call_count"]
            )

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return self.execution_stats.copy()

    def to_schema(self) -> dict[str, Any]:
        """转换为 Anthropic 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
