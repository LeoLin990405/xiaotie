# Telegram 集成 API

## 概览

Telegram 集成由以下模块组成：

- `xiaotie.telegram.client.TelegramBotClient`
- `xiaotie.telegram.service.TelegramIntegrationService`
- `xiaotie.telegram.webhook.TelegramWebhookServer`
- `xiaotie.tools.telegram_tool.TelegramTool`

## 配置项

在 `config.yaml` 中新增：

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

## Tool 接口

`telegram` 工具支持以下 action：

- `get_me`
- `set_webhook`
- `get_webhook_info`
- `delete_webhook`
- `start_webhook_server`
- `stop_webhook_server`
- `send_message`
- `send_photo`
- `send_document`
- `process_update`
- `register_user`

## 请求参数

### set_webhook

- `action`: `set_webhook`
- `webhook_url`: 公开可访问 HTTPS URL
- `drop_pending_updates`: 可选，默认 `false`

### send_message

- `action`: `send_message`
- `chat_id`: Telegram chat id
- `text`: 文本内容

### send_photo

- `action`: `send_photo`
- `chat_id`: Telegram chat id
- `photo`: 图片 URL 或 file_id
- `caption`: 可选

### send_document

- `action`: `send_document`
- `chat_id`: Telegram chat id
- `document`: 文件 URL 或 file_id
- `caption`: 可选

### process_update

- `action`: `process_update`
- `update`: Telegram Update JSON 对象

### register_user

- `action`: `register_user`
- `telegram_user_id`: Telegram 用户 ID
- `app_user_id`: 应用侧用户 ID

## 返回结构

所有 action 返回 `ToolResult`：

- `success`: `true/false`
- `content`: JSON 字符串或文本说明
- `error`: 失败时错误描述

## 安全机制

- Webhook Header 校验：`X-Telegram-Bot-Api-Secret-Token`
- 源 IP 网段白名单：`allowed_cidrs`
- 会话白名单：`allowed_chat_ids`
- 用户绑定鉴权：`register_user` + `user_auth_map`

## 高并发处理

- Webhook 服务器采用 `ThreadingHTTPServer` 并发处理请求
- 每个请求通过事件循环异步调度到 `TelegramIntegrationService`
- 性能回归通过 CI 门禁控制
