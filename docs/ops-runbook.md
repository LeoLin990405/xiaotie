# 生产部署与监控运行手册

## 0. 前置依赖

- python3
- pip
- pytest
- docker
- docker compose

## 1. 一键部署

```bash
./scripts/deploy_prod.sh
```

执行计划参考：

- [next-step-delivery-plan.md](./next-step-delivery-plan.md)

## 2. 监控访问地址

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- OTel Collector OTLP gRPC: localhost:4317
- OTel Collector OTLP HTTP: localhost:4318
- Agent Prometheus 指标: http://localhost:9464

启动前可按需调整：

```bash
export XIAOTIE_METRICS_ENABLED=1
export XIAOTIE_METRICS_HOST=0.0.0.0
export XIAOTIE_METRICS_PORT=9464
```

会话中可实时查看指标快照：

```text
/metrics
/metrics json
```

## 3. 性能基准

```bash
python3 benchmarks/agent_perf_benchmark.py
python3 scripts/check_benchmark_thresholds.py
```

基准结果会写入：

- `benchmarks/results/latest.json`

## 4. 回归验证

```bash
pytest -q
```

## 5. 生产门禁建议

- 测试门禁：单元、集成全量通过
- 性能门禁：批量事件吞吐不低于基线 90%
- 安全门禁：高风险工具调用需要二次确认

## 6. 监控联调检查

- 导入 Grafana 模板：`deployment/grafana-agent-dashboard.json`
- Prometheus 查询示例：
  - `sum(rate(xiaotie_runs_total[5m]))`
  - `histogram_quantile(0.95, sum(rate(xiaotie_llm_latency_seconds_bucket[5m])) by (le))`
  - `sum(rate(xiaotie_tool_calls_total{success="false"}[5m])) / clamp_min(sum(rate(xiaotie_tool_calls_total[5m])), 1e-9)`
