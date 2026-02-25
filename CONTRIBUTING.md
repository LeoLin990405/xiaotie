# 贡献指南

感谢你对小铁 (XiaoTie) 项目的关注！欢迎提交 Issue 和 Pull Request。

## 开发环境设置

```bash
# 克隆项目
git clone https://github.com/LeoLin990405/xiaotie.git
cd xiaotie

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装开发依赖
pip install -e ".[all]"
pip install pytest pytest-asyncio pytest-cov ruff mypy
```

## 代码规范

- 使用 [ruff](https://github.com/astral-sh/ruff) 进行代码格式化和 lint
- 遵循 PEP 8 风格指南
- 类型注解：所有公开 API 必须包含类型注解
- 文档字符串：公开类和方法使用 Google 风格 docstring
- 中文注释：内部注释使用中文，docstring 使用中文

```bash
# 格式化
ruff format xiaotie/

# Lint 检查
ruff check xiaotie/
```

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[optional body]
```

### Type 类型

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `refactor` | 代码重构 |
| `test` | 测试相关 |
| `perf` | 性能优化 |
| `chore` | 构建/工具变更 |

### 示例

```
feat(agent): 添加工具并行执行支持
fix(events): 修复弱引用导致的内存泄漏
docs(readme): 更新安装说明
test(config): 添加 YAML 解析单元测试
```

## 测试要求

- 新功能必须包含对应的单元测试
- Bug 修复应包含回归测试
- 测试文件放在 `tests/unit/` 或 `tests/integration/` 目录下
- 使用 `pytest-asyncio` 测试异步代码

```bash
# 运行所有测试
pytest

# 运行指定模块测试
pytest tests/unit/test_agent.py

# 查看覆盖率
pytest --cov=xiaotie --cov-report=html
```

## 分支策略

- `main` - 稳定版本
- `dev` - 开发分支
- `feat/<name>` - 功能分支
- `fix/<name>` - 修复分支

## Pull Request 流程

1. Fork 项目并创建功能分支
2. 编写代码和测试
3. 确保所有测试通过且 lint 无报错
4. 提交 PR 到 `dev` 分支
5. 等待代码审查

## 项目结构

核心模块位于 `xiaotie/` 目录下，认知架构模块包括：

- `context/` - 上下文感知
- `decision/` - 智能决策
- `learning/` - 自适应学习
- `memory/` - 记忆系统
- `planning/` - 规划系统
- `reflection/` - 反思机制
- `skills/` - 技能学习
- `kg/` - 知识图谱
- `rl/` - 强化学习
- `multimodal/` - 多模态支持
