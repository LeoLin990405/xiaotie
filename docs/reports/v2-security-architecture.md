# Xiaotie v2.0 Security Architecture

**Date**: 2026-03-06
**Author**: security-agent
**Status**: Proposal
**References**:
- [Security Audit v2](security-audit-v2.md) -- 19 findings from v1.1.0
- [Competitor Analysis](competitor-analysis.md) -- Claude Code, Gemini CLI, Codex CLI sandboxing models

---

## 1. Design Principles

1. **Deny-by-default**: No tool runs without explicit policy or user approval.
2. **Defense in depth**: OS sandbox + application-level checks + permission gates.
3. **Least privilege**: Each tool gets only the capabilities it needs.
4. **Audit everything**: Every tool call is logged immutably.
5. **Fail closed**: If a security check fails or errors, deny the action.
6. **Zero trust plugins**: MCP servers and external tools are untrusted by default.

---

## 2. OS-Level Sandbox

### 2.1 Architecture Overview

```
User Input
    |
    v
+-------------------+
| Agent Orchestrator |  (unsandboxed - controls flow)
+-------------------+
    |
    v
+-------------------+     +-------------------+
| Permission Gate   | --> | Audit Logger      |
+-------------------+     +-------------------+
    |
    v
+-------------------+
| Sandbox Wrapper   |  (selects OS-appropriate sandbox)
+-------------------+
    |
    +-------+-------+
    |               |
    v               v
+--------+   +-----------+
| macOS  |   | Linux     |
| Seatbelt|   | landlock  |
+--------+   | + seccomp  |
             +-----------+
    |               |
    v               v
+-------------------+
| Tool Subprocess   |  (sandboxed)
+-------------------+
```

### 2.2 macOS: Seatbelt (sandbox-exec)

Seatbelt is macOS's built-in mandatory access control. Claude Code and Gemini CLI both use it. It adds <15ms overhead per invocation.

**Implementation**: Generate a `.sb` profile dynamically based on tool requirements.

```python
# xiaotie/sandbox/seatbelt.py

import subprocess
import tempfile
from pathlib import Path

# Base profile: deny everything, then allow specific operations
SEATBELT_BASE = """
(version 1)
(deny default)

;; Allow basic process operations
(allow process-exec)
(allow process-fork)
(allow signal (target self))
(allow sysctl-read)

;; Allow reading system libraries and frameworks
(allow file-read*
    (subpath "/usr/lib")
    (subpath "/usr/share")
    (subpath "/System")
    (subpath "/Library/Frameworks")
    (subpath "/Applications/Xcode.app/Contents/Developer")  ;; dev tools
    (subpath "/private/var/db/dyld")
)

;; Allow temp file access
(allow file-read* file-write*
    (subpath "/private/tmp")
    (subpath "/private/var/folders")
    (regex #"^/tmp/")
)

;; Allow reading Python and common interpreters
(allow file-read*
    (subpath "/usr/local")
    (subpath "/opt/homebrew")
)

;; Deny network by default (override per-tool)
(deny network*)
"""

SEATBELT_WORKSPACE_READ = """
;; Allow reading workspace
(allow file-read* (subpath "{workspace}"))
"""

SEATBELT_WORKSPACE_WRITE = """
;; Allow writing to workspace
(allow file-read* file-write* (subpath "{workspace}"))
"""

SEATBELT_NETWORK = """
;; Allow outbound network
(allow network-outbound)
(allow system-socket)
"""


def build_seatbelt_profile(
    workspace: str,
    allow_write: bool = False,
    allow_network: bool = False,
    extra_read_paths: list[str] | None = None,
) -> str:
    """Build a Seatbelt profile for a tool execution."""
    profile = SEATBELT_BASE

    if allow_write:
        profile += SEATBELT_WORKSPACE_WRITE.format(workspace=workspace)
    else:
        profile += SEATBELT_WORKSPACE_READ.format(workspace=workspace)

    if allow_network:
        profile += SEATBELT_NETWORK

    for path in (extra_read_paths or []):
        profile += f'\n(allow file-read* (subpath "{path}"))\n'

    return profile


async def execute_sandboxed_macos(
    command: list[str],
    workspace: str,
    allow_write: bool = False,
    allow_network: bool = False,
    timeout: float = 120,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Execute a command inside a macOS Seatbelt sandbox."""
    profile = build_seatbelt_profile(workspace, allow_write, allow_network)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sb", delete=False
    ) as f:
        f.write(profile)
        profile_path = f.name

    try:
        full_cmd = ["sandbox-exec", "-f", profile_path] + command
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=workspace,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return proc.returncode, stdout.decode(), stderr.decode()
    finally:
        Path(profile_path).unlink(missing_ok=True)
```

