# Test Coverage Analysis - Xiaotie v1.1.0

**Date**: 2026-03-06
**Test Suite**: 1,249 unit tests passed, 15 skipped, 2 warnings (21.06s)
**Overall Coverage**: 54% (7,718 / 14,263 statements)

---

## 1. Benchmark Fix

**File**: `benchmarks/performance_test.py`
**Issue**: Imported `Agent` and `AsyncLRUCache` from top-level `xiaotie`, but they are not re-exported there.
**Fix**: Changed to correct submodule imports:
```python
# Before (broken)
from xiaotie import Agent, AsyncLRUCache

# After (fixed)
from xiaotie.agent import Agent
from xiaotie.cache import AsyncLRUCache
```
**Status**: Verified working -- all 3 benchmark tests pass (cache, events, agent creation).

---

## 2. Modules Below 50% Coverage

### 0% Coverage (no tests at all) -- 18 modules

| Module | Statements | Category |
|--------|-----------|----------|
| `automation/__init__.py` | 6 | Automation |
| `automation/appium_driver.py` | - | Automation |
| `automation/macos/__init__.py` | - | Automation |
| `automation/macos/miniapp_controller.py` | - | Automation |
| `automation/macos/proxy_integration.py` | - | Automation |
| `automation/macos/wechat_controller.py` | - | Automation |
| `automation/miniapp_automation.py` | - | Automation |
| `banner.py` | - | Display |
| `cache.py` | - | Core |
| `cli.py` | - | CLI |
| `display.py` | - | Display |
| `feedback.py` | - | UI |
| `input.py` | - | UI |
| `knowledge_base.py` | - | Core |
| `logging.py` | - | Infra |
| `memory/core.py` | 302 | Core |
| `multi_agent/__init__.py` | 5 | Multi-Agent |
| `multi_agent/agent_tool.py` | 29 | Multi-Agent |
| `multi_agent/coordinator.py` | 169 | Multi-Agent |
| `multi_agent/roles.py` | 24 | Multi-Agent |
| `multi_agent/task_agent.py` | 85 | Multi-Agent |
| `plugins.py` | 79 | Core |
| `profiles.py` | 119 | Core |
| `repomap.py` | 186 | Core |
| `scraper/examples/demo_scraper.py` | 9 | Example |
| `session.py` | 92 | Core |
| `tui/main.py` | 64 | TUI |
| `workflows/__init__.py` | 2 | Workflows |
| `workflows/miniapp_capture.py` | 223 | Workflows |

### 1-49% Coverage -- 17 modules

| Module | Coverage | Statements | Uncovered | Category |
|--------|----------|-----------|-----------|----------|
| `commands/custom.py` | 9% | - | - | Commands |
| `commands/workspace.py` | 12% | - | - | Commands |
| `commands/profiles.py` | 13% | - | - | Commands |
| `commands/plugins.py` | 15% | - | - | Commands |
| `commands/quality.py` | 16% | - | - | Commands |
| `commands/session.py` | 17% | - | - | Commands |
| `tools/automation_tool.py` | 20% | 139 | 111 | Tools |
| `commands/system.py` | 21% | - | - | Commands |
| `tools/telegram_tool.py` | 24% | 85 | 65 | Tools |
| `search/semantic_search.py` | 29% | 108 | 77 | Search |
| `custom_commands.py` | 32% | - | - | Commands |
| `tools/extended.py` | 32% | 119 | 81 | Tools |
| `llm/openai_client.py` | 33% | - | - | LLM |
| `tui/app.py` | 36% | 583 | 372 | TUI |
| `tui/layout.py` | 39% | 51 | 31 | TUI |
| `lsp/client.py` | 40% | - | - | LSP |
| `commands/base.py` | 42% | - | - | Commands |
| `tui/onboarding.py` | 42% | 306 | 177 | TUI |
| `search/vector_store.py` | 42% | 71 | 41 | Search |
| `tools/bash_tool.py` | 43% | 42 | - | Tools |
| `proxy/cert_manager.py` | 45% | 55 | 30 | Proxy |
| `tools/semantic_search_tool.py` | 46% | 70 | 38 | Tools |

---

## 3. Coverage by Category

| Category | Avg Coverage | Modules | Key Gaps |
|----------|-------------|---------|----------|
| **Core framework** (agent, schema, config, events) | 83% | 8 | agent/core.py at 65% |
| **LLM clients** | 65% | 5 | openai_client.py at 33% |
| **Tools** | 62% | 15 | automation_tool 20%, telegram_tool 24% |
| **TUI** | 45% | 8 | main.py 0%, app.py 36% |
| **Commands** | 20% | 9 | Most commands 10-20% |
| **Multi-Agent** | 0% | 5 | Entire subsystem untested |
| **Automation** | 0% | 7 | Entire subsystem untested |
| **Workflows** | 0% | 2 | Entire subsystem untested |
| **Search** | 46% | 4 | semantic_search 29% |
| **Storage/DB** | 86% | 5 | message_store 60% |
| **Scraper** | 84% | 6 | demo_scraper 0% (example) |
| **Proxy** | 77% | 5 | cert_manager 45% |
| **MCP** | 82% | 4 | transport 53% |
| **Telegram** | 73% | 4 | client 61% |

---

## 4. Highest-Impact Improvements

To reach **70% coverage** (target: +16 percentage points), prioritize by statement count:

| Priority | Module | Current | Uncovered Stmts | Effort |
|----------|--------|---------|-----------------|--------|
| 1 | `tui/app.py` | 36% | 372 | High (UI logic) |
| 2 | `memory/core.py` | 0% | 302 | Medium |
| 3 | `workflows/miniapp_capture.py` | 0% | 223 | Medium |
| 4 | `repomap.py` | 0% | 186 | Medium |
| 5 | `tui/onboarding.py` | 42% | 177 | High (UI) |
| 6 | `multi_agent/coordinator.py` | 0% | 169 | Medium |
| 7 | `tui/widgets.py` | 56% | 136 | High (UI) |
| 8 | `tui/command_palette.py` | 55% | 122 | High (UI) |
| 9 | `profiles.py` | 0% | 119 | Low |
| 10 | `tools/automation_tool.py` | 20% | 111 | Medium |

Adding tests for just the top 5 modules (memory/core, workflows, repomap, multi_agent/coordinator, profiles) would cover ~1,000 additional statements and push overall coverage to ~61%.

---

## 5. Recommendations

1. **Quick wins (0% modules with simple logic)**: `cache.py`, `session.py`, `profiles.py`, `plugins.py`, `logging.py` -- these are straightforward to unit test and would add ~500 statements.

2. **Multi-Agent subsystem** (0% across 5 modules, 312 statements): This is a complete feature with no test coverage. High risk for regressions.

3. **Commands subsystem** (avg 20%, 9 modules): Nearly all slash commands lack tests. Consider a parametric test approach using the command registry.

4. **TUI modules** are inherently hard to unit test. Consider integration tests with Textual's testing framework (`textual.pilot`).

5. **`benchmarks/performance_test.py`** import fix is applied and verified. The agent creation benchmark runs in 0.09s for 10 agents.
