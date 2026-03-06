"""命令系统测试"""

from types import SimpleNamespace

from xiaotie.commands import Commands


class DummySessionManager:
    def list_sessions(self):
        return []


class TestCommands:
    def test_cmd_parallel_updates_agent_and_config(self, tmp_path):
        agent = SimpleNamespace(
            workspace_dir=str(tmp_path),
            parallel_tools=True,
            config=SimpleNamespace(parallel_tools=True),
        )
        commands = Commands(agent=agent, session_mgr=DummySessionManager())

        ok, message = commands.cmd_parallel("")
        assert ok is True
        assert "关闭" in message
        assert agent.parallel_tools is False
        assert agent.config.parallel_tools is False

        ok, message = commands.cmd_parallel("")
        assert ok is True
        assert "开启" in message
        assert agent.parallel_tools is True
        assert agent.config.parallel_tools is True

    def test_cmd_metrics_text_and_json(self, tmp_path):
        telemetry = SimpleNamespace(
            snapshot=lambda: {
                "session_id": "s1",
                "runs_total": 3,
                "runs_success": 2,
                "runs_error": 1,
                "runs_cancelled": 0,
                "llm_calls_total": 5,
                "llm_error_rate": 0.2,
                "llm_latency_avg_sec": 0.5,
                "llm_latency_p95_sec": 0.9,
                "tool_calls_total": 4,
                "tool_error_rate": 0.25,
                "tool_latency_avg_sec": 0.2,
                "tool_latency_p95_sec": 0.4,
                "stream_flush_total": 10,
                "stream_events_per_flush": 8.5,
                "stream_queue_depth": 1,
            }
        )
        agent = SimpleNamespace(
            workspace_dir=str(tmp_path),
            parallel_tools=True,
            config=SimpleNamespace(parallel_tools=True),
            telemetry=telemetry,
        )
        commands = Commands(agent=agent, session_mgr=DummySessionManager())

        ok, message = commands.cmd_metrics("")
        assert ok is True
        assert "运行监控指标" in message
        assert "LLM 调用" in message

        ok, message = commands.cmd_metrics("json")
        assert ok is True
        assert '"session_id": "s1"' in message
