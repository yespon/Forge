# 底层框架选型分析

## 候选框架

### DeerFlow（字节跳动）

- **仓库**: [github.com/bytedance/deer-flow](https://github.com/bytedance/deer-flow)
- **定位**: 企业级 Super Agent Harness，基于 LangChain + LangGraph
- **版本**: 2.0（ground-up 重写）

**架构特点：**

- Gateway API 暴露 LangGraph 兼容路由
- Lead Agent 驱动，可 spawn 隔离 Sub-agent
- Sandbox Provider 抽象（Local / Docker AioSandboxProvider / K8s Provisioner）
- Markdown-based Skill 系统（SKILL.md），按需加载
- MCP Server adapter 支持外部工具
- 上下文工程深度优化（压缩/去重/offload to fs）
- 持久化本地记忆（去重）
- 多 IM Channel 对接（飞书/企微/钉钉/Slack/Telegram/WeChat）
- LangSmith + Langfuse 可观测

**优势：**
- Sandbox Provider 三级抽象成熟
- 6 个 IM Channel 已对接
- Skill 系统完整
- 上下文工程深度好
- Docker Compose / K8s 部署经验

**劣势：**
- 单用户架构，无多租户
- 无异步任务调度
- 无 HITL interrupt
- 无权限系统
- 前端为单用户 UI

---

### DeepAgents（LangChain 官方）

- **仓库**: [github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)
- **定位**: Batteries-included Agent Harness
- **版本**: 0.5.6 (2026-05-01)
- **License**: MIT

**架构特点：**

- `create_deep_agent()` 直接返回编译后的 LangGraph Graph
- 内置工具：Planning (write_todos), Filesystem (read/write/edit/ls/glob/grep), Shell (execute, sandboxed), Sub-agent (task)
- 原生 LangGraph 特性：checkpoint, interrupt (HITL), streaming, Studio 集成
- MCP 集成：via `langchain-mcp-adapters`
- 上下文管理：auto-summarization + save to file
- Persistent memory
- CLI：交互式 TUI + headless mode（CI/scripting）
- 远程 sandbox 支持
- Provider agnostic（任何支持 tool calling 的 LLM）

**优势：**
- LangGraph 原生度最高（compiled graph）
- HITL interrupt 原生支持
- Checkpoint 持久化标准（PostgreSQL 等）
- LangGraph Studio 可直接调试
- 轻量（~98% Python），MIT，易改造
- LangChain 官方维护，生态同步升级

**劣势：**
- 无多用户/多租户
- 无企业级 Sandbox（仅 tool-level sandboxing）
- 无 Skill Registry
- 无 IM Channel 对接
- 无 Web GUI（仅 CLI/TUI）

---

## 对比矩阵

| 维度 | DeerFlow | DeepAgents |
|------|----------|-----------|
| LangGraph 集成度 | 兼容 API | 原生 compiled graph |
| HITL interrupt | ❌ | ✅ 原生 |
| Checkpoint | 文件存储 | LangGraph 原生 (PG) |
| Sandbox | ✅ 三级 Provider | ⚠️ tool-level |
| Skill 系统 | ✅ 完整 | ❌ |
| 多 IM Channel | ✅ 6个 | ❌ |
| Web UI | ✅ React | ❌ |
| TUI/CLI | ❌ | ✅ |
| MCP | ✅ | ✅ |
| Sub-agent | ✅ | ✅ |
| 流式输出 | ✅ | ✅ |
| 可观测 | ✅ LangSmith+Langfuse | ✅ Studio |
| 代码复杂度 | 高 | 低 |
| 维护方 | 字节 | LangChain 官方 |

---

## 其它参考项目

| 项目 | 参考维度 | 链接 |
|------|---------|------|
| E2B | Sandbox 基础设施层（Firecracker，API 驱动） | [github.com/e2b-dev/E2B](https://github.com/e2b-dev/E2B) |
| OpenHands | 多用户 agent runtime + RBAC + K8s 部署 | [github.com/All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands) |
| Coder | 多用户 workspace 管理 & 模板 | [github.com/coder/coder](https://github.com/coder/coder) |
| Composio | 第三方 OAuth 工具集成管理 | [github.com/ComposioHQ/composio](https://github.com/ComposioHQ/composio) |
| LangGraph Platform | 官方 agent 托管（商业） | LangChain 官方 |

---

## 推荐方案

**Skill/Plugin Runtime 自建 + LangGraph/DeepAgents 作为执行图 + DeerFlow 组件移植**

产品主线不是 coding agent，因此不能直接把 DeepAgents 的内置 coding/file/shell 工具作为平台默认能力。DeepAgents/LangGraph 更适合作为底层执行图，承载 checkpoint、interrupt、streaming、sub-agent 和 cron；平台主抽象应是 Skill、Plugin、Connector、Task、Approval 和 Artifact。

### 理由

1. **平台抽象正确**：企业任务以 Skill/Plugin/Connector 为主，不以 bash/file/code 工具为主。
2. **LangGraph 原生**：DeepAgents 是 compiled LangGraph graph，interrupt / checkpoint / Studio / cron 可复用。
3. **HITL 原生**：需求 #11 核心需求，底层 interrupt 能支撑审批暂停和恢复。
4. **Checkpoint 标准**：异步任务暂停/恢复直接依赖 LangGraph checkpoint。
5. **官方维护**：LangGraph 升级时 DeepAgents 第一时间适配。
6. **可组合**：`create_deep_agent()` 返回标准 graph，可嵌入平台自建 Task Runtime。

### 组合策略

```
平台 = 自建 Skill/Plugin Runtime + Task Runtime
     + LangGraph/DeepAgents (执行图、checkpoint、interrupt、stream)
     + DeerFlow 移植 (Sandbox Provider + Skill 包结构 + IM Channel)
     + 自建 (多租户 + 权限传导 + Connector + 通知 + 前端)
```

### 改造工作量估算

| 工作项 | 基于 DeerFlow | 基于 DeepAgents + 移植 |
|--------|:------------:|:--------------------:|
| 多租户层 | 3-4周 | 3-4周 |
| HITL | 3-4周 (从零) | **0周 (原生)** |
| Checkpoint/异步 | 2-3周 | **0周 (原生)** |
| Sandbox | 0周 (已有) | 1-2周 (移植) |
| Skill 系统 | 0周 (已有) | 2-3周 (移植) |
| IM Channel | 0周 (已有) | 2周 (移植) |
| 前端 | 2周 (改) | 4周 (新建) |
| 定时任务 | 3周 | 1周 (LangGraph cron) |
| **总计** | **~14-17周** | **~13-16周** |

工作量相近，但 DeepAgents 方案的 runtime 稳定性更高——HITL 和 checkpoint 是官方实现。
