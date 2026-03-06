"""Tests for OS-level SandboxManager (sandbox_v2)."""

import asyncio
import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.sandbox_v2 import (
    BubblewrapBackend,
    Capability,
    FallbackBackend,
    SandboxManager,
    SandboxResult,
    SeatbeltBackend,
    TOOL_CAPABILITIES,
)


# ---------------------------------------------------------------------------
# Capability tests
# ---------------------------------------------------------------------------

class TestCapability:
    def test_flag_combinations(self):
        caps = Capability.READ_FS | Capability.WRITE_FS
        assert Capability.READ_FS in caps
        assert Capability.WRITE_FS in caps
        assert Capability.NETWORK not in caps

    def test_none(self):
        assert Capability.NONE.value == 0

    def test_dangerous_is_separate(self):
        caps = Capability.READ_FS | Capability.WRITE_FS
        assert Capability.DANGEROUS not in caps

    def test_read_write_alias(self):
        assert Capability.READ_WRITE == (Capability.READ_FS | Capability.WRITE_FS)


# ---------------------------------------------------------------------------
# TOOL_CAPABILITIES tests
# ---------------------------------------------------------------------------

class TestToolCapabilities:
    def test_read_file_is_read_only(self):
        assert TOOL_CAPABILITIES["read_file"] == Capability.READ_FS

    def test_bash_has_subprocess(self):
        caps = TOOL_CAPABILITIES["bash"]
        assert Capability.SUBPROCESS in caps
        assert Capability.READ_FS in caps
        assert Capability.WRITE_FS in caps

    def test_calculator_has_none(self):
        assert TOOL_CAPABILITIES["calculator"] == Capability.NONE

    def test_web_fetch_has_network(self):
        assert Capability.NETWORK in TOOL_CAPABILITIES["web_fetch"]


# ---------------------------------------------------------------------------
# SandboxResult tests
# ---------------------------------------------------------------------------

class TestSandboxResult:
    def test_success(self):
        r = SandboxResult(exit_code=0, stdout="ok", stderr="", backend="test", sandboxed=True)
        assert r.success is True

    def test_failure(self):
        r = SandboxResult(exit_code=1, stdout="", stderr="fail", backend="test", sandboxed=True)
        assert r.success is False


# ---------------------------------------------------------------------------
# SeatbeltBackend tests
# ---------------------------------------------------------------------------

