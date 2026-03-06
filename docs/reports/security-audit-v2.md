# Xiaotie v1.1.0 Security Audit Report

**Date**: 2026-03-06
**Auditor**: security-agent (automated + manual review)
**Scope**: Full codebase (`xiaotie/` directory), dependencies, configuration files
**Methodology**: Manual code review + Bandit SAST + OWASP Top 10 mapping

---

## Executive Summary

The Xiaotie AI Agent framework (v1.1.0) contains **5 Critical**, **6 High**, **5 Medium**, and **3 Low** severity findings. The most urgent issues are:

1. **Hardcoded API key** in committed config file (CRITICAL)
2. **No path traversal protection** in file tools (CRITICAL)
3. **Unrestricted shell command execution** via BashTool (CRITICAL)
4. **Unsafe pickle deserialization** from database (HIGH)
5. **SQL injection vectors** in QueryBuilder and memory module (HIGH)

The enhanced bash tool (`EnhancedBashTool`) includes injection detection but the basic `BashTool` has no protections. The sandbox import checker can be bypassed. The permission system defaults to auto-approving medium-risk operations.

---

## Risk Matrix

| Severity | Count | Exploitability | Impact |
|----------|-------|----------------|--------|
| CRITICAL | 5 | Easy | Full system compromise |
| HIGH | 6 | Moderate | Data breach / RCE |
| MEDIUM | 5 | Moderate | Limited compromise |
| LOW | 3 | Difficult | Information disclosure |

---

## Findings

### SEC-001: Hardcoded API Key in Configuration File
- **CVSS**: 9.1 (Critical)
- **CWE**: CWE-798 (Use of Hard-coded Credentials)
- **OWASP**: A07:2021 - Identification and Authentication Failures
- **File**: `config/config.yaml:5`

**Description**: The GLM API key `9816840d92eb4cb5aabdf86efa0b674d.YjD9TCHaenVABicH` is hardcoded in the configuration file, which is likely tracked in version control.

**Evidence**:
```yaml
api_key: 9816840d92eb4cb5aabdf86efa0b674d.YjD9TCHaenVABicH
```

**Impact**: Anyone with repository access can use this API key, incurring costs and potentially accessing associated resources.

**Remediation**:
1. Immediately rotate the compromised API key
2. Replace with environment variable reference: `api_key: ${ZHIPU_API_KEY}`
3. Add `config/config.yaml` to `.gitignore`, use `config/config.yaml.example` with placeholders
4. Run `git filter-branch` or BFG Repo-Cleaner to remove the key from git history

---

### SEC-002: No Path Traversal Protection in File Tools
- **CVSS**: 8.6 (Critical)
- **CWE**: CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)
- **OWASP**: A01:2021 - Broken Access Control
- **File**: `xiaotie/tools/file_tools.py:79-97` (ReadTool), `xiaotie/tools/file_tools.py:132-146` (WriteTool)

**Description**: `ReadTool` and `WriteTool` accept absolute paths and paths with `../` sequences without any validation that the resolved path stays within the workspace directory. An AI agent (or adversarial prompt) can read/write any file accessible to the process user.

**PoC**:
```python
# ReadTool can read /etc/passwd
await read_tool.execute(path="/etc/passwd")

# ReadTool path traversal
await read_tool.execute(path="../../etc/shadow")

# WriteTool can overwrite arbitrary files
await write_tool.execute(path="/etc/cron.d/backdoor", content="...")
```

**Affected Code** (`file_tools.py:79-84`):
```python
file_path = Path(path)
if not file_path.is_absolute():
    file_path = self.workspace_dir / file_path
# NO check that file_path is within workspace_dir!
```

**Remediation**:
```python
file_path = (self.workspace_dir / file_path).resolve()
if not str(file_path).startswith(str(self.workspace_dir.resolve())):
    return ToolResult(success=False, error="Access denied: path outside workspace")
```

---

### SEC-003: Unrestricted Shell Command Execution (BashTool)
- **CVSS**: 9.8 (Critical)
- **CWE**: CWE-78 (Improper Neutralization of Special Elements used in an OS Command)
- **OWASP**: A03:2021 - Injection
- **File**: `xiaotie/tools/bash_tool.py:47-92`

