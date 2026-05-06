"""v3 Agent architecture primitives.

The runtime keeps these objects lightweight and framework-neutral: MIMO is the
only model boundary, while tools, resources, checkpoints, guardrails and trace
events stay explicit enough to evolve toward MCP-style integrations.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimePhase(str, Enum):
    """Durable phases for a resumable agent run."""

    INPUT_GUARDRAIL = "input_guardrail"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AgentTraceEvent:
    """Structured event emitted around model, tool and guardrail work."""

    name: str
    phase: RuntimePhase
    session_id: str
    step: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AgentCheckpoint:
    """Serializable checkpoint snapshot for durable execution."""

    checkpoint_id: str
    session_id: str
    phase: RuntimePhase
    step: int
    message_roles: list[str]
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class GuardrailDecision:
    """Guardrail output compatible with input/output/tool boundaries."""

    allowed: bool
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class MimoOnlyGuardrail:
    """Blocks any non-MIMO model/provider boundary."""

    @staticmethod
    def check(provider: Any) -> GuardrailDecision:
        provider_name = getattr(provider, "value", str(provider)).lower()
        allowed = provider_name == "mimo"
        return GuardrailDecision(
            allowed=allowed,
            reason="" if allowed else "小铁 v3 只允许 MIMO provider",
            data={"provider": provider_name},
        )


class InMemoryCheckpointStore:
    """Small checkpoint store used by tests and local interactive runs."""

    def __init__(self):
        self._items: dict[str, list[AgentCheckpoint]] = {}

    def save(self, checkpoint: AgentCheckpoint) -> None:
        self._items.setdefault(checkpoint.session_id, []).append(checkpoint)

    def latest(self, session_id: str) -> AgentCheckpoint | None:
        items = self._items.get(session_id, [])
        return items[-1] if items else None

    def list(self, session_id: str) -> list[AgentCheckpoint]:
        return list(self._items.get(session_id, []))