class TestSeatbeltBackend:
    def test_availability_on_darwin(self):
        backend = SeatbeltBackend()
        if platform.system() == "Darwin":
            assert backend.is_available() is True
        else:
            assert backend.is_available() is False

    def test_name(self):
        assert SeatbeltBackend().name == "seatbelt"

    def test_profile_generation_read_only(self):
        backend = SeatbeltBackend()
        profile = backend.build_profile("/workspace", Capability.READ_FS)
        assert "(allow default)" in profile
        # Read-only: should deny writes to workspace and deny network
        assert '(deny file-write* (subpath "/workspace"))' in profile
        assert "(deny network*)" in profile

    def test_profile_generation_read_write(self):
        backend = SeatbeltBackend()
        profile = backend.build_profile("/workspace", Capability.READ_FS | Capability.WRITE_FS)
        # Write allowed: should NOT deny writes to workspace
        assert "(deny file-write*" not in profile
        # Still no network
        assert "(deny network*)" in profile

    def test_profile_generation_network(self):
        backend = SeatbeltBackend()
        profile = backend.build_profile("/workspace", Capability.NETWORK)
        # Network allowed: should NOT deny network
        assert "(deny network*)" not in profile

    def test_profile_generation_no_network(self):
        backend = SeatbeltBackend()
        profile = backend.build_profile(
            "/workspace", Capability.READ_FS | Capability.SUBPROCESS
        )
        assert "(deny network*)" in profile

    def test_profile_full_capabilities(self):
        backend = SeatbeltBackend()
        profile = backend.build_profile(
            "/workspace",
            Capability.READ_FS | Capability.WRITE_FS | Capability.NETWORK | Capability.SUBPROCESS,
        )
        # Everything allowed: no denials except base
        assert "(deny network*)" not in profile
        assert "(deny file-write*" not in profile

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_execute_simple_command(self, tmp_path):
        """Integration test: actually run sandbox-exec on macOS."""
        backend = SeatbeltBackend()
        result = await backend.execute(
            command=["/bin/echo", "hello sandbox"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert result.success
        assert "hello sandbox" in result.stdout
        assert result.sandboxed is True
        assert result.backend == "seatbelt"

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_sandbox_blocks_workspace_write(self, tmp_path):
        """Verify seatbelt blocks writing to workspace when READ_FS only."""
        backend = SeatbeltBackend()
        test_file = tmp_path / "should_not_exist.txt"
        result = await backend.execute(
            command=["/bin/bash", "-c", f"echo blocked > {test_file}"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS | Capability.SUBPROCESS,  # no WRITE_FS
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        # Write to workspace should be denied
        assert not result.success or not test_file.exists()
        assert result.backend == "seatbelt"
        assert result.sandboxed is True

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_sandbox_allows_workspace_write(self, tmp_path):
        """Verify seatbelt allows writing within workspace when WRITE_FS."""
        backend = SeatbeltBackend()
        test_file = tmp_path / "test_write.txt"
        result = await backend.execute(
            command=["/bin/bash", "-c", f"echo hello > {test_file}"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS | Capability.WRITE_FS | Capability.SUBPROCESS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert result.success
        assert test_file.read_text().strip() == "hello"

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_sandbox_blocks_network(self, tmp_path):
        """Verify seatbelt blocks network when NETWORK not in capabilities."""
        backend = SeatbeltBackend()
        result = await backend.execute(
            command=["/bin/bash", "-c", "curl -s --max-time 3 http://example.com"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS | Capability.SUBPROCESS,  # no NETWORK
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        # curl should fail because network is blocked
        assert not result.success

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_sandbox_python_execution(self, tmp_path):
        """Verify Python can run inside the sandbox."""
        backend = SeatbeltBackend()
        result = await backend.execute(
            command=["/usr/bin/python3", "-c", "print('sandbox python ok')"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS | Capability.SUBPROCESS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert result.success
        assert "sandbox python ok" in result.stdout

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_sandbox_read_workspace_file(self, tmp_path):
        """Verify sandbox can read files in workspace."""
        test_file = tmp_path / "readable.txt"
        test_file.write_text("content123")
        backend = SeatbeltBackend()
        result = await backend.execute(
            command=["/bin/cat", str(test_file)],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert result.success
        assert "content123" in result.stdout

    @pytest.mark.asyncio
    async def test_timeout(self, tmp_path):
        """Test that timeout works."""
        backend = SeatbeltBackend()
        if not backend.is_available():
            pytest.skip("seatbelt not available")
        result = await backend.execute(
            command=["/bin/sleep", "60"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=1.0,
            env=None,
            extra_read_paths=None,
        )
        assert not result.success
        assert "Timed out" in result.stderr


# ---------------------------------------------------------------------------
# BubblewrapBackend tests
# ---------------------------------------------------------------------------

class TestBubblewrapBackend:
    def test_name(self):
        assert BubblewrapBackend().name == "bubblewrap"

    def test_availability_on_linux_only(self):
        backend = BubblewrapBackend()
        if platform.system() != "Linux":
            assert backend.is_available() is False

    def test_build_command_read_only(self):
        backend = BubblewrapBackend()
        cmd = backend.build_command(
            ["/bin/ls"], "/workspace", Capability.READ_FS
        )
        assert cmd[0] == "bwrap"
        assert "--ro-bind" in cmd
        # Find workspace bind: --ro-bind /workspace /workspace
        ws_indices = [i for i, c in enumerate(cmd) if c == "/workspace"]
        assert len(ws_indices) >= 2  # src and dest
        # The flag before the workspace pair should be --ro-bind
        assert cmd[ws_indices[0] - 1] == "--ro-bind"

    def test_build_command_write(self):
        backend = BubblewrapBackend()
        cmd = backend.build_command(
            ["/bin/ls"], "/workspace", Capability.READ_FS | Capability.WRITE_FS
        )
        # workspace should be writable via --bind
        ws_indices = [i for i, c in enumerate(cmd) if c == "/workspace"]
        assert len(ws_indices) >= 2
        assert cmd[ws_indices[0] - 1] == "--bind"

    def test_build_command_no_network(self):
        backend = BubblewrapBackend()
        cmd = backend.build_command(
            ["/bin/ls"], "/workspace", Capability.READ_FS
        )
        assert "--unshare-net" in cmd

    def test_build_command_with_network(self):
        backend = BubblewrapBackend()
        cmd = backend.build_command(
            ["/bin/ls"], "/workspace", Capability.READ_FS | Capability.NETWORK
        )
        assert "--unshare-net" not in cmd

    def test_build_command_isolation_flags(self):
        backend = BubblewrapBackend()
        cmd = backend.build_command(
            ["/bin/ls"], "/workspace", Capability.READ_FS
        )
        assert "--unshare-pid" in cmd
        assert "--unshare-ipc" in cmd
        assert "--die-with-parent" in cmd
        assert "--new-session" in cmd


# ---------------------------------------------------------------------------
# FallbackBackend tests
# ---------------------------------------------------------------------------

class TestFallbackBackend:
    def test_always_available(self):
        assert FallbackBackend().is_available() is True

    def test_name(self):
        assert FallbackBackend().name == "fallback"

    @pytest.mark.asyncio
    async def test_execute_simple(self, tmp_path):
        backend = FallbackBackend()
        result = await backend.execute(
            command=["/bin/echo", "hello"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert result.success
        assert "hello" in result.stdout
        assert result.sandboxed is False
        assert result.backend == "fallback"

    @pytest.mark.asyncio
    async def test_timeout(self, tmp_path):
        backend = FallbackBackend()
        result = await backend.execute(
            command=["/bin/sleep", "60"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=1.0,
            env=None,
            extra_read_paths=None,
        )
        assert not result.success
        assert "Timed out" in result.stderr

    @pytest.mark.asyncio
    async def test_nonzero_exit(self, tmp_path):
        backend = FallbackBackend()
        result = await backend.execute(
            command=["/bin/bash", "-c", "exit 42"],
            workspace=str(tmp_path),
            capabilities=Capability.READ_FS,
            timeout=10.0,
            env=None,
            extra_read_paths=None,
        )
        assert not result.success
        assert result.exit_code == 42


# ---------------------------------------------------------------------------
# SandboxManager tests
# ---------------------------------------------------------------------------

class TestSandboxManager:
    def test_auto_select_backend(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        if platform.system() == "Darwin":
            assert mgr.backend_name == "seatbelt"
            assert mgr.is_os_sandboxed is True
        elif platform.system() == "Linux":
            # May be bubblewrap or fallback depending on bwrap availability
            assert mgr.backend_name in ("bubblewrap", "fallback")
        else:
            assert mgr.backend_name == "fallback"

    def test_disabled_uses_fallback(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path), enabled=False)
        assert mgr.backend_name == "fallback"
        assert mgr.is_os_sandboxed is False

    def test_preferred_backend(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path), preferred_backend="fallback")
        assert mgr.backend_name == "fallback"

    def test_invalid_preferred_falls_back(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path), preferred_backend="nonexistent")
        # Should fall back to best available
        assert mgr.backend_name in ("seatbelt", "bubblewrap", "fallback")

    def test_get_capabilities_for_tool(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        assert mgr.get_capabilities_for_tool("read_file") == Capability.READ_FS
        assert Capability.SUBPROCESS in mgr.get_capabilities_for_tool("bash")
        assert mgr.get_capabilities_for_tool("unknown_tool") == Capability.NONE

    @pytest.mark.asyncio
    async def test_execute(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        result = await mgr.execute(
            command=["/bin/echo", "test"],
            capabilities=Capability.READ_FS,
            timeout=10.0,
        )
        assert result.success
        assert "test" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_shell(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        result = await mgr.execute_shell(
            shell_command="echo hello world",
            capabilities=Capability.READ_FS | Capability.SUBPROCESS,
            timeout=10.0,
        )
        assert result.success
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_safe_env_strips_secrets(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        with patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "HOME": "/home/test",
            "ANTHROPIC_API_KEY": "secret123",
            "AWS_SECRET_ACCESS_KEY": "aws_secret",
            "NORMAL_VAR": "normal",
        }):
            env = mgr._build_safe_env()
            assert "PATH" in env
            assert "NORMAL_VAR" in env
            assert "ANTHROPIC_API_KEY" not in env
            assert "AWS_SECRET_ACCESS_KEY" not in env

    @pytest.mark.asyncio
    async def test_execute_with_workspace_write(self, tmp_path):
        mgr = SandboxManager(workspace=str(tmp_path))
        test_file = tmp_path / "sandbox_write_test.txt"
        result = await mgr.execute_shell(
            shell_command=f"echo sandbox_ok > {test_file}",
            capabilities=Capability.READ_FS | Capability.WRITE_FS | Capability.SUBPROCESS,
            timeout=10.0,
        )
        assert result.success
        assert test_file.exists()
        assert test_file.read_text().strip() == "sandbox_ok"

    @pytest.mark.asyncio
    async def test_fallback_execute(self, tmp_path):
        """Test with fallback backend explicitly."""
        mgr = SandboxManager(workspace=str(tmp_path), enabled=False)
        result = await mgr.execute(
            command=["/bin/echo", "fallback"],
            capabilities=Capability.READ_FS,
            timeout=10.0,
        )
        assert result.success
        assert result.sandboxed is False
        assert "fallback" in result.stdout


# ---------------------------------------------------------------------------
# BashTool sandbox integration tests
# ---------------------------------------------------------------------------

class TestBashToolSandboxIntegration:
    @pytest.mark.asyncio
    async def test_bash_tool_with_sandbox(self, tmp_path):
        from xiaotie.tools.bash_tool import BashTool

        mgr = SandboxManager(workspace=str(tmp_path))
        tool = BashTool(sandbox_manager=mgr)
        result = await tool.execute("echo sandbox_integration_test")
        assert result.success
        assert "sandbox_integration_test" in result.content

    @pytest.mark.asyncio
    async def test_bash_tool_without_sandbox(self):
        from xiaotie.tools.bash_tool import BashTool

        tool = BashTool()  # no sandbox
        result = await tool.execute("echo no_sandbox")
        assert result.success
        assert "no_sandbox" in result.content

    @pytest.mark.asyncio
    async def test_bash_tool_dangerous_still_blocked(self, tmp_path):
        from xiaotie.tools.bash_tool import BashTool

        mgr = SandboxManager(workspace=str(tmp_path))
        tool = BashTool(sandbox_manager=mgr)
        result = await tool.execute("sudo rm -rf /")
        assert not result.success
        assert "Blocked" in result.error
