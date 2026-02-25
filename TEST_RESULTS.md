# 单元测试结果报告

**项目**: xiaotie v1.1.0
**测试时间**: 2026-02-25
**Python**: 3.9.6 | pytest 8.4.2
**平台**: macOS Darwin 23.2.0

## 测试总结

| 指标 | 数值 |
|------|------|
| 总测试数 | 1182 (收集) |
| 通过 | 1149 |
| 失败 | 18 |
| 跳过 | 15 |
| 收集错误 | 5 |
| 警告 | 6 |
| 执行时间 | 17.65s |
| 代码覆盖率 | **54.80%** (要求 >= 30%, 通过) |

## 收集错误 (5个文件无法加载)

| 测试文件 | 错误原因 |
|----------|----------|
| `test_cache.py` | ImportError: `CacheConfig` 不存在于 `xiaotie.cache` |
| `test_command_palette.py` | SyntaxError: `xiaotie/tui/themes.py:461` 未匹配的 `}` |
| `test_multi_agent.py` | ImportError: `AgentCoordinator` 不存在于 `xiaotie.multi_agent` |
| `test_onboarding.py` | SyntaxError: `xiaotie/tui/themes.py:461` 未匹配的 `}` |
| `test_streaming.py` | SyntaxError: `xiaotie/tui/themes.py:461` 未匹配的 `}` |

## 失败测试 (18个)

### test_sandbox.py (11个失败)

所有失败原因: `AttributeError: 'TokenUsage' object has no attribute 'prompt_tokens'`
- `TestSandbox::test_execute_simple_code`
- `TestSandbox::test_execute_blocked_import`
- `TestSandbox::test_execute_skip_import_check`
- `TestSandbox::test_on_complete_callback`
- `TestSandbox::test_execute_file`
- `TestSandbox::test_execute_file_not_found`
- `TestSandboxPool::test_execute_with_pool`
- `TestSandboxPool::test_execute_no_available`
- `TestDockerExecutor::test_docker_not_available`
- `TestDockerExecutor::test_docker_check_timeout`
- `TestIntegration::test_full_workflow`
- `TestIntegration::test_computation`
- `TestIntegration::test_error_handling`

**根因**: `TokenUsage` pydantic 模型字段名与测试中使用的 `prompt_tokens` 不匹配。

### test_orchestrator.py (2个失败)
- `TestPipeline::test_pipeline_continue_on_error`
- `TestIntegration::test_nested_workflows`

### test_database.py (1个失败)
- `TestDatabaseTool::test_get_columns_invalid_table`

### test_providers.py (1个失败)
- `TestLLMClientProviderIntegration::test_client_from_unknown_provider`

### test_schema.py (1个失败)
- `TestLLMResponse::test_response_with_usage` — 同样是 `TokenUsage` 字段名问题

## 覆盖率详情 (按模块)

| 模块 | 覆盖率 | 说明 |
|------|--------|------|
| `xiaotie/schema.py` | 100% | 完全覆盖 |
| `xiaotie/lsp/protocol.py` | 100% | 完全覆盖 |
| `xiaotie/mcp/protocol.py` | 100% | 完全覆盖 |
| `xiaotie/scraper/auth.py` | 100% | 完全覆盖 |
| `xiaotie/scraper/output.py` | 100% | 完全覆盖 |
| `xiaotie/proxy/storage.py` | 99% | 近完全覆盖 |
| `xiaotie/config.py` | 96% | 高覆盖 |
| `xiaotie/retry_v2.py` | 95% | 高覆盖 |
| `xiaotie/scraper/base_scraper.py` | 95% | 高覆盖 |
| `xiaotie/testing/__init__.py` | 93% | 高覆盖 |
| `xiaotie/database.py` | 92% | 高覆盖 |
| `xiaotie/orchestrator.py` | 90% | 高覆盖 |
| `xiaotie/builder.py` | 90% | 高覆盖 |
| `xiaotie/tui/` | 0% | TUI 模块未覆盖 (themes.py 语法错误) |
| `xiaotie/cli.py` | 0% | CLI 入口未覆盖 |
| **总计** | **54.80%** | **16254 语句, 7347 未覆盖** |

## 关键问题

1. **`xiaotie/tui/themes.py:461` 语法错误** — 未匹配的 `}`，导致 3 个测试文件无法收集
2. **`TokenUsage` 模型字段不匹配** — 影响 sandbox 和 schema 相关的 12 个测试
3. **`CacheConfig` 和 `AgentCoordinator` 导入缺失** — 代码重构后测试未同步更新
