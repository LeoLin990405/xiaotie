# Xiaotie v1.1.0 Codebase Audit Report

**Date**: 2026-03-06
**Scope**: `/Users/leo/Desktop/xiaotie/xiaotie/` (127 source files, ~32k lines)
**Test Coverage**: 24% (1367 tests, 55 test files)
**Auditor**: code-auditor agent

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Source files | 127 |
| Total lines | 32,044 |
| Test files | 55 |
| Tests collected | 1,367 |
| Coverage | 24% |
| TODO/FIXME markers | 1 |
| Bare except clauses | 4 |
| Complex functions (CC >= 8) | 95 |
| Functions missing type annotations | 1,425 |
| Print statements in non-UI code | 49 |
| Global mutable singletons | 4+ |

---

## Issues by Severity

### P0 - Critical (Must Fix)

#### P0-1: PythonTool missing `await` on async sandbox call
- **File**: `xiaotie/tools/python_tool.py:46`
- **Description**: `self._sandbox.execute(code)` is an `async def` method (defined in `sandbox.py:464`) but is called without `await`. This means the PythonTool never actually executes code -- it gets a coroutine object instead of an `ExecutionResult`, and subsequent `.status` access will fail or produce wrong results.
- **Fix**: Change `result = self._sandbox.execute(code)` to `result = await self._sandbox.execute(code)`
- **Effort**: S

#### P0-2: Metrics server binds to 0.0.0.0 by default
- **File**: `xiaotie/cli.py:58`
- **Description**: `start_metrics_server()` defaults to `host="0.0.0.0"` with metrics enabled by default. This exposes Prometheus metrics to all network interfaces without authentication. An attacker on the same network can scrape internal metrics.
- **Fix**: Default to `127.0.0.1` and require explicit opt-in for external binding.
- **Effort**: S

#### P0-3: No input sanitization on bash tool commands
- **File**: `xiaotie/tools/bash_tool.py:63`
- **Description**: `asyncio.create_subprocess_shell(command, ...)` passes LLM-generated commands directly to the shell. While the permission system catches some dangerous patterns via regex, the regex-based blocklist in `permissions.py:60-86` is bypassable (e.g. `r\m -r\f`, encoded commands, shell quoting tricks, `$(...)` subshells). The permission system auto-approves medium-risk by default.
- **Fix**: Use a proper command parser or deny-by-default for bash. Consider using `subprocess_exec` with argument splitting instead of `subprocess_shell`.
- **Effort**: M

#### P0-4: Sensitive output filter is overly broad and bypassable
- **File**: `xiaotie/agent/core.py:777-791`
- **Description**: The `_filter_sensitive_output` regex blocks entire output if it contains patterns like `token\s*[:=]\s*[^\s]+`. This false-positives on legitimate output (e.g. code containing the word "token"). Meanwhile, it can be bypassed with multiline formatting, base64 encoding, etc.
- **Fix**: Use a more targeted approach (e.g., entropy-based detection, only match specific key formats).
- **Effort**: M

---

### P1 - High (Should Fix Soon)

#### P1-1: Massive code duplication in `cli.py` between interactive and non-interactive paths
- **File**: `xiaotie/cli.py:292-393` vs `xiaotie/cli.py:487-587`
- **Description**: `main_async()` and `run_non_interactive()` duplicate ~100 lines of nearly identical setup code: config loading, tool creation, plugin loading, MCP loading, LLM client creation, retry config. Any change to startup must be made in two places.
- **Fix**: Extract shared setup into a helper function (e.g., `_create_agent_from_config(config) -> Agent`).
- **Effort**: S

#### P1-2: `_execute_single_tool` is 183 lines with CC=13
- **File**: `xiaotie/agent/core.py:468-650`
- **Description**: This method handles tool resolution, permission checking, execution, error handling, telemetry recording, and event publishing all in one function. It's the most complex method in the codebase and very hard to test in isolation.
- **Fix**: Extract into smaller methods: `_resolve_tool()`, `_check_tool_permission()`, `_record_tool_result()`.
- **Effort**: M