### 2.3 Linux: Landlock + Seccomp

Landlock (kernel 5.13+) provides filesystem access control without root. Seccomp-BPF restricts system calls.

```python
# xiaotie/sandbox/landlock.py

import ctypes
import os
from pathlib import Path

# Landlock access rights
LANDLOCK_ACCESS_FS_READ = 0x1 | 0x2 | 0x4 | 0x8   # read file/dir/link/attr
LANDLOCK_ACCESS_FS_WRITE = 0x10 | 0x20 | 0x40       # write/remove/make

def apply_landlock(
    read_paths: list[str],
    write_paths: list[str],
) -> bool:
    """Apply Landlock restrictions to the current process.

    Must be called BEFORE executing the tool (e.g., in preexec_fn).
    Returns True if landlock was applied, False if unsupported.
    """
    try:
        # Load libc for landlock syscalls
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        # ... landlock_create_ruleset, landlock_add_rule, landlock_restrict_self
        # (Full implementation uses raw syscalls via ctypes)
        return True
    except OSError:
        return False


async def execute_sandboxed_linux(
    command: list[str],
    workspace: str,
    allow_write: bool = False,
    allow_network: bool = False,
    timeout: float = 120,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Execute in a Linux sandbox using bubblewrap (bwrap) as the outer layer."""
    bwrap_cmd = [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/sbin", "/sbin",
        "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
        "--tmpfs", "/tmp",
        "--proc", "/proc",
        "--dev", "/dev",
        "--die-with-parent",
        "--new-session",
    ]

    if allow_write:
        bwrap_cmd += ["--bind", workspace, workspace]
    else:
        bwrap_cmd += ["--ro-bind", workspace, workspace]

    if not allow_network:
        bwrap_cmd += ["--unshare-net"]

    bwrap_cmd += ["--unshare-pid", "--unshare-ipc"]
    bwrap_cmd += command

    proc = await asyncio.create_subprocess_exec(
        *bwrap_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(), timeout=timeout
    )
    return proc.returncode, stdout.decode(), stderr.decode()
```

### 2.4 Unified Sandbox Interface

