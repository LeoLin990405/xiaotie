# XiaoTie v3

**A MIMO-only local coding-agent runtime.**

XiaoTie v3 is no longer a multi-provider model wrapper. It keeps one model boundary, `provider: mimo`, and focuses the repo on agent runtime concerns: state machines, guardrails, trace events, checkpoints, tool permissions, context budgeting, RepoMap, and sandboxed execution.

## Runtime Shape

```text
input_guardrail
  -> thinking
  -> acting
  -> observing
  -> reflecting
  -> completed | failed | cancelled
```

Every major phase emits an `AgentTraceEvent` and stores an `AgentCheckpoint`.

## Quick Start

```bash
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie
pip install -e ".[dev,tui,secrets,repomap]"
export MIMO_API_KEY="your-key"
xiaotie
```

Minimal config:

```yaml
api_key: ${secret:api_key}
api_base: https://token-plan-sgp.xiaomimimo.com/anthropic
model: mimo-v2-pro
provider: mimo
thinking_enabled: false
```

## Supported Model Boundary

| Provider | Models |
|----------|--------|
| `mimo` | `mimo-v2-pro`, `mimo-v2-omni` |

Other provider names are intentionally rejected.

## Development Gate

```bash
uv run --python 3.12 --extra dev ruff check xiaotie/ tests/unit/test_providers.py tests/unit/test_config.py tests/unit/test_builder.py tests/unit/test_runtime.py tests/unit/test_agent_architecture.py tests/unit/test_mimo_client.py
uv run --python 3.12 --extra dev python -m pytest tests/unit -q
uv run --python 3.12 --extra dev python -m pytest tests/integration/test_core_business_smoke.py -v --tb=short -m smoke
```

Latest local result: `1674 passed, 39 skipped`, smoke `3 passed`, coverage `62%`.

## License

[MIT](LICENSE)