#### P1-3: `_stream_generate` has CC=21 with nested closures
- **File**: `xiaotie/agent/core.py:652-746`
- **Description**: This method defines 5 inner functions/closures, manages event buffering state with `nonlocal`, and mixes synchronous and asynchronous callbacks via `asyncio.create_task()`. The `sync_on_thinking`/`sync_on_content` wrappers at lines 720-724 create fire-and-forget tasks that can silently fail.
- **Fix**: Extract stream handler into a separate `StreamHandler` class.
- **Effort**: M

#### P1-4: `openai_client.py:generate_stream` has CC=32 (highest in codebase)
- **File**: `xiaotie/llm/openai_client.py:197-331`
- **Description**: 135-line method handling GLM-specific params, MiniMax params, fallback retry, streaming chunk parsing for thinking/content/tool_calls, and JSON assembly. Extremely hard to test and maintain.
- **Fix**: Extract provider-specific logic into strategy methods. Split stream processing into a separate method.
- **Effort**: L

#### P1-5: `_normalize_steps` duplicated in Pipeline and Parallel
- **File**: `xiaotie/orchestrator.py:248-260` and `xiaotie/orchestrator.py:310-320`
- **Description**: Nearly identical method duplicated in two classes. The Pipeline version raises on invalid types while the Parallel version silently ignores them -- inconsistent behavior.
- **Fix**: Move to `Workflow` base class with consistent error handling.
- **Effort**: S

#### P1-6: 24% test coverage is dangerously low
- **File**: Project-wide
- **Description**: Critical paths like `agent/core.py`, `llm/openai_client.py`, `permissions.py`, and `tools/bash_tool.py` have minimal coverage. The 1,367 tests are mostly unit tests for individual tools. Integration tests for the agent loop are sparse.
- **Fix**: Prioritize coverage for agent core loop, LLM clients, and permission system. Target 60%+ for critical paths.
- **Effort**: XL

#### P1-7: Global mutable singletons without thread safety
- **Files**: `xiaotie/events.py:327` (`_global_broker`), `xiaotie/storage/database.py:254` (`_database`), `xiaotie/cli.py:54` (`_mcp_manager`), `xiaotie/display.py` (display singleton)
- **Description**: Multiple global mutable singletons initialized lazily with no thread-safety guarantees. In concurrent contexts (multi-agent, TUI), race conditions are possible.
- **Fix**: Use module-level locks or dependency injection pattern instead of global singletons.
- **Effort**: M

---

### P2 - Medium (Should Fix)

#### P2-1: 49 stray `print()` statements in non-UI code
- **Files**: `agent/core.py` (14), `lsp/client.py` (4), `memory/core.py` (4), `plugins.py` (4), `custom_commands.py` (2), others (21)
- **Description**: Debug/status print statements scattered throughout business logic. Bypasses the logging system, makes output uncontrollable, and prevents quiet mode from working properly. The `agent/core.py` prints are partially guarded by `if not self.quiet` but inconsistently.
- **Fix**: Replace all `print()` calls with `logging` or route through the Display/Event system.
- **Effort**: M

#### P2-2: 4 bare `except:` clauses
- **Files**: `xiaotie/logging.py:33`, `xiaotie/cache.py:134`, `xiaotie/automation/miniapp_automation.py:105,161`
- **Description**: Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and other critical exceptions, masking bugs.
- **Fix**: Change to `except Exception:` at minimum.
- **Effort**: S

#### P2-3: 1,425 functions missing type annotations
- **File**: Project-wide
- **Description**: Majority of function arguments lack type annotations. This hampers IDE support, static analysis, and makes the codebase harder to understand.
- **Fix**: Add type annotations to public API methods first, then internal methods. Use `mypy` in CI.
- **Effort**: L