**Description**: `BashTool.execute()` passes user-supplied commands directly to `asyncio.create_subprocess_shell()` with zero filtering or validation. While the `EnhancedBashTool` has injection detection, the basic `BashTool` is a direct command execution sink. Both tools are registered and the basic one can be used if `EnhancedBashTool` is not explicitly chosen.

**Impact**: Full remote code execution as the process owner. An adversarial prompt injection through the LLM can execute arbitrary system commands.

**Evidence** (`bash_tool.py:63`):
```python
process = await asyncio.create_subprocess_shell(
    command,  # Raw user/LLM-supplied command
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

**Remediation**:
1. Remove `BashTool` entirely; only use `EnhancedBashTool`
2. Always enforce the injection check (do not allow `check_injection=False`)
3. Add a mandatory command allowlist for non-interactive mode
4. Run commands in a sandbox (Docker, firejail, macOS sandbox-exec)
5. Consider using `create_subprocess_exec` with parsed arguments instead of shell mode

---

### SEC-004: EnhancedBashTool Injection Filter Bypass
- **CVSS**: 7.5 (High)
- **CWE**: CWE-78 (OS Command Injection)
- **OWASP**: A03:2021 - Injection
- **File**: `xiaotie/tools/enhanced_bash.py:169-203`

**Description**: The injection detection in `check_injection()` is regex-based and can be bypassed with encoding tricks, newline injection, or patterns not covered:

1. `$'\x72\x6d' -rf /` - hex-encoded `rm` bypasses string matching
2. `python3 -c 'import subprocess; subprocess.run(["rm","-rf","/"])'` - only checks `import os`, not `subprocess`
3. `bash -c "$(echo cm0gLXJmIC8K | base64 -d)"` - the base64 pattern only catches `base64 ... | bash` but not this variant
4. Whitespace variations: `rm  -rf  /` vs `rm\t-rf\t/`
5. Variable expansion: `cmd=rm; $cmd -rf /`

**Remediation**:
1. Use an allowlist approach instead of a denylist
2. Parse commands with `shlex.split()` and validate the binary name
3. Block all shell metacharacters in arguments when possible
4. Run in a sandboxed environment as defense-in-depth

---

### SEC-005: Unsafe Pickle Deserialization
- **CVSS**: 8.1 (High)
- **CWE**: CWE-502 (Deserialization of Untrusted Data)
- **OWASP**: A08:2021 - Software and Data Integrity Failures
- **File**: `xiaotie/memory/core.py:282, 336`

**Description**: The memory module uses `pickle.loads()` to deserialize embedding data from the SQLite database. If an attacker can write to the database (via SQL injection, file access, or supply chain attack), they can execute arbitrary code through crafted pickle payloads.

**Evidence**:
```python
embedding = pickle.loads(row['embedding']) if row['embedding'] else None
```

**Remediation**:
1. Replace `pickle` with `json` or `numpy.frombuffer()` for embedding vectors
2. If pickle is required, use `restrictedpickle` or a custom `Unpickler` with a restricted allowlist
3. Store embeddings as JSON arrays or binary blobs with a known format

---

### SEC-006: SQL Injection in QueryBuilder and count()
- **CVSS**: 7.3 (High)
- **CWE**: CWE-89 (SQL Injection)
- **OWASP**: A03:2021 - Injection
- **Files**: `xiaotie/db_tool.py:388-408, 450-467`

**Description**: Multiple SQL injection vectors exist:

1. **`DatabaseTool.count()`** (line 394-399): The `where` parameter is validated by `SQLValidator` but then string-interpolated into the query. The validator only blocks certain keywords but doesn't prevent all injection, e.g. `1=1 UNION SELECT sqlite_version()` passes validation because it starts with a number, not a blocked keyword.

2. **`QueryBuilder.build()`** (line 450-466): Table name, column names, and ORDER BY clauses are directly interpolated into SQL without parameterization. While table name has regex validation in `get_columns()`, `QueryBuilder` has no such check.

**Evidence**:
```python
# db_tool.py:394 - table name interpolated
sql = f"SELECT COUNT(*) as cnt FROM {table}"
if where:
    sql += f" WHERE {where}"  # where clause interpolated

