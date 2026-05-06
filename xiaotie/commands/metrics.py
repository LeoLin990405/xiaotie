"""
Metrics and observability commands Mixin.
"""

import json

from .base import CommandsBase


class MetricsCommandsMixin(CommandsBase):
    """Metrics related commands like metrics, status"""

    def cmd_metrics(self, args: str) -> tuple[bool, str]:
        """显示运行监控指标 (用法: /metrics [json])"""
        snapshot = self.agent.telemetry.snapshot()
        if args.strip() == "json":
            return True, json.dumps(snapshot, ensure_ascii=False, indent=2)

        lines = [
            "\\n📈 运行监控指标:\\n",
            f"  会话: {snapshot['session_id']}",
            f"  运行总数: {snapshot['runs_total']} (成功 {snapshot['runs_success']} / 失败 {snapshot['runs_error']} / 取消 {snapshot['runs_cancelled']})",
            f"  LLM 调用: {snapshot['llm_calls_total']} (错误率 {snapshot['llm_error_rate'] * 100:.2f}%)",
            f"  LLM 时延: avg {snapshot['llm_latency_avg_sec']:.3f}s / p95 {snapshot['llm_latency_p95_sec']:.3f}s",
            f"  工具调用: {snapshot['tool_calls_total']} (错误率 {snapshot['tool_error_rate'] * 100:.2f}%)",
            f"  工具时延: avg {snapshot['tool_latency_avg_sec']:.3f}s / p95 {snapshot['tool_latency_p95_sec']:.3f}s",
            f"  流式刷新: {snapshot['stream_flush_total']} 次，批均事件 {snapshot['stream_events_per_flush']:.2f}",
            f"  当前队列深度: {snapshot['stream_queue_depth']}",
        ]
        return True, "\\n".join(lines)
