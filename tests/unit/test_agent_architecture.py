"""v3 Agent architecture primitives tests."""

from xiaotie.agent.architecture import (
    AgentCheckpoint,
    InMemoryCheckpointStore,
    MimoOnlyGuardrail,
    RuntimePhase,
)


def test_mimo_only_guardrail_allows_mimo():
    decision = MimoOnlyGuardrail.check("mimo")
    assert decision.allowed is True
    assert decision.data["provider"] == "mimo"


def test_mimo_only_guardrail_blocks_other_provider():
    decision = MimoOnlyGuardrail.check("openai")
    assert decision.allowed is False
    assert "MIMO" in decision.reason


def test_checkpoint_store_latest():
    store = InMemoryCheckpointStore()
    first = AgentCheckpoint(
        checkpoint_id="c1",
        session_id="s1",
        phase=RuntimePhase.THINKING,
        step=1,
        message_roles=["system", "user"],
    )
    second = AgentCheckpoint(
        checkpoint_id="c2",
        session_id="s1",
        phase=RuntimePhase.COMPLETED,
        step=1,
        message_roles=["system", "user", "assistant"],
    )

    store.save(first)
    store.save(second)

    assert store.latest("s1") == second
    assert store.list("s1") == [first, second]
