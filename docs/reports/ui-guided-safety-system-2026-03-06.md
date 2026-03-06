# 小铁引导与安全交互系统交付报告（2026-03-06）

## 1. 交付范围

- Onboarding 主链路流程
  - 支持分步骤引导、进度条、跳过入口、步骤错误提示
  - 支持首次启动判定、完成/跳过状态持久化
  - 支持引导完成后落地基础配置文件
- 主题预览卡片组件
  - 主题列表与实时预览联动
  - 切换动效反馈（预览中 -> 已更新）
  - 预览与实际应用使用同一主题应用链路
- 高风险操作确认层
  - 操作意图识别
  - 二次确认输入（CONFIRM）
  - 冷却期（默认 3 秒）防误触
  - 操作日志写入（JSON Lines）

## 2. 设计理念落地

- 可引导
  - 启动后自动接入引导流程（或首次启动自动触发）
  - 引导中每步都有明确状态与可恢复提示
- 低误触
  - 高风险命令必须通过意图识别 + 输入确认 + 冷却期
  - 取消路径清晰，且记录审计日志

## 3. 响应式与国际化

- 响应式
  - 主题选择器采用双栏布局（列表 + 预览），主应用已有断点适配策略
  - 窄屏下自动收敛侧栏，保证主操作区优先
- 国际化
  - 根据 `LANG` 自动设置 UI 语言（zh/en）
  - 高风险提示标题使用 i18n 词条；系统保留统一术语表达

## 4. 性能优化方案（高并发场景）

- 已落地
  - 消息列表增加 200 条上限，避免无限增长导致渲染退化
  - 主题预览复用主主题应用链路，避免重复渲染器
  - 风险确认逻辑仅在命令入口执行，常规消息路径无额外开销
- 建议下一步
  - 风险日志异步批量落盘（当前为同步 append，适合中低频）
  - 对会话列表更新采用 diff 刷新（减少全量 remove/mount）
  - 在流式输出路径启用批量 flush 节流（50ms）并与消息上限联动

## 5. 测试结果

- 单元与集成测试
  - 命令：`pytest tests/unit/test_onboarding.py tests/unit/test_tui_upgrade.py tests/integration/test_tui_pilot.py tests/integration/test_tui_guided_flow.py -q`
  - 结果：44 passed
- 启动性能
  - `startup_seconds=0.205`
  - 满足首屏 < 2 秒目标

## 6. 产出文件清单

- 核心实现
  - `xiaotie/tui/onboarding.py`
  - `xiaotie/tui/app.py`
  - `xiaotie/tui/main.py`
  - `xiaotie/tui/widgets.py`
- 测试
  - `tests/unit/test_onboarding.py`
  - `tests/unit/test_tui_upgrade.py`
  - `tests/integration/test_tui_guided_flow.py`