#### P2-4: Agent core uses `time.time()` and `time.perf_counter()` inconsistently
- **File**: `xiaotie/agent/core.py:342,449,452,555,558,625`
- **Description**: `_run_loop` uses `time.perf_counter()` for LLM timing but `_execute_tools_parallel` uses `time.time()`. `perf_counter` is monotonic and more accurate; `time.time()` can jump due to NTP adjustments.
- **Fix**: Standardize on `time.perf_counter()` for all duration measurements.
- **Effort**: S

#### P2-5: `tools/__init__.py` eagerly imports all tools
- **File**: `xiaotie/tools/__init__.py:1-45`
- **Description**: Importing `xiaotie.tools` loads ALL tool modules including heavy ones like `charles_tool.py` (867 lines), `scraper_tool.py` (498 lines), and `proxy_tool.py`. This slows startup even when most tools are disabled in config.
- **Fix**: Use lazy imports -- only import tools when they are enabled in config.
- **Effort**: M

#### P2-6: Token estimation uses wrong encoding for non-Anthropic providers
- **File**: `xiaotie/agent/core.py:119-123`
- **Description**: `cl100k_base` encoding is used for all providers, but it's specific to OpenAI/Anthropic tokenizers. For GLM, Qwen, DeepSeek etc. the estimates will be inaccurate.
- **Fix**: Select encoding based on provider, or use a generic character-based estimate for non-OpenAI providers.
- **Effort**: S

#### P2-7: `BatchCommitDatabase._flush_loop` runs forever with no shutdown
- **File**: `xiaotie/storage/database.py:197-207`
- **Description**: The `_flush_loop` asyncio task runs indefinitely with `while True`. If `close()` is not called (e.g., unclean exit), the task leaks. Also, exceptions in the flush loop are silently swallowed with bare `pass`.
- **Fix**: Add a stop flag and proper error logging.
- **Effort**: S

#### P2-8: Permission system regex patterns are not anchored
- **File**: `xiaotie/permissions.py:60-86`
- **Description**: Dangerous patterns like `r"rm\s+-rf"` will match substrings, causing false positives (e.g., a filename containing "rm -rf" in a comment). Meanwhile, patterns can be bypassed by prepending characters.
- **Fix**: Anchor patterns appropriately and use word boundaries.
- **Effort**: S

---

### P3 - Low (Nice to Have)

#### P3-1: `orchestrator.py` is 562 lines of unused code
- **File**: `xiaotie/orchestrator.py`
- **Description**: The orchestrator module (Pipeline, Parallel, Router, Orchestrator) is well-designed but appears to not be imported or used anywhere in the main application flow. No tests reference it except `test_orchestrator.py`.
- **Fix**: Either integrate into the agent workflow or mark as experimental/remove.
- **Effort**: S

#### P3-2: `_summarize_messages` drops tool call context
- **File**: `xiaotie/agent/core.py:213-276`
- **Description**: When summarizing, old tool calls and results are discarded. This loses important context about what actions were taken, potentially causing the agent to repeat actions.
- **Fix**: Include tool call summaries in the summarized context.
- **Effort**: M

#### P3-3: `SandboxPool` uses threading lock in async context
- **File**: `xiaotie/sandbox.py:506-555`
- **Description**: `SandboxPool` uses `threading.Lock` which blocks the event loop. Should use `asyncio.Lock` since `execute()` is async.
- **Fix**: Replace `threading.Lock` with `asyncio.Lock`.
- **Effort**: S

#### P3-4: `config.py:from_yaml` has excessive backwards compatibility code
- **File**: `xiaotie/config.py:236-278`
- **Description**: The YAML loader has ~40 lines of fallback logic for "old version" config format. If v1.1.0 is the baseline for v2, this legacy support should be cleaned up.
- **Fix**: Remove old-format support and provide a migration script.
- **Effort**: S

#### P3-5: `knowledge_base.py` and `memory/core.py` overlap in functionality
- **File**: `xiaotie/knowledge_base.py` (600 lines) and `xiaotie/memory/core.py` (561 lines)
- **Description**: Both modules deal with storing and retrieving information. `knowledge_base.py` handles structured knowledge while `memory/core.py` handles conversation memory, but they share patterns (chunk storage, search, metadata) without a common base.
- **Fix**: Evaluate consolidation or extract shared storage patterns into a common module.
- **Effort**: L

