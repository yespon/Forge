# IM Channels

## Configured Channels
- **Feishu/Lark** - WebSocket + event subscription
- **Slack** - Socket Mode
- **Telegram** - Bot API polling
- **DingTalk** - Stream mode
- **WeChat** - iLink protocol
- **Discord** - Gateway bot
- **WeCom** - Bot HTTP callbacks

## Architecture
```
MessageBus (pub/sub)
  ├── Inbound: channels → agent
  └── Outbound: agent → channels
```
