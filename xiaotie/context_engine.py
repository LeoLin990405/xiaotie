"""ContextEngine - Token-budgeted context composition for LLM calls.

Assembles context from multiple sources (system prompt, repo map, memory,
conversation history) and trims to fit within a token budget using
priority-based allocation.

Usage:
    engine = ContextEngine()
    engine.set_budget(100_000)
    bundle = await engine.compose_context(
        query="implement auth",
        conversation=[Message(role="user", content="add login")],
        repo_map="src/auth.py: class AuthService ...",
        memory_chunks=[MemoryChunk(id="1", content="uses JWT")],
    )
    print(bundle.token_usage)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False

from .schema import Message


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class BlockPriority(IntEnum):
    """Priority levels for context blocks (higher = kept first when trimming)."""

    SYSTEM = 100
    CONVERSATION_RECENT = 80
    REPO_MAP = 60
    MEMORY = 50
    CONVERSATION_OLD = 40
    SKILLS = 30


@dataclass
class ContextBlock:
    """A single block of context to include in the LLM prompt."""

    priority: BlockPriority
    label: str
    content: str
    token_count: int = 0


@dataclass
class TokenBudget:
    """Tracks token allocation across context categories."""

    total: int = 100_000
    system: int = 0
    repo_map: int = 0
    memory: int = 0
    conversation: int = 0
    skills: int = 0

    @property
    def used(self) -> int:
        return self.system + self.repo_map + self.memory + self.conversation + self.skills

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used)


@dataclass
class ContextBundle:
    """Complete context package produced by compose_context."""

    blocks: List[ContextBlock] = field(default_factory=list)
    token_usage: TokenBudget = field(default_factory=TokenBudget)

    def to_messages(self, system_prompt: str) -> List[Message]:
        """Convert the bundle into a list of Messages suitable for the LLM.

        Merges non-conversation blocks into the system prompt and returns
        conversation blocks as separate messages.
        """
        # Gather non-conversation context to prepend to system prompt
        supplements: list[str] = []
        conversation_msgs: list[Message] = []

        for block in self.blocks:
            if block.priority in (
                BlockPriority.CONVERSATION_RECENT,
                BlockPriority.CONVERSATION_OLD,
            ):
                # Will be handled below
                continue
            if block.content.strip():
                supplements.append(f"[{block.label}]\n{block.content}")

        # Build augmented system prompt
        augmented_system = system_prompt
        if supplements:
            augmented_system += "\n\n" + "\n\n".join(supplements)

        messages = [Message(role="system", content=augmented_system)]

        # Add conversation blocks in original order (sorted by insertion)
        conv_blocks = [
            b
            for b in self.blocks
            if b.priority
            in (BlockPriority.CONVERSATION_RECENT, BlockPriority.CONVERSATION_OLD)
        ]
        for block in conv_blocks:
            # Convention: label encodes "role:..." for conversation blocks
            role, _, text = block.content.partition("|||")
            if role in ("user", "assistant", "tool"):
                messages.append(Message(role=role, content=text))
            else:
                messages.append(Message(role="user", content=block.content))

        return messages


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


class TokenCounter:
    """Counts tokens using tiktoken if available, else character estimation."""

    def __init__(self):
        self._encoding = None
        if _HAS_TIKTOKEN:
            try:
                self._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        # Fallback: ~4 chars per token for English/code, ~2 for CJK
        return len(text) // 3


# ---------------------------------------------------------------------------
# Allocation ratios
# ---------------------------------------------------------------------------

# Default budget allocation ratios (must sum to 1.0)
_DEFAULT_RATIOS = {
    "system": 0.10,
    "repo_map": 0.15,
    "memory": 0.15,
    "conversation": 0.50,
    "skills": 0.05,
    "reserve": 0.05,
}


# ---------------------------------------------------------------------------
# ContextEngine
# ---------------------------------------------------------------------------


class ContextEngine:
    """Composes context for LLM calls within a token budget.

    Combines system prompt, repo map, memory recall, conversation history,
    and skills metadata. Trims lowest-priority blocks when over budget.
    """

    def __init__(
        self,
        token_budget: int = 100_000,
        ratios: Optional[dict[str, float]] = None,
    ):
        self._budget = token_budget
        self._ratios = ratios or dict(_DEFAULT_RATIOS)
        self._counter = TokenCounter()

    def set_budget(self, max_tokens: int) -> None:
        """Set the total token budget."""
        self._budget = max(1, max_tokens)

    @property
    def budget(self) -> int:
        return self._budget

    async def compose_context(
        self,
        query: str,
        conversation: Optional[List[Message]] = None,
        repo_map: Optional[str] = None,
        memory_chunks: Optional[list] = None,
        system_prompt: Optional[str] = None,
        skills_metadata: Optional[str] = None,
    ) -> ContextBundle:
        """Compose a context bundle within the token budget.

        Args:
            query: The current user query (used for relevance context).
            conversation: Conversation message history.
            repo_map: Pre-built repo map string.
            memory_chunks: Memory chunks (MemoryChunk or objects with .content).
            system_prompt: System prompt text.
            skills_metadata: Skills/tools metadata string.

        Returns:
            ContextBundle with prioritized, budget-fitted blocks.
        """
        blocks: list[ContextBlock] = []
        budget = TokenBudget(total=self._budget)

        # Compute category budgets
        effective_budget = self._budget
        cat_budgets = {k: int(effective_budget * v) for k, v in self._ratios.items()}

        # 1. System prompt (highest priority, fixed)
        if system_prompt:
            sys_tokens = self._counter.count(system_prompt)
            blocks.append(
                ContextBlock(
                    priority=BlockPriority.SYSTEM,
                    label="System Prompt",
                    content=system_prompt,
                    token_count=sys_tokens,
                )
            )
            budget.system = sys_tokens

        # 2. Repo map
        if repo_map:
            repo_tokens = self._counter.count(repo_map)
            repo_limit = cat_budgets.get("repo_map", int(effective_budget * 0.15))
            trimmed_repo = self._trim_to_budget(repo_map, repo_limit)
            trimmed_tokens = self._counter.count(trimmed_repo)
            blocks.append(
                ContextBlock(
                    priority=BlockPriority.REPO_MAP,
                    label="Repo Map",
                    content=trimmed_repo,
                    token_count=trimmed_tokens,
                )
            )
            budget.repo_map = trimmed_tokens

        # 3. Memory
        if memory_chunks:
            mem_limit = cat_budgets.get("memory", int(effective_budget * 0.15))
            mem_content, mem_tokens = self._build_memory_context(
                memory_chunks, mem_limit
            )
            if mem_content:
                blocks.append(
                    ContextBlock(
                        priority=BlockPriority.MEMORY,
                        label="Memory",
                        content=mem_content,
                        token_count=mem_tokens,
                    )
                )
                budget.memory = mem_tokens

        # 4. Skills metadata
        if skills_metadata:
            skills_limit = cat_budgets.get("skills", int(effective_budget * 0.05))
            trimmed_skills = self._trim_to_budget(skills_metadata, skills_limit)
            skills_tokens = self._counter.count(trimmed_skills)
            blocks.append(
                ContextBlock(
                    priority=BlockPriority.SKILLS,
                    label="Skills",
                    content=trimmed_skills,
                    token_count=skills_tokens,
                )
            )
            budget.skills = skills_tokens

        # 5. Conversation history (split into recent and old)
        if conversation:
            conv_limit = cat_budgets.get(
                "conversation", int(effective_budget * 0.50)
            )
            conv_blocks, conv_tokens = self._build_conversation_blocks(
                conversation, conv_limit
            )
            blocks.extend(conv_blocks)
            budget.conversation = conv_tokens

        # 6. Trim if over budget
        blocks = self._fit_to_budget(blocks, self._budget)

        # Recalculate budget totals after trimming
        budget = self._recalculate_budget(blocks, self._budget)

        return ContextBundle(blocks=blocks, token_usage=budget)

    async def compact(
        self, conversation: List[Message], target_tokens: int
    ) -> List[Message]:
        """Compact conversation history to fit within target_tokens.

        Strategy: keep system message and last N messages verbatim,
        summarize older messages into a single condensed message.
        """
        if not conversation:
            return []

        total = sum(self._counter.count(str(m.content)) for m in conversation)
        if total <= target_tokens:
            return list(conversation)

        # Keep system message if present
        result: list[Message] = []
        start_idx = 0
        if conversation[0].role == "system":
            result.append(conversation[0])
            start_idx = 1

        remaining = conversation[start_idx:]
        if not remaining:
            return result

        # Binary search for how many recent messages we can keep
        keep_count = len(remaining)
        while keep_count > 1:
            recent = remaining[-keep_count:]
            tokens = sum(self._counter.count(str(m.content)) for m in recent)
            tokens += sum(self._counter.count(str(m.content)) for m in result)
            if tokens <= target_tokens:
                break
            keep_count -= 1

        # Summarize older messages
        old_messages = remaining[:-keep_count] if keep_count < len(remaining) else []
        if old_messages:
            summary_parts = []
            for m in old_messages:
                content_str = str(m.content)[:200]
                summary_parts.append(f"[{m.role}]: {content_str}")
            summary_text = "[Earlier conversation summary]\n" + "\n".join(
                summary_parts[-10:]
            )
            result.append(Message(role="assistant", content=summary_text))

        # Add recent messages
        result.extend(remaining[-keep_count:])
        return result

    def _build_memory_context(
        self, chunks: list, limit: int
    ) -> tuple[str, int]:
        """Build memory context string from chunks, fitting within limit."""
        parts: list[str] = []
        total_tokens = 0

        # Sort by importance if available
        sorted_chunks = sorted(
            chunks,
            key=lambda c: getattr(c, "importance", 0.5),
            reverse=True,
        )

        for chunk in sorted_chunks:
            content = getattr(chunk, "content", str(chunk))
            chunk_tokens = self._counter.count(content)
            if total_tokens + chunk_tokens > limit:
                # Try to fit a trimmed version
                remaining = limit - total_tokens
                if remaining > 20:
                    trimmed = self._trim_to_budget(content, remaining)
                    parts.append(trimmed)
                    total_tokens += self._counter.count(trimmed)
                break
            parts.append(content)
            total_tokens += chunk_tokens

        return "\n---\n".join(parts), total_tokens

    def _build_conversation_blocks(
        self, messages: List[Message], limit: int
    ) -> tuple[list[ContextBlock], int]:
        """Build conversation context blocks with recent/old split."""
        blocks: list[ContextBlock] = []
        total_tokens = 0

        # Skip system messages (handled separately)
        conv_msgs = [m for m in messages if m.role != "system"]

        if not conv_msgs:
            return blocks, 0

        # Split: last 6 messages are "recent", rest are "old"
        recent_boundary = max(0, len(conv_msgs) - 6)
        old_msgs = conv_msgs[:recent_boundary]
        recent_msgs = conv_msgs[recent_boundary:]

        # Add recent messages first (higher priority)
        for msg in recent_msgs:
            content_str = str(msg.content)
            # Encode role into content for later extraction
            encoded = f"{msg.role}|||{content_str}"
            tokens = self._counter.count(content_str)
            if total_tokens + tokens > limit:
                break
            blocks.append(
                ContextBlock(
                    priority=BlockPriority.CONVERSATION_RECENT,
                    label=f"conversation:{msg.role}",
                    content=encoded,
                    token_count=tokens,
                )
            )
            total_tokens += tokens

        # Add old messages (lower priority, may be trimmed)
        for msg in old_msgs:
            content_str = str(msg.content)
            encoded = f"{msg.role}|||{content_str}"
            tokens = self._counter.count(content_str)
            if total_tokens + tokens > limit:
                break
            blocks.append(
                ContextBlock(
                    priority=BlockPriority.CONVERSATION_OLD,
                    label=f"conversation:{msg.role}",
                    content=encoded,
                    token_count=tokens,
                )
            )
            total_tokens += tokens

        return blocks, total_tokens

    def _trim_to_budget(self, text: str, max_tokens: int) -> str:
        """Trim text to fit within a token budget."""
        tokens = self._counter.count(text)
        if tokens <= max_tokens:
            return text

        # Approximate: trim by character ratio
        ratio = max_tokens / max(tokens, 1)
        char_limit = int(len(text) * ratio * 0.95)  # 5% safety margin
        trimmed = text[:char_limit]

        # Try to end at a newline for cleaner output
        last_newline = trimmed.rfind("\n")
        if last_newline > char_limit * 0.8:
            trimmed = trimmed[:last_newline]

        return trimmed + "\n... (trimmed)"

    def _fit_to_budget(
        self, blocks: List[ContextBlock], budget: int
    ) -> List[ContextBlock]:
        """Remove lowest-priority blocks until total fits within budget."""
        total = sum(b.token_count for b in blocks)
        if total <= budget:
            return blocks

        # Sort by priority ascending (lowest first = removed first)
        sorted_blocks = sorted(blocks, key=lambda b: b.priority)

        to_remove: set[int] = set()
        for i, block in enumerate(sorted_blocks):
            if total <= budget:
                break
            total -= block.token_count
            to_remove.add(id(block))

        return [b for b in blocks if id(b) not in to_remove]

    def _recalculate_budget(
        self, blocks: List[ContextBlock], total_budget: int
    ) -> TokenBudget:
        """Recalculate budget totals from current blocks."""
        budget = TokenBudget(total=total_budget)
        for block in blocks:
            if block.priority == BlockPriority.SYSTEM:
                budget.system += block.token_count
            elif block.priority == BlockPriority.REPO_MAP:
                budget.repo_map += block.token_count
            elif block.priority == BlockPriority.MEMORY:
                budget.memory += block.token_count
            elif block.priority == BlockPriority.SKILLS:
                budget.skills += block.token_count
            elif block.priority in (
                BlockPriority.CONVERSATION_RECENT,
                BlockPriority.CONVERSATION_OLD,
            ):
                budget.conversation += block.token_count
        return budget
