# Performance Baseline Report - Xiaotie v1.1.0

**Date**: 2026-03-06
**Platform**: macOS Darwin 23.2.0, Python 3.x

---

## 1. Startup Time Breakdown

### Package Import (`import xiaotie`)
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Import time (median, 3 runs) | **20ms** | <=800ms | PASS |
| Self time in import chain | 278us | - | - |
| Memory at import | 0.01 MB | - | - |

The top-level `xiaotie` package uses lazy imports for MCP, LSP, and search modules, resulting in an extremely fast initial import.

### Full CLI Startup (`import xiaotie.tui.main`)
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Wall clock time (median) | **620ms** | <=800ms | PASS |
| Python-internal import time | 521ms | - | - |
| Peak memory | 51.91 MB | <=256MB | PASS |

### Core Component Imports (from cold start)
| Component | Time | Memory |
|-----------|------|--------|
| `xiaotie.agent.Agent` | 1781ms | 43.5 MB |
| `xiaotie.events.EventBroker` | <1ms (shared deps) | - |
| `xiaotie.tools.PythonTool` | <1ms (shared deps) | - |
| `xiaotie.config` | 69ms | - |
| `xiaotie.tui.app` | 492ms | 18.8 MB |

Note: `xiaotie.agent.Agent` pulls in anthropic + openai SDKs eagerly, taking ~1.8s standalone. The TUI main path is faster (620ms total) because it imports a different subset.

---

## 2. Import Chain Analysis - Top Bottlenecks

Sorted by self-time (time spent in the module itself, not its dependencies):

| Rank | Module | Self Time (ms) | Category |
|------|--------|----------------|----------|
| 1 | `openai.types.beta.assistant_stream_event` | 28.1 | OpenAI SDK |
| 2 | `openai.types.beta.threads.runs.run_step_delta_event` | 18.3 | OpenAI SDK |
| 3 | `prometheus_client.metrics` | 18.6 | Observability |
| 4 | `anthropic._compat` | 14.5 | Anthropic SDK |
| 5 | `anthropic.lib.streaming` | 11.4 | Anthropic SDK |
| 6 | `openai.types.beta.threads.runs.run_step_delta` | 14.1 | OpenAI SDK |
| 7 | `openai.lib.streaming.responses._events` | 12.8 | OpenAI SDK |
| 8 | `anthropic.lib.streaming._beta_types` | 9.7 | Anthropic SDK |
| 9 | `openai.lib.streaming.chat._types` | 9.4 | OpenAI SDK |
| 10 | `xiaotie.config` | 8.1 | Xiaotie core |

**Key insight**: ~70% of import time comes from OpenAI and Anthropic SDK type definitions. These are third-party dependencies and cannot be easily reduced without lazy-loading the LLM providers.

---

## 3. Memory Usage Profile

| Scenario | Current | Peak | Target | Status |
|----------|---------|------|--------|--------|
| Package import only | 0.01 MB | 0.01 MB | <=256MB | PASS |
| TUI main import | 51.60 MB | 51.91 MB | <=256MB | PASS |
| Agent + all components | 43.49 MB | 43.51 MB | <=256MB | PASS |

Memory usage is well within targets at ~52MB for full CLI startup (20% of 256MB limit).

---

## 4. Runtime Performance Benchmarks

### Event System (20,000 events)
| Metric | Latest Run | Previous Run | Baseline | Status |
|--------|-----------|--------------|----------|--------|
| Single publish (events/sec) | 705,646 | 731,723 | 300,000 | PASS (2.4x) |
| Batch publish (events/sec) | 859,742 | 880,589 | 300,000 | PASS (2.9x) |
| Batch speedup factor | 1.22x | 1.2x | - | - |

### Storage System (200,000 entries, 10,000 retained)
| Metric | Latest Run | Previous Run | Baseline | Status |
|--------|-----------|--------------|----------|--------|
| Insert rate (ops/sec) | 804,858 | 899,345 | 300,000 | PASS (2.7x) |

All runtime benchmarks exceed the baseline by 2-3x with a 0.95 threshold ratio.

---

## 5. Test Suite Statistics

| Metric | Value |
|--------|-------|
| Total tests collected | 1,367 |
| Unit tests run | 1,249 passed, 15 skipped |
| Unit test duration | 20.31s |
| Test failures | 0 |
| Warnings | 2 |
| Code coverage | **54%** (unit tests), **24%** (full collection) |
| Coverage report | `htmlcov/` directory |
| Lines of code (source) | 14,263 |
| Lines covered | 7,718 (54%) |
| Lines uncovered | 6,545 |

### Coverage Gaps (lowest coverage modules)
| Module | Coverage | Notes |
|--------|----------|-------|
| `tui/main.py` | 0% | CLI entry point, not unit-testable |
| `workflows/miniapp_capture.py` | 0% | No tests |
| `workflows/__init__.py` | 0% | - |
| `tools/telegram_tool.py` | 24% | External integration |
| `tui/app.py` | 36% | UI logic hard to unit test |

---

## 6. Summary vs Targets

| Metric | Actual | Target | Margin | Verdict |
|--------|--------|--------|--------|---------|
| CLI startup time | 620ms | <=800ms | 22.5% headroom | PASS |
| Peak memory (startup) | 51.9 MB | <=256MB | 79.7% headroom | PASS |
| Event throughput | 860K/s | >=285K/s | 3.0x over | PASS |
| Storage throughput | 805K/s | >=285K/s | 2.8x over | PASS |

---

## 7. Bottleneck Identification & Optimization Recommendations

### High Priority

1. **Lazy-load LLM provider SDKs** (`anthropic`, `openai`)
   - These account for ~70% of agent import time (1.4s of 1.8s)
   - Defer import until first LLM call is made
   - Impact: Would reduce `from xiaotie.agent import Agent` from 1.8s to ~400ms

2. **Lazy-load `prometheus_client`**
   - 18.6ms self-time on import
   - Only needed when metrics are enabled
   - Impact: Minor but easy win

### Medium Priority

3. **Increase test coverage to 70%+**
   - Current 54% leaves significant code untested
   - Focus on `workflows/`, `tui/main.py`, and `tools/telegram_tool.py`

4. **The `performance_test.py` benchmark is broken**
   - Imports `Agent` and `AsyncLRUCache` from `xiaotie` top-level, but these are not exported
   - Fix: Update imports to use correct submodule paths

### Low Priority

5. **Consider import-time budgeting**
   - Add a CI gate that fails if startup exceeds 800ms
   - Use the existing `benchmarks/results/performance-gate-report.json` pattern

6. **Profile Textual CSS tokenizer**
   - `textual.css.tokenize` takes ~5ms self-time
   - Low priority but could be deferred if TUI startup grows

---

## Appendix: Raw Benchmark Data

```json
{
  "timestamp": 1772769302,
  "event_benchmark": {
    "single_publish_seconds": 0.028343,
    "batch_publish_seconds": 0.023263,
    "events": 20000,
    "single_events_per_sec": 705645.76,
    "batch_events_per_sec": 859742.07,
    "speedup": 1.22
  },
  "storage_benchmark": {
    "insert_seconds": 0.248491,
    "insert_per_sec": 804857.85,
    "total_entries": 200000,
    "retained_entries": 10000,
    "max_entries": 10000
  }
}
```