```python
# xiaotie/sandbox/wrapper.py

import platform
from dataclasses import dataclass
from enum import Enum


class SandboxCapability(Enum):
    """Capabilities that a tool can request."""
    FS_READ_WORKSPACE = "fs_read_workspace"
    FS_WRITE_WORKSPACE = "fs_write_workspace"
    NETWORK_OUTBOUND = "network_outbound"
    SUBPROCESS = "subprocess"
    # Dangerous - require explicit approval
    FS_READ_SYSTEM = "fs_read_system"
    FS_WRITE_SYSTEM = "fs_write_system"


@dataclass
class SandboxPolicy:
    """Policy for a sandboxed execution."""
    capabilities: set[SandboxCapability]
    workspace: str
    timeout: float = 120.0
    memory_limit_mb: int = 512
    extra_read_paths: list[str] | None = None


# Tool -> required capabilities mapping
TOOL_CAPABILITIES: dict[str, set[SandboxCapability]] = {
    "read_file": {SandboxCapability.FS_READ_WORKSPACE},
    "write_file": {SandboxCapability.FS_READ_WORKSPACE, SandboxCapability.FS_WRITE_WORKSPACE},
    "edit_file": {SandboxCapability.FS_READ_WORKSPACE, SandboxCapability.FS_WRITE_WORKSPACE},
    "bash": {SandboxCapability.FS_READ_WORKSPACE, SandboxCapability.FS_WRITE_WORKSPACE, SandboxCapability.SUBPROCESS},
    "python": {SandboxCapability.FS_READ_WORKSPACE, SandboxCapability.SUBPROCESS},
    "web_search": {SandboxCapability.NETWORK_OUTBOUND},
    "web_fetch": {SandboxCapability.NETWORK_OUTBOUND},
    "git": {SandboxCapability.FS_READ_WORKSPACE, SandboxCapability.FS_WRITE_WORKSPACE, SandboxCapability.NETWORK_OUTBOUND},
}


async def execute_sandboxed(
    command: list[str],
    policy: SandboxPolicy,
) -> tuple[int, str, str]:
    """Execute a command with OS-appropriate sandboxing."""
    system = platform.system()
    allow_write = SandboxCapability.FS_WRITE_WORKSPACE in policy.capabilities
    allow_network = SandboxCapability.NETWORK_OUTBOUND in policy.capabilities

    if system == "Darwin":
        from .seatbelt import execute_sandboxed_macos
        return await execute_sandboxed_macos(
            command, policy.workspace, allow_write, allow_network,
            policy.timeout, extra_read_paths=policy.extra_read_paths,
        )
    elif system == "Linux":
        from .landlock import execute_sandboxed_linux
        return await execute_sandboxed_linux(
            command, policy.workspace, allow_write, allow_network,
            policy.timeout,
        )
    else:
        # Fallback: subprocess with resource limits only (current v1 behavior)
        from .subprocess_fallback import execute_with_limits
        return await execute_with_limits(command, policy)
```

---

## 3. Permission Model

### 3.1 Four Permission Modes

Inspired by Claude Code's model, with enhancements:

| Mode | Description | Behavior |
|------|-------------|----------|
| **Locked** | Maximum restriction | Only read-only tools. No writes, no commands. |
| **Supervised** | Human-in-the-loop (default) | Read auto-approved. Writes/commands require approval. Dangerous ops require double-confirm. |
| **Permissive** | Trust workspace ops | Workspace read/write auto-approved. System-level and network require approval. |
| **YOLO** | Full trust (dev-only) | Everything auto-approved except critical blocklist. Logged with warnings. |

### 3.2 Permission Decision Flow

```
Tool Call Request
    |
    v
[1. Deny Rules] -----> DENY (always wins, cannot be overridden)
    |
    v
[2. OS Sandbox Check] --> Is sandbox available?
    |                       |
    | (yes)                 | (no)
    v                       v
[3. Capability Check] --> Escalate to higher approval level
    |
    v
[4. Mode-based Decision]
    |
    +--[Locked]-------> Only allow FS_READ_WORKSPACE
    +--[Supervised]---> auto-approve LOW risk, prompt MEDIUM/HIGH
    +--[Permissive]--> auto-approve LOW+MEDIUM, prompt HIGH
    +--[YOLO]---------> auto-approve all (log warning)
    |
    v
[5. User Prompt] (if needed)
    |
    +--[Allow Once]--------> Execute
    +--[Allow Session]-----> Add to session allowlist, Execute
    +--[Allow Permanent]---> Add to config allowlist, Execute
    +--[Deny]--------------> Block
    |
    v
[6. Audit Log Entry]
```

### 3.3 Deny Rules (Highest Priority)

Deny rules cannot be overridden by any permission mode. They are hardcoded and configurable:

