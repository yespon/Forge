# Forge × DeerFlow 集成计划

## 架构目标

将 DeerFlow 的 Super Agent Harness 能力融入 Forge 的企业平台架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Forge Enterprise Platform                      │
├─────────────────────────────────────────────────────────────────┤
│  Multi-Tenant RBAC │ HITL Approval │ Audit Logging │ Task Queue │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │            Integrated DeerFlow Agent Runtime             │   │
│   │                                                         │   │
│   │  Middleware Chain (14 DeerFlow + Forge Integration)     │   │
│   │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐    │   │
│   │  │TD │ │UP │ │SB │ │SG │ │DT │ │GR │ │TE │ │SM │ │TL │    │   │
│   │  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘    │   │
│   │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐    │   │
│   │
│   │  │MM │ │VI │ │SL │ │LD │ │CL │ │AU │ │HI │ │MT │    │   │
│   │  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘    │   │
│   │                                                         │   │
│   │  Sub-Agent Executor │ MCP Integration │ Skills System   │   │
│   │  Multi-Provider Models │ Tools Registry                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  PostgreSQL │ Redis │ Docker Sandbox │ Feishu/Slack/... Channels│
└─────────────────────────────────────────────────────────────────┘
```

## 集成步骤

### Phase 1: 基础设施 (当前)
- [x] 分析两个项目的架构差异
- [ ] 创建集成层包结构
- [ ] 适配 DeerFlow 的依赖注入到 Forge
- [ ] 统一配置管理

### Phase 2: Agent Runtime
- [ ] 移植 DeerFlow 的 Agent Factory
- [ ] 移植 Middleware Chain (14个中间件)
- [ ] 创建 Forge 集成中间件 (HITL/Audit/Multi-Tenant)
- [ ] 集成 ToolGateway 作为中间件

### Phase 3: Skills & Tools
- [ ] 移植 Skills System (SKILL.md)
- [ ] 移植 Multi-Provider Model Factory
- [ ] 移植 Tools Registry (搜索/文件/Bash)
- [ ] 移植 MCP Integration

### Phase 4: Sub-Agents & Memory
- [ ] 移植 Sub-Agent Executor
- [ ] 移植 Memory System
- [ ] 移植 Summarization
- [ ] 移植 Title Generation

### Phase 5: Channels & Deployment
- [ ] 移植 IM Channels (Feishu/Slack/Telegram/微信/钉钉/企微/Discord)
- [ ] 更新 Docker Compose
- [ ] 更新前端展示新的 Agent 能力
- [ ] 测试与验证