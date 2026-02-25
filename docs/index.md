# 小铁 (XiaoTie)

轻量级 AI Agent 框架，基于 Mini-Agent 架构，融合认知科学理论。

## 快速开始

```bash
pip install xiaotie
```

```python
from xiaotie import AgentBuilder

agent = (
    AgentBuilder()
    .with_provider("anthropic", model="claude-sonnet-4-20250514")
    .with_memory()
    .with_context()
    .build()
)

response = await agent.run("你好，帮我分析这段代码")
```

## 文档导航

- [架构设计](architecture.md) - 系统架构、模块关系图、ADR 决策记录
- [认知架构指南](cognitive-architecture.md) - 记忆/上下文/决策/学习等模块使用指南
- [API 参考](api/agent.md) - 完整 API 文档（从源码 docstring 自动生成）

## 生成 API 文档

```bash
# 安装文档依赖
pip install xiaotie[docs]

# 本地预览
mkdocs serve

# 构建静态站点
mkdocs build
```