```yaml
# ~/.xiaotie/security.yaml
deny_rules:
  # Patterns that are ALWAYS blocked, regardless of mode
  commands:
    - "rm -rf /"
    - "mkfs"
    - "dd if=/dev/zero"
    - "> /dev/sd*"
    - "curl * | *sh"
    - "chmod 777"
  paths:
    write:
      - "/etc/**"
      - "/usr/**"
      - "/System/**"
      - "~/.ssh/**"
      - "~/.gnupg/**"
    read:
      - "~/.ssh/id_*"         # Private keys
      - "**/.env"             # Environment files (except workspace)
      - "**/credentials*"
```

### 3.4 Risk Classification v2

```python
class RiskLevel(Enum):
    NONE = "none"       # No-op or informational
    LOW = "low"         # Read-only within workspace
    MEDIUM = "medium"   # Write within workspace, or read outside
    HIGH = "high"       # Shell execution, network access
    CRITICAL = "critical"  # System modification, privilege escalation

# Tool risk matrix (base risk before argument analysis)
TOOL_RISK_MAP = {
    "read_file": RiskLevel.LOW,
    "calculator": RiskLevel.NONE,
    "web_search": RiskLevel.MEDIUM,
    "web_fetch": RiskLevel.MEDIUM,
    "code_analysis": RiskLevel.LOW,
    "write_file": RiskLevel.MEDIUM,
    "edit_file": RiskLevel.MEDIUM,
    "python": RiskLevel.HIGH,
    "bash": RiskLevel.HIGH,
    "enhanced_bash": RiskLevel.HIGH,
    "git": RiskLevel.MEDIUM,        # read ops
    "git_push": RiskLevel.HIGH,     # remote mutation
    "mcp_*": RiskLevel.HIGH,        # external plugins
}
```

---

## 4. Secret Management

### 4.1 Current State (v1.1.0)

- API keys stored in plaintext YAML (`config/config.yaml`)
- Keys loaded via `os.environ` fallback
- No encryption, no keyring, no rotation support

### 4.2 v2.0 Secret Architecture

```
Priority order for secret resolution:
1. System keyring (macOS Keychain / Linux Secret Service)
2. Environment variables
3. Encrypted config file (~/.xiaotie/secrets.enc)
4. Plaintext config (DEPRECATED, emit warning)
```

```python
# xiaotie/secrets.py

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SecretManager:
    """Layered secret resolution with keyring priority."""

    def __init__(self, service_name: str = "xiaotie"):
        self.service_name = service_name
        self._keyring = self._init_keyring()

    def _init_keyring(self):
        try:
            import keyring
            # Verify keyring backend is usable
            keyring.get_keyring()
            return keyring
        except Exception:
            return None

    def get(self, key: str) -> Optional[str]:
        """Resolve a secret by key name.

        Resolution order:
        1. System keyring
        2. Environment variable (XIAOTIE_{KEY})
        3. None
        """
        # 1. Keyring
        if self._keyring:
            try:
                value = self._keyring.get_password(self.service_name, key)
                if value:
                    return value
            except Exception:
                pass

        # 2. Environment variable
        env_key = f"XIAOTIE_{key.upper()}"
        value = os.environ.get(env_key)
        if value:
            return value

        # Also check common env var names
        common_names = {
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "zhipu_api_key": "ZHIPU_API_KEY",
        }
        if key.lower() in common_names:
            value = os.environ.get(common_names[key.lower()])
            if value:
                return value

        return None

    def set(self, key: str, value: str) -> bool:
        """Store a secret in the system keyring."""
        if not self._keyring:
            logger.warning("No keyring backend available. Secret not stored.")
            return False
        try:
            self._keyring.set_password(self.service_name, key, value)
            return True
        except Exception as e:
            logger.error("Failed to store secret: %s", e)
            return False

    def delete(self, key: str) -> bool:
        """Remove a secret from the keyring."""
        if not self._keyring:
            return False
        try:
            self._keyring.delete_password(self.service_name, key)
            return True
        except Exception:
            return False
```

### 4.3 Config Migration

