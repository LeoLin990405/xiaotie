from xiaotie.telemetry import AgentTelemetry


class TestAgentTelemetry:
    def test_snapshot_fields(self):
        telemetry = AgentTelemetry(session_id="s1")
        telemetry.record_run_start()
        telemetry.record_llm_call(provider="openai", model="gpt-4o", latency_sec=0.5, success=True)
        telemetry.record_llm_call(provider="openai", model="gpt-4o", latency_sec=1.0, success=False)
        telemetry.record_tool_call(tool_name="bash", latency_sec=0.2, success=True)
        telemetry.record_tool_call(tool_name="bash", latency_sec=0.4, success=False)
        telemetry.record_stream_queue_depth(6)
        telemetry.record_stream_flush(event_count=12, latency_sec=0.01)
        telemetry.record_run_end("error")

        snapshot = telemetry.snapshot()
        assert snapshot["session_id"] == "s1"
        assert snapshot["runs_total"] == 1
        assert snapshot["runs_error"] == 1
        assert snapshot["llm_calls_total"] == 2
        assert snapshot["llm_calls_error"] == 1
        assert snapshot["tool_calls_total"] == 2
        assert snapshot["tool_calls_error"] == 1
        assert snapshot["stream_event_total"] == 12
        assert snapshot["stream_queue_depth"] == 6
        assert snapshot["llm_calls_by_provider_model"]["openai:gpt-4o"] == 2
        assert snapshot["tool_calls_by_name"]["bash"] == 2
