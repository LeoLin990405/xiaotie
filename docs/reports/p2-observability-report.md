# P2 可观测性阶段交付报告

## 1. 交付范围

- Agent 运行监控模块：`xiaotie/telemetry.py`
- Agent 核心链路埋点：`xiaotie/agent.py`
- 指标查看命令：`xiaotie/commands.py` `/metrics`
- Prometheus 指标服务启动：`xiaotie/cli.py`
- Grafana 模板：`deployment/grafana-agent-dashboard.json`

## 2. 已落地指标

- 运行维度：`runs_total`、`runs_success`、`runs_error`、`runs_cancelled`
- LLM 维度：调用总量、错误率、平均时延、P95 时延、provider/model 维度计数
- 工具维度：调用总量、错误率、平均时延、P95 时延、tool 维度计数
- 流式维度：flush 次数、批均事件数、flush 时延、队列深度

## 3. 监控接入说明

- 启动后默认暴露 Prometheus 指标端口：`9464`
- Grafana 导入模板：`deployment/grafana-agent-dashboard.json`
- 命令行实时指标：
  - `/metrics`
  - `/metrics json`

## 4. 验证记录

- 单元测试：
  - `pytest tests/unit/test_telemetry.py tests/unit/test_agent.py tests/unit/test_commands.py -q`
  - 结果：14 passed
- 代码静态检查：
  - `python3 -m compileall xiaotie`
  - 结果：通过

## 5. 风险与应对

- 风险：生产环境 Prometheus 未抓取到 Agent 端口
  - 应对：发布前新增抓取连通性检查并在预发对齐网络策略
- 风险：指标标签维度膨胀
  - 应对：当前仅保留 `provider/model/tool/session_id`，禁止透传用户输入类标签