```yaml
# OLD (v1.x) - DEPRECATED, emits warning
api_key: sk-abc123

# NEW (v2.0) - references secret manager
llm:
  api_key: "${secret:anthropic_api_key}"   # resolved via SecretManager
  # OR
  api_key: "${env:ANTHROPIC_API_KEY}"      # explicit env var
```

### 4.4 CLI Commands

```bash
xiaotie secret set anthropic_api_key    # Prompts for value, stores in keyring
xiaotie secret get anthropic_api_key    # Shows masked value
xiaotie secret list                     # Lists stored keys (not values)
xiaotie secret delete anthropic_api_key
xiaotie secret migrate                  # Migrates plaintext config to keyring
```

---

## 5. MCP Plugin Security (Tool Signing and Verification)

### 5.1 Threat Model

MCP servers are external processes that run with the user's full permissions. A malicious or compromised MCP server can:
- Execute arbitrary code
- Exfiltrate data via network
- Modify files outside the workspace
- Harvest secrets from the environment

### 5.2 Defense Layers

```
MCP Server Request
    |
    v
[1. Registry Check] --> Is server in trusted registry?
    |                    (npmjs.com/@modelcontextprotocol/*)
    |
    v
[2. Hash Verification] --> Does binary/package hash match known-good?
    |                       (stored in ~/.xiaotie/mcp-hashes.json)
    |
    v
[3. Capability Declaration] --> What capabilities does it claim?
    |                            (fs_read, fs_write, network, exec)
    |
    v
[4. Sandbox Enforcement] --> Run in OS sandbox with ONLY declared capabilities
    |
    v
[5. Runtime Monitoring] --> Audit all tool calls, rate limit, size limit
```

### 5.3 MCP Server Policy Configuration

```yaml
# ~/.xiaotie/mcp-policy.yaml
mcp:
  default_policy: sandboxed  # sandboxed | permissive | blocked

  trusted_registries:
    - "npmjs.com/@modelcontextprotocol/*"
    - "github.com/anthropics/*"

  servers:
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
      capabilities: [fs_read, fs_write]
      sandbox: true
      allowed_paths: ["/workspace"]
      # SHA-256 hash of package for integrity verification
      hash: "sha256:abc123..."

    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      capabilities: [network]
      sandbox: true
      env_secrets: ["github_token"]  # resolved via SecretManager
      rate_limit: 60/min

    untrusted_plugin:
      command: /path/to/plugin
      capabilities: []  # no capabilities until reviewed
      sandbox: true
      blocked: true      # must be explicitly unblocked
```

### 5.4 Runtime Monitoring

```python
class MCPMonitor:
    """Monitor MCP server behavior at runtime."""

    def __init__(self, server_name: str, policy: MCPServerPolicy):
        self.server_name = server_name
        self.policy = policy
        self.call_count = 0
        self.bytes_transferred = 0
        self._rate_limiter = TokenBucket(policy.rate_limit)

    def check_tool_call(self, tool_name: str, arguments: dict) -> bool:
        """Check if a tool call from this MCP server is allowed."""
        # Rate limiting
        if not self._rate_limiter.consume():
            logger.warning("MCP %s rate limited", self.server_name)
            return False

        # Capability check
        required_caps = infer_capabilities(tool_name, arguments)
        if not required_caps.issubset(self.policy.capabilities):
            logger.warning(
                "MCP %s requested capability %s not in policy",
                self.server_name, required_caps - self.policy.capabilities
            )
            return False

        self.call_count += 1
        return True
```

---

## 6. Audit Logging

### 6.1 What Gets Logged

Every security-relevant event is logged to an append-only audit log:

| Event Type | Data Captured |
|------------|--------------|
| `tool_call` | tool name, arguments (redacted secrets), risk level, decision, user, timestamp |
| `permission_decision` | tool, risk, approved/denied, reason, mode |
| `sandbox_violation` | tool, attempted access, blocked resource |
| `secret_access` | key name (not value), source (keyring/env), accessor |
| `mcp_call` | server name, tool, arguments, response size |
| `config_change` | field changed, old hash, new hash |
| `session_start/end` | session ID, duration, tool call count |