#### P3-6: `builder.py` contains example code in docstrings with print statements
- **File**: `xiaotie/builder.py:15,121`
- **Description**: The builder module has example lambda callbacks in docstrings that use `print()`. Minor, but indicates the builder pattern may not be production-ready.
- **Fix**: Clean up examples or add proper documentation.
- **Effort**: S

---

## Architecture Assessment

### Strengths
1. **Clean event system**: The `EventBroker` with weak references and copy-on-read is well-designed for async UI updates.
2. **Provider abstraction**: `LLMClient` wrapper cleanly abstracts Anthropic vs OpenAI-compatible APIs.
3. **Config via Pydantic**: Type-safe configuration with validation and defaults.
4. **Database layer**: `BatchCommitDatabase` with write-behind is a thoughtful optimization for SQLite.
5. **Permission system**: Risk-based classification with interactive approval is a good foundation.

### Weaknesses
1. **God class**: `Agent` in `core.py` (810 lines) does too much -- LLM calls, tool execution, streaming, token management, summarization, permissions, events.
2. **Eager loading**: All tools are imported at startup regardless of config, adding unnecessary latency.
3. **Mixed concerns**: `cli.py` handles both CLI parsing and application bootstrapping.
4. **No dependency injection**: Global singletons (event broker, database, MCP manager) make testing and concurrent usage difficult.
5. **Inconsistent error handling**: Mix of return values, exceptions, and silently swallowed errors across the codebase.

### Module Coupling (Low Risk)
No circular imports detected. Module dependencies are mostly one-directional:
- `cli.py` -> `agent/core.py` -> `llm/`, `tools/`, `events.py`, `permissions.py`, `telemetry.py`
- `tools/*` -> `schema.py`, `tools/base.py`
- `storage/*` -> standalone (only `aiosqlite`)

---

## Priority-Ordered Action Items

| Priority | ID | Issue | Effort | Impact |
|----------|----|-------|--------|--------|
| P0 | P0-1 | Fix missing `await` in PythonTool | S | Bug: tool completely broken |
| P0 | P0-2 | Bind metrics to 127.0.0.1 | S | Security: network exposure |
| P0 | P0-3 | Harden bash tool command execution | M | Security: command injection |
| P0 | P0-4 | Fix sensitive output filter | M | Security: false positives/negatives |
| P1 | P1-1 | Deduplicate CLI setup code | S | Maintainability |
| P1 | P1-5 | Deduplicate `_normalize_steps` | S | Code quality |
| P1 | P1-2 | Decompose `_execute_single_tool` | M | Testability |
| P1 | P1-3 | Extract stream handler | M | Testability |
| P1 | P1-4 | Refactor `generate_stream` | L | Maintainability |
| P1 | P1-7 | Fix global singleton threading | M | Correctness |
| P1 | P1-6 | Increase test coverage to 60%+ | XL | Reliability |
| P2 | P2-2 | Fix bare except clauses | S | Correctness |
| P2 | P2-4 | Standardize timing functions | S | Correctness |
| P2 | P2-6 | Fix token estimation per provider | S | Accuracy |
| P2 | P2-7 | Fix flush loop lifecycle | S | Reliability |
| P2 | P2-8 | Anchor permission regex patterns | S | Security |
| P2 | P2-5 | Lazy-load tool modules | M | Startup performance |
| P2 | P2-1 | Replace print() with logging | M | Observability |
| P2 | P2-3 | Add type annotations | L | Developer experience |
| P3 | P3-1 | Evaluate orchestrator usage | S | Dead code |
| P3 | P3-3 | Fix SandboxPool lock type | S | Correctness |
| P3 | P3-4 | Remove legacy config support | S | Simplicity |
| P3 | P3-6 | Clean up builder examples | S | Polish |
| P3 | P3-2 | Preserve tool context in summary | M | Agent quality |
| P3 | P3-5 | Consolidate knowledge/memory | L | Architecture |
