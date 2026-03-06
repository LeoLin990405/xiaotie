# Telegram Bot 集成指南

## 1. 创建并配置 Bot

1. 在 Telegram 中联系 `@BotFather`
2. 执行 `/newbot` 创建机器人
3. 获取 Bot Token
4. 将 Token 写入 `config.yaml`：

```yaml
tools:
  enable_telegram: true
  telegram:
    enabled: true
    bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
    webhook_host: "0.0.0.0"
    webhook_port: 9000
    webhook_path: "/telegram/webhook"
    webhook_secret_token: "YOUR_WEBHOOK_SECRET"
    allowed_chat_ids: [123456789]
    allowed_cidrs: ["149.154.160.0/20", "91.108.4.0/22"]
```

## 2. 启动应用并启动 Webhook 服务

通过 `telegram` 工具执行：

- `start_webhook_server`

启动成功后返回：

- `webhook server 启动成功: <host>:<port><path>`

## 3. 设置 Webhook

执行 `set_webhook`：

- `webhook_url` 示例：`https://your-domain.com/telegram/webhook`

建议与 `webhook_secret_token` 一起使用。

## 4. 双向通信

### 应用主动推送

- `send_message`
- `send_photo`
- `send_document`

### 用户通过 Bot 查询应用数据

默认命令：

- `/help`
- `/sessions`
- `/messages <session_id>`
- `/stats`

## 5. 鉴权与安全

- 启用 `allowed_chat_ids` 限制会话来源
- 启用 `allowed_cidrs` 限制来源网段
- 使用 `register_user` 绑定 Telegram 用户与应用用户
- 使用 `webhook_secret_token` 验证请求头

## 6. 错误处理与日志

- Webhook 层返回标准 JSON 错误码
- 服务层统一捕获异常并回复用户“稍后重试”
- 详细错误写入应用日志，便于排障

## 7. 测试建议

已覆盖的自动化测试：

- 安全校验：secret token 与 IP 白名单
- 消息处理：文本命令、图片、文件
- 数据查询：会话与消息落库读取
- Webhook：端到端接收并异步回包

可在本地执行：

```bash
pytest tests/unit/test_telegram_integration.py -v --tb=short
```