### 6.2 Storage Format

```python
# xiaotie/audit.py

import json
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AuditEntry:
    timestamp: float
    event_type: str
    session_id: str
    tool_name: str | None = None
    risk_level: str | None = None
    decision: str | None = None  # "approved" | "denied" | "auto_approved"
    reason: str | None = None
    details: dict | None = None
    # Chain hash for tamper detection
    prev_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self, prev_hash: str) -> str:
        self.prev_hash = prev_hash
        content = json.dumps(asdict(self), sort_keys=True, default=str)
        self.entry_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.entry_hash


class AuditLog:
    """Append-only, hash-chained audit log."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or (Path.home() / ".xiaotie" / "audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_file = self._get_log_file()
        self._last_hash = self._read_last_hash()

    def _get_log_file(self) -> Path:
        date_str = time.strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{date_str}.jsonl"

    def _read_last_hash(self) -> str:
        if self._current_file.exists():
            lines = self._current_file.read_text().strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                return last.get("entry_hash", "")
        return "genesis"

    def log(self, entry: AuditEntry) -> None:
        entry.compute_hash(self._last_hash)
        self._last_hash = entry.entry_hash
        with open(self._current_file, "a") as f:
            f.write(json.dumps(asdict(entry), default=str) + "\n")

    def verify_integrity(self) -> tuple[bool, int]:
        """Verify the hash chain. Returns (valid, entry_count)."""
        prev_hash = "genesis"
        count = 0
        for log_file in sorted(self.log_dir.glob("audit-*.jsonl")):
            for line in log_file.read_text().strip().split("\n"):
                if not line:
                    continue
                entry = json.loads(line)
                expected = entry.get("entry_hash", "")
                entry["prev_hash"] = prev_hash
                entry["entry_hash"] = ""
                content = json.dumps(entry, sort_keys=True, default=str)
                computed = hashlib.sha256(content.encode()).hexdigest()
                if computed != expected:
                    return False, count
                prev_hash = expected
                count += 1
        return True, count
```

### 6.3 CLI Commands

```bash
xiaotie audit show                    # Show recent audit entries
xiaotie audit show --tool bash        # Filter by tool
xiaotie audit show --decision denied  # Show denied operations
xiaotie audit verify                  # Verify hash chain integrity
xiaotie audit export --format csv     # Export for external analysis
```

---

## 7. CI/CD Security Pipeline

### 7.1 Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.6
    hooks:
      - id: bandit
        args: ["-r", "xiaotie/", "-ll", "-q"]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
        args: ["--maxkb=500"]

  - repo: local
    hooks:
      - id: check-secrets
        name: Check for hardcoded secrets
        entry: python scripts/check_secrets.py
        language: python
        types: [python, yaml]
```

### 7.2 GitHub Actions CI

```yaml
# .github/workflows/security.yml
name: Security Checks

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Bandit SAST
        run: |
          pip install bandit
          bandit -r xiaotie/ -f json -o bandit-report.json -ll
          bandit -r xiaotie/ -ll  # also print to console

      - name: Upload Bandit Report
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: bandit-report.json

  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: pip-audit
        run: |
          pip install pip-audit
          pip-audit --requirement requirements.txt --format json --output pip-audit.json
          pip-audit --requirement requirements.txt

      - name: Safety check
        run: |
          pip install safety
          safety check --json --output safety-report.json || true

  sbom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate SBOM (CycloneDX)
        run: |
          pip install cyclonedx-bom
          cyclonedx-py requirements \
            --input-file requirements.txt \
            --output-format json \
            --output-file sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json

  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # full history for secret scanning

      - name: TruffleHog Secret Scan
        uses: trufflesecurity/trufflehog@main
        with:
          extra_args: --only-verified
