"""OS-level Sandbox Manager

Provides real OS-level isolation for tool execution:
- macOS: Seatbelt (sandbox-exec) with dynamic .sb profile generation
- Linux: bubblewrap (bwrap) with namespace + filesystem isolation
- Fallback: subprocess with rlimits (universal)

Usage:
    from xiaotie.sandbox_v2 import SandboxManager, Capability

    manager = SandboxManager(workspace="/path/to/workspace")
    exit_code, stdout, stderr = await manager.execute(
        command=["ls", "-la"],
        capabilities={Capability.READ_FS},
    )
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------


class Capability(Flag):
    """Capabilities that a sandboxed process can request."""

    NONE = 0
    READ_FS = auto()  # Read files within workspace
    WRITE_FS = auto()  # Write files within workspace
    NETWORK = auto()  # Outbound network access
    SUBPROCESS = auto()  # Spawn child processes
    DANGEROUS = auto()  # System-level ops (requires explicit approval)

    # Convenience combos
    READ_WRITE = READ_FS | WRITE_FS


# Pre-defined capability sets for built-in tools
TOOL_CAPABILITIES: dict[str, Capability] = {
    "read_file": Capability.READ_FS,
    "write_file": Capability.READ_FS | Capability.WRITE_FS,
    "edit_file": Capability.READ_FS | Capability.WRITE_FS,
    "bash": Capability.READ_FS | Capability.WRITE_FS | Capability.SUBPROCESS,
    "enhanced_bash": Capability.READ_FS | Capability.WRITE_FS | Capability.SUBPROCESS,
    "python": Capability.READ_FS | Capability.SUBPROCESS,
    "web_search": Capability.NETWORK,
    "web_fetch": Capability.NETWORK,
    "git": Capability.READ_FS | Capability.WRITE_FS | Capability.NETWORK,
    "calculator": Capability.NONE,
    "code_analysis": Capability.READ_FS,
}


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""

    exit_code: int
    stdout: str
    stderr: str
    backend: str  # which backend was used
    sandboxed: bool  # whether OS sandbox was actually applied

    @property
    def success(self) -> bool:
        return self.exit_code == 0


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class SandboxBackend(ABC):
    """Abstract base for OS-specific sandbox backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend can run on the current system."""
        ...

    @abstractmethod
    async def execute(
        self,
        command: list[str],
        workspace: str,
        capabilities: Capability,
        timeout: float,
        env: dict[str, str] | None,
        extra_read_paths: list[str] | None,
    ) -> SandboxResult:
        """Execute a command within the sandbox."""
        ...


# ---------------------------------------------------------------------------
# macOS Seatbelt backend
# ---------------------------------------------------------------------------

_SEATBELT_BASE = """\
(version 1)
;; Allow-default strategy: start permissive, selectively deny.
;; deny-default is too fragile on modern macOS (process/mach/ipc
;; requirements change across OS versions and cause SIGABRT).
(allow default)
"""

_SEATBELT_DENY_NETWORK = """
;; Block all network access
(deny network*)
"""

_SEATBELT_DENY_WORKSPACE_WRITE = """
;; Deny writing to workspace (read-only mode)
(deny file-write* (subpath "{workspace}"))
"""


class SeatbeltBackend(SandboxBackend):
    """macOS Seatbelt (sandbox-exec) backend."""

    @property
    def name(self) -> str:
        return "seatbelt"

    def is_available(self) -> bool:
        return platform.system() == "Darwin" and shutil.which("sandbox-exec") is not None

    def build_profile(
        self,
        workspace: str,
        capabilities: Capability,
        extra_read_paths: list[str] | None = None,
    ) -> str:
        """Generate a Seatbelt .sb profile from capabilities.

        Uses allow-default strategy with selective denials:
        - No NETWORK  -> deny network*
        - No WRITE_FS -> deny file-write* on workspace
        """
        profile = _SEATBELT_BASE

        # Block network unless explicitly allowed
        if Capability.NETWORK not in capabilities:
            profile += _SEATBELT_DENY_NETWORK

        # Block workspace writes unless WRITE_FS granted
        if Capability.WRITE_FS not in capabilities:
            profile += _SEATBELT_DENY_WORKSPACE_WRITE.format(workspace=workspace)

        return profile

    async def execute(
        self,
        command: list[str],
        workspace: str,
        capabilities: Capability,
        timeout: float,
        env: dict[str, str] | None,
        extra_read_paths: list[str] | None,
    ) -> SandboxResult:
        profile = self.build_profile(workspace, capabilities, extra_read_paths)

        # Write profile to temp file
        fd, profile_path = tempfile.mkstemp(suffix=".sb", prefix="xiaotie_sb_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(profile)

            full_cmd = ["sandbox-exec", "-f", profile_path] + command
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=workspace,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Timed out ({timeout}s)",
                    backend=self.name,
                    sandboxed=True,
                )

            return SandboxResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                backend=self.name,
                sandboxed=True,
            )
        finally:
            Path(profile_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Linux bubblewrap backend
# ---------------------------------------------------------------------------


class BubblewrapBackend(SandboxBackend):
    """Linux bubblewrap (bwrap) backend."""

    @property
    def name(self) -> str:
        return "bubblewrap"

    def is_available(self) -> bool:
        return platform.system() == "Linux" and shutil.which("bwrap") is not None

    def build_command(
        self,
        command: list[str],
        workspace: str,
        capabilities: Capability,
    ) -> list[str]:
        """Build bwrap command with appropriate isolation flags."""
        bwrap: list[str] = ["bwrap"]

        # System mounts (read-only)
        for sys_path in ("/usr", "/lib", "/lib64", "/bin", "/sbin"):
            if Path(sys_path).exists():
                bwrap += ["--ro-bind", sys_path, sys_path]

        # /etc (read-only, needed for resolv.conf etc)
        bwrap += ["--ro-bind", "/etc", "/etc"]

        # Proc/dev/tmp
        bwrap += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]

        # Workspace
        if Capability.WRITE_FS in capabilities:
            bwrap += ["--bind", workspace, workspace]
        elif Capability.READ_FS in capabilities:
            bwrap += ["--ro-bind", workspace, workspace]

        # Network isolation
        if Capability.NETWORK not in capabilities:
            bwrap += ["--unshare-net"]

        # PID/IPC isolation always
        bwrap += ["--unshare-pid", "--unshare-ipc", "--die-with-parent", "--new-session"]

        bwrap += command
        return bwrap

    async def execute(
        self,
        command: list[str],
        workspace: str,
        capabilities: Capability,
        timeout: float,
        env: dict[str, str] | None,
        extra_read_paths: list[str] | None,
    ) -> SandboxResult:
        full_cmd = self.build_command(command, workspace, capabilities)

        # Add extra read paths
        # Insert before the actual command (which is at the end)
        if extra_read_paths:
            insert_pos = len(full_cmd) - len(command)
            for path in extra_read_paths:
                full_cmd.insert(insert_pos, path)
                full_cmd.insert(insert_pos, path)
                full_cmd.insert(insert_pos, "--ro-bind")
                insert_pos += 3

        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Timed out ({timeout}s)",
                backend=self.name,
                sandboxed=True,
            )

        return SandboxResult(
            exit_code=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            backend=self.name,
            sandboxed=True,
        )


# ---------------------------------------------------------------------------
# Fallback backend (subprocess + rlimits)
# ---------------------------------------------------------------------------


class FallbackBackend(SandboxBackend):
    """Fallback backend using subprocess with resource limits.

    Provides no real OS-level isolation, but enforces memory/CPU limits
    via setrlimit on Unix. Always available.
    """

    @property
    def name(self) -> str:
        return "fallback"

    def is_available(self) -> bool:
        return True  # always available

    async def execute(
        self,
        command: list[str],
        workspace: str,
        capabilities: Capability,
        timeout: float,
        env: dict[str, str] | None,
        extra_read_paths: list[str] | None,
    ) -> SandboxResult:
        preexec = self._make_preexec() if platform.system() != "Windows" else None

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=workspace,
            preexec_fn=preexec,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr=f"Timed out ({timeout}s)",
                backend=self.name,
                sandboxed=False,
            )

        return SandboxResult(
            exit_code=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            backend=self.name,
            sandboxed=False,
        )

    @staticmethod
    def _make_preexec():
        """Create a preexec_fn that sets resource limits."""

        def _set_limits():
            import resource

            # Memory: 512 MB
            mem = 512 * 1024 * 1024
            try:
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            except (ValueError, resource.error):
                pass
            # CPU: 300 seconds
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
            except (ValueError, resource.error):
                pass

        return _set_limits


# ---------------------------------------------------------------------------
# SandboxManager
# ---------------------------------------------------------------------------


@dataclass
class SandboxManager:
    """Unified sandbox manager that auto-selects the best available backend.

    Args:
        workspace: The workspace directory that tools can access.
        enabled: If False, always use the fallback (no OS sandbox).
        preferred_backend: Force a specific backend name, or None for auto.
    """

    workspace: str
    enabled: bool = True
    preferred_backend: str | None = None
    _backends: list[SandboxBackend] = field(default_factory=list, repr=False)
    _selected: SandboxBackend | None = field(default=None, repr=False)

    def __post_init__(self):
        # Register backends in priority order
        self._backends = [
            SeatbeltBackend(),
            BubblewrapBackend(),
            FallbackBackend(),
        ]
        self._selected = self._select_backend()

    def _select_backend(self) -> SandboxBackend:
        """Select the best available backend."""
        if not self.enabled:
            return self._get_fallback()

        if self.preferred_backend:
            for b in self._backends:
                if b.name == self.preferred_backend and b.is_available():
                    return b
            logger.warning(
                "Preferred backend %r not available, falling back",
                self.preferred_backend,
            )

        for b in self._backends:
            if b.is_available():
                return b

        return self._get_fallback()

    def _get_fallback(self) -> SandboxBackend:
        for b in self._backends:
            if b.name == "fallback":
                return b
        return FallbackBackend()

    @property
    def backend_name(self) -> str:
        """Name of the currently selected backend."""
        return self._selected.name if self._selected else "none"

    @property
    def is_os_sandboxed(self) -> bool:
        """Whether real OS-level sandboxing is active."""
        return self._selected is not None and self._selected.name != "fallback"

    async def execute(
        self,
        command: list[str],
        capabilities: Capability = Capability.READ_FS,
        timeout: float = 120.0,
        env: dict[str, str] | None = None,
        extra_read_paths: list[str] | None = None,
    ) -> SandboxResult:
        """Execute a command within the sandbox.

        Args:
            command: Command and arguments as a list (NOT a shell string).
            capabilities: What the command is allowed to do.
            timeout: Maximum execution time in seconds.
            env: Environment variables (defaults to filtered os.environ).
            extra_read_paths: Additional paths to allow reading.

        Returns:
            SandboxResult with exit_code, stdout, stderr.
        """
        if Capability.DANGEROUS in capabilities:
            logger.warning("Executing with DANGEROUS capability: %s", command)

        if env is None:
            env = self._build_safe_env()

        workspace = str(Path(self.workspace).resolve())

        return await self._selected.execute(
            command=command,
            workspace=workspace,
            capabilities=capabilities,
            timeout=timeout,
            env=env,
            extra_read_paths=extra_read_paths,
        )

    async def execute_shell(
        self,
        shell_command: str,
        capabilities: Capability = Capability.READ_FS,
        timeout: float = 120.0,
        env: dict[str, str] | None = None,
        extra_read_paths: list[str] | None = None,
    ) -> SandboxResult:
        """Execute a shell command string within the sandbox.

        Wraps the command in /bin/bash -c "...".
        """
        return await self.execute(
            command=["/bin/bash", "-c", shell_command],
            capabilities=capabilities,
            timeout=timeout,
            env=env,
            extra_read_paths=extra_read_paths,
        )

    @staticmethod
    def _build_safe_env() -> dict[str, str]:
        """Build a filtered environment, stripping sensitive variables."""
        sensitive_prefixes = (
            "AWS_",
            "ANTHROPIC_API",
            "OPENAI_API",
            "GOOGLE_API",
            "GITHUB_TOKEN",
            "SSH_",
            "GPG_",
        )
        env = {}
        for key, value in os.environ.items():
            if any(key.startswith(p) for p in sensitive_prefixes):
                continue
            env[key] = value
        return env

    def get_capabilities_for_tool(self, tool_name: str) -> Capability:
        """Look up default capabilities for a known tool."""
        return TOOL_CAPABILITIES.get(tool_name, Capability.NONE)