# db_tool.py:453 - columns and table interpolated
sql = f"SELECT {columns} FROM {self._table}"
```

**Remediation**:
1. Never interpolate table/column names directly; use a strict allowlist
2. Always use parameterized queries for WHERE clauses
3. Add input validation for all QueryBuilder inputs

---

### SEC-007: Sandbox Import Checker Bypass
- **CVSS**: 7.0 (High)
- **CWE**: CWE-693 (Protection Mechanism Failure)
- **OWASP**: A05:2021 - Security Misconfiguration
- **File**: `xiaotie/sandbox.py:138-186`

**Description**: The `ImportChecker` uses AST-based import detection, which can be bypassed:

1. `__builtins__.__import__('os')` - blocked in config but not by AST checker
2. `getattr(__builtins__, '__import__')('os')` - dynamic import via getattr
3. `exec("import os; os.system('id')")` - code inside eval/exec strings is not parsed
4. `importlib.import_module('os')` - importlib is not in the blocked list
5. `open('/etc/passwd').read()` - file access without importing os

The blocked imports list (`os.system`, `subprocess`, etc.) only blocks specific sub-modules, not the parent `os` module entirely. `os.popen`, `os.exec*`, `os.spawn*` are all accessible.

**Remediation**:
1. Block entire `os` module, not just `os.system`
2. Add `importlib`, `builtins`, `code`, `codeop`, `compile` to blocklist
3. Use `RestrictedPython` or run in Docker/gVisor for real isolation
4. Block `exec`, `eval`, `compile`, `open` builtins in the execution context

---

### SEC-008: Permission System Auto-Approves Medium Risk
- **CVSS**: 6.5 (High)
- **CWE**: CWE-862 (Missing Authorization)
- **OWASP**: A01:2021 - Broken Access Control
- **File**: `xiaotie/permissions.py:126-133`

**Description**: The `PermissionManager` defaults to `auto_approve_medium_risk=True`, meaning file writes (`write_file`, `edit_file`) and Python execution are approved without user confirmation. Combined with the path traversal in SEC-002, this allows silent arbitrary file writes.

**Evidence**:
```python
def __init__(
    self,
    auto_approve_low_risk: bool = True,
    auto_approve_medium_risk: bool = True,  # Dangerous default!
```

**Remediation**:
1. Change default to `auto_approve_medium_risk=False`
2. Require explicit opt-in for auto-approving writes
3. Log all auto-approved actions for audit

---

### SEC-009: Weak MD5 Hash Usage
- **CVSS**: 4.3 (Medium)
- **CWE**: CWE-327 (Use of a Broken or Risky Cryptographic Algorithm)
- **OWASP**: A02:2021 - Cryptographic Failures
- **Files**: `xiaotie/cache.py:146`, `xiaotie/config_watcher.py:54`, `xiaotie/knowledge_base.py:44,128`, `xiaotie/scraper/auth.py:94`, `xiaotie/search/semantic_search.py:274`

**Description**: MD5 is used in 6 locations for cache keys, content hashing, and API signature generation. While MD5 for cache keys is low risk, using it for authentication signatures (`scraper/auth.py`) is problematic as MD5 collisions are practical.

**Remediation**:
1. Replace `hashlib.md5` with `hashlib.sha256` across the codebase
2. For cache keys, add `usedforsecurity=False` parameter (Python 3.9+)
3. For auth signatures, use HMAC-SHA256 instead of plain MD5

---

### SEC-010: Binding to All Interfaces (0.0.0.0)
- **CVSS**: 5.3 (Medium)
- **CWE**: CWE-605 (Multiple Binds to Same Port)
- **OWASP**: A05:2021 - Security Misconfiguration
- **Files**: `xiaotie/config.py:91`, `xiaotie/proxy/proxy_server.py:65`, `xiaotie/cli.py:61`

**Description**: The proxy server, Telegram webhook server, and Prometheus metrics endpoint all default to binding on `0.0.0.0`, exposing them to all network interfaces. In shared or cloud environments, this exposes internal services.

**Remediation**:
1. Default to `127.0.0.1` for all services
2. Require explicit configuration to bind to external interfaces
3. Add network access documentation and warnings

---

### SEC-011: SSRF Protection Incomplete (DNS Rebinding)
- **CVSS**: 5.9 (Medium)
- **CWE**: CWE-918 (Server-Side Request Forgery)
- **OWASP**: A10:2021 - Server-Side Request Forgery
- **File**: `xiaotie/tools/web_tool.py:161-175, 196-218`

**Description**: `WebFetchTool` has SSRF protections including private IP blocking and redirect checking. However, it is vulnerable to DNS rebinding attacks: the DNS resolution check (`_is_private_ip`) and the actual HTTP request are separate operations. An attacker can use a DNS rebinding service where the first resolution returns a public IP (passing the check) and the second returns a private IP (during the actual connection).

The redirect check (line 213-214) only verifies the URL hostname, not the actual connected IP address, so it doesn't fully mitigate TOCTOU DNS rebinding.

**Remediation**:
1. Use a custom DNS resolver that pins the IP from validation
2. Or use `socket.create_connection` with the resolved IP directly
3. Consider using a library like `ssrf-king` or `defused-urllib` for comprehensive protection

---

### SEC-012: Memory Module SQL Injection via Tags
- **CVSS**: 5.5 (Medium)
- **CWE**: CWE-89 (SQL Injection)
- **OWASP**: A03:2021 - Injection
- **File**: `xiaotie/memory/core.py:316-332`

**Description**: The `search_by_tags()` method constructs SQL with LIKE clauses using user-provided tags. While the values are parameterized, the LIKE pattern uses `%{tag}%` which allows LIKE injection (e.g., `%` as a tag matches everything). More critically, the `query` parameter in `retrieve()` (line 278) is also used in a LIKE pattern without escaping LIKE metacharacters (`%`, `_`).

**Remediation**:
1. Escape LIKE metacharacters in tag/query values
2. Use `ESCAPE` clause: `WHERE tags LIKE ? ESCAPE '\'`

---

### SEC-013: Insecure Temporary File Usage
- **CVSS**: 3.7 (Low)
- **CWE**: CWE-377 (Insecure Temporary File)
- **OWASP**: A05:2021 - Security Misconfiguration
- **File**: `xiaotie/automation/macos/wechat_controller.py:37`

**Description**: Hardcoded `/tmp/xiaotie_screenshots` directory is used for screenshots. On multi-user systems, another user could create a symlink at this path pointing to a sensitive location, causing files to be written elsewhere.

**Remediation**: Use `tempfile.mkdtemp()` or a user-specific directory like `~/.xiaotie/screenshots/`.

---

### SEC-014: Feedback Module Shell Injection
- **CVSS**: 6.8 (Medium)
- **CWE**: CWE-78 (OS Command Injection)
- **OWASP**: A03:2021 - Injection
- **File**: `xiaotie/feedback.py:173-194`

**Description**: The `_run_command()` method in the feedback module uses `create_subprocess_shell()` with commands that may include user-supplied file paths (via `lint_file(file_path)`). If `file_path` contains shell metacharacters, command injection is possible.

**Remediation**:
1. Use `create_subprocess_exec()` with argument lists
2. Validate and sanitize file paths before passing to shell commands
3. Use `shlex.quote()` for any values interpolated into shell commands

---

### SEC-015: Proxy SSL Insecure Mode
- **CVSS**: 3.1 (Low)
- **CWE**: CWE-295 (Improper Certificate Validation)
- **OWASP**: A07:2021 - Identification and Authentication Failures
- **File**: `xiaotie/proxy/proxy_server.py:126`

**Description**: The proxy server sets `ssl_insecure=True` for mitmproxy, which disables upstream certificate verification. While expected for a MITM proxy, this means the proxy itself cannot detect if it's being MITMed when connecting to target servers.

**Remediation**: Document this as a known design choice. Consider adding an option to enable upstream cert verification for non-interception use cases.

---

### SEC-016: No Rate Limiting on Telegram Webhook
- **CVSS**: 3.1 (Low)
- **CWE**: CWE-770 (Allocation of Resources Without Limits)
- **OWASP**: A05:2021 - Security Misconfiguration
- **File**: `xiaotie/telegram/webhook.py:52-126`

**Description**: The Telegram webhook server has IP-based access control and secret token verification, but no rate limiting. An attacker who knows the webhook path and has a valid source IP could flood the server with requests.

**Remediation**: Add rate limiting (e.g., token bucket per IP) to the webhook handler.

---

### SEC-017: Subprocess in Feedback and Automation Without Sanitization
- **CVSS**: 5.4 (Medium -- aggregated)
- **CWE**: CWE-78
- **OWASP**: A03:2021 - Injection
- **Files**: `xiaotie/feedback.py:176`, `xiaotie/automation/macos/wechat_controller.py:66,80`, `xiaotie/automation/macos/proxy_integration.py:67,97,129,150`

**Description**: Multiple modules use `create_subprocess_exec` or `create_subprocess_shell` to execute external commands. The automation modules generally use `create_subprocess_exec` (safer), but the feedback module uses `create_subprocess_shell`. Input validation varies.

---

## Dependency Analysis

### Direct Dependencies (pyproject.toml)

| Package | Version | Known Issues |
|---------|---------|-------------|
| anthropic | >=0.40.0 | No critical CVEs |
| openai | >=1.50.0 | No critical CVEs |
| pydantic | >=2.0 | No critical CVEs |
| tiktoken | >=0.7.0 | No critical CVEs |
| pyyaml | >=6.0 | Uses `safe_load` -- OK |
| rich | >=13.0 | No critical CVEs |
| prompt_toolkit | >=3.0 | No critical CVEs |
| aiosqlite | >=0.19.0 | No critical CVEs |
| aiofiles | >=23.0 | No critical CVEs |
| psutil | >=5.8.0 | No critical CVEs |
| mitmproxy | >=10.0.0 | Inherent MITM capabilities |
| chromadb | >=0.4.0 | No critical CVEs |

**Positive finding**: YAML loading uses `yaml.safe_load()` (config.py:230), preventing YAML deserialization attacks.

---

## Priority-Ordered Fix List

| Priority | Finding | Effort | Risk Reduction |
|----------|---------|--------|----------------|
| P0 | SEC-001: Rotate hardcoded API key | 15 min | Critical |
| P0 | SEC-002: Add path traversal protection | 30 min | Critical |
| P0 | SEC-003: Remove BashTool, enforce enhanced | 1 hour | Critical |
| P1 | SEC-005: Replace pickle with safe format | 2 hours | High |
| P1 | SEC-006: Parameterize SQL in QueryBuilder | 2 hours | High |
| P1 | SEC-007: Harden sandbox import checker | 3 hours | High |
| P1 | SEC-004: Improve injection filter (allowlist) | 3 hours | High |
| P1 | SEC-008: Change permission defaults | 15 min | High |
| P2 | SEC-014: Use subprocess_exec in feedback | 30 min | Medium |
| P2 | SEC-009: Replace MD5 with SHA256 | 1 hour | Medium |
| P2 | SEC-010: Default bind to 127.0.0.1 | 15 min | Medium |
| P2 | SEC-011: Fix SSRF DNS rebinding | 2 hours | Medium |
| P2 | SEC-012: Escape LIKE metacharacters | 30 min | Medium |
| P3 | SEC-013: Use secure temp directory | 15 min | Low |
| P3 | SEC-015: Document SSL insecure mode | 15 min | Low |
| P3 | SEC-016: Add webhook rate limiting | 1 hour | Low |

---

## Positive Security Practices Observed

1. **SSRF protections** in WebFetchTool with private IP blocking (SEC-011 is a refinement)
2. **YAML safe_load** used consistently
3. **SQL Validator** with dangerous keyword blocking (needs hardening but good foundation)
4. **Command injection detection** in EnhancedBashTool (needs improvement but exists)
5. **Sandbox with resource limits** (memory, CPU, timeout)
6. **AST-based safe calculator** with strict node allowlist
7. **Telegram webhook** with secret token + IP-based ACL
8. **HMAC timing-safe comparison** in `verify_secret_token`
9. **Docker sandbox option** with read-only fs, no network, PID limits

---

*End of Security Audit Report*