```

### 7.3 SBOM Generation

Every release generates a Software Bill of Materials (SBOM) in CycloneDX format:

```bash
# scripts/generate-sbom.sh
#!/bin/bash
set -euo pipefail

VERSION=$(python -c "import xiaotie; print(xiaotie.__version__)")
DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cyclonedx-py requirements \
  --input-file requirements.txt \
  --output-format json \
  --output-file "sbom-${VERSION}.json"

echo "SBOM generated: sbom-${VERSION}.json"
echo "Components: $(jq '.components | length' sbom-${VERSION}.json)"
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (v2.0-alpha) -- 2 weeks

| Task | Files | Priority |
|------|-------|----------|
| SecretManager with keyring + env var | `xiaotie/secrets.py` | P0 |
| Config migration to use SecretManager | `xiaotie/config.py` | P0 |
| AuditLog with hash chain | `xiaotie/audit.py` | P0 |
| Wire audit logging into tool execution | `xiaotie/orchestrator.py` | P0 |
| Pre-commit hooks (bandit, secrets) | `.pre-commit-config.yaml` | P0 |

### Phase 2: OS Sandbox (v2.0-beta) -- 3 weeks

| Task | Files | Priority |
|------|-------|----------|
| Seatbelt wrapper (macOS) | `xiaotie/sandbox/seatbelt.py` | P1 |
| Landlock/bwrap wrapper (Linux) | `xiaotie/sandbox/landlock.py` | P1 |
| Unified sandbox interface | `xiaotie/sandbox/wrapper.py` | P1 |
| Wire sandbox into BashTool/PythonTool | `xiaotie/tools/bash_tool.py` | P1 |
| Sandbox capability declarations per tool | `xiaotie/sandbox/wrapper.py` | P1 |

### Phase 3: Permission Model (v2.0-beta) -- 2 weeks

| Task | Files | Priority |
|------|-------|----------|
| Four permission modes | `xiaotie/permissions.py` | P1 |
| Deny rules engine (hardcoded + config) | `xiaotie/permissions.py` | P1 |
| User prompt with session/permanent allow | `xiaotie/permissions.py` | P1 |
| CLI: `xiaotie config set permission-mode` | `xiaotie/cli.py` | P2 |
| Security config file (`~/.xiaotie/security.yaml`) | `xiaotie/config.py` | P2 |

### Phase 4: MCP Security (v2.0-rc) -- 2 weeks

| Task | Files | Priority |
|------|-------|----------|
| MCP server policy config | `xiaotie/mcp/policy.py` | P2 |
| MCP runtime monitor + rate limiter | `xiaotie/mcp/monitor.py` | P2 |
| MCP sandbox integration | `xiaotie/mcp/transport.py` | P2 |
| Hash verification for MCP packages | `xiaotie/mcp/verify.py` | P3 |

### Phase 5: CI/CD (v2.0-rc) -- 1 week

| Task | Files | Priority |
|------|-------|----------|
| GitHub Actions security workflow | `.github/workflows/security.yml` | P1 |
| SBOM generation script | `scripts/generate-sbom.sh` | P2 |
| Release checklist with security gates | `docs/release-checklist.md` | P2 |

---

## 9. Metrics and Success Criteria

| Metric | v1.1.0 (current) | v2.0 Target |
|--------|-------------------|-------------|
| Bandit findings (HIGH) | 6 | 0 |
| Bandit findings (MEDIUM) | 11 | 0 |
| Hardcoded secrets | 1 | 0 |
| Tools with sandbox | 0% | 100% (bash, python, mcp) |
| Permission gate coverage | ~60% | 100% |
| Audit log coverage | 0% | 100% of tool calls |
| SBOM generated per release | No | Yes |
| Pre-commit security hooks | 0 | 3 (bandit, secrets, large files) |
| Path traversal protection | 0 tools | All file tools |
| Dependency scan in CI | No | Yes (pip-audit + safety) |

---

*End of v2.0 Security Architecture*
