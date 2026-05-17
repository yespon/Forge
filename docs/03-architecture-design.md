# 企业 Agent Runtime 平台 — 详细架构设计

## 设计定位

平台是企业内的 Skill/Plugin Runtime + Task Runtime。它借鉴 Codex 的端云一体体验，但默认不以 coding 为核心能力。Agent 的默认工作方式是解析任务意图、选择并组合已授权 Skill/Plugin/Connector，在受控任务运行时中执行企业和个人任务。

因此，bash、文件读写、代码编辑、shell 等能力不属于默认工具集，只能作为受限内置 Skill 或特定插件启用。所有工具调用都必须经过权限解析、凭证注入、HITL 策略检查、审计日志和可观测链路。

## 一、系统全景

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           接入层 (Ingress Layer)                              │
│                                                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ┌───────────┐ │
│  │ Web  │ │ TUI  │ │飞书  │ │企微  │ │钉钉  │ │ Slack    │ │ API/SDK   │ │
│  │ GUI  │ │ CLI  │ │ Bot  │ │ Bot  │ │ Bot  │ │ Bot     │ │ (Headless)│ │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘ └─────┬─────┘ │
└─────┼────────┼────────┼────────┼────────┼──────────┼─────────────┼────────┘
      │        │        │        │        │          │             │
      └────────┴────────┴────────┴────────┴──────────┴─────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                         API Gateway (自建)                                    │
│                                                                             │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Auth   │ │  Rate    │ │ Protocol  │ │ Channel  │ │  WebSocket/SSE   │ │
│  │  OIDC   │ │  Limit   │ │ Adapter   │ │ Context  │ │  Stream Manager  │ │
│  └─────────┘ └──────────┘ └───────────┘ └──────────┘ └──────────────────┘ │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                       业务编排层 (Task Orchestration)                         │
│                                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐ │
│  │   Session    │ │    Task      │ │Skill Resolver│ │   HITL Approval    │ │
│  │   Manager    │ │   Runtime    │ │+ Permission  │ │     Engine         │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
┌─────────▼────────────────▼────────────────▼────────────────────▼────────────┐
│                       Agent Runtime Layer (执行图)                            │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    LangGraph / DeepAgents Engine                      │   │
│  │  Task → Skill Context → Tool Plan → Compiled LangGraph Graph         │   │
│  │  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌───────────────────────┐ │   │
│  │  │ Planning  │ │ Context  │ │ Skill Docs│ │ Tool/Connector Router │ │   │
│  │  │ Task steps│ │ Summarize│ │  SKILL.md │ │ Permission + HITL     │ │   │
│  │  └───────────┘ └──────────┘ └───────────┘ └───────────────────────┘ │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │  LangGraph Runtime: checkpoint │ interrupt │ stream │ cron   │   │   │
│  │  └───────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌────────────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ Skill/Plugin Registry  │  │      Tool/Connector Registry             │   │
│  │ public │ team │ private│  │ builtin-skill │ MCP │ SaaS │ internal  │   │
│  └────────────────────────┘  └──────────────────────────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│                      Sandbox Layer (执行隔离层)                               │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              Sandbox Provider (移植自 DeerFlow)                       │   │
│  │  ┌────────────┐  ┌─────────────────┐  ┌──────────────────────────┐  │   │
│  │  │   Local    │  │  Docker (Aio)   │  │   Kubernetes (Pods)      │  │   │
│  │  │ (dev only) │  │  (default)      │  │   (production)           │  │   │
│  │  └────────────┘  └─────────────────┘  └──────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Per-Sandbox:  filesystem │ env_vars │ network policy │ resource cap │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│                      基础设施层 (Infrastructure)                              │
│                                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌───────┐ ┌─────────────────┐ │
│  │ Postgres│ │ Redis  │ │ MinIO  │ │ Vault │ │Prom/  │ │ Kubernetes      │ │
│  │ (state)│ │(queue) │ │(files) │ │(secret│ │Grafana│ │ (orchestration) │ │
│  └────────┘ └────────┘ └────────┘ └───────┘ └───────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块详细设计

### 2.1 API Gateway

**路由设计：**

```python
# 核心 API 路由
POST /api/v1/tasks                 → 创建任务（同步短任务/异步长任务）
GET  /api/v1/tasks/{id}            → 查询任务
GET  /api/v1/tasks/{id}/stream     → SSE 流式输出
GET  /api/v1/tasks/{id}/artifacts  → 查询任务产物
POST /api/v1/sessions              → 创建会话
POST /api/v1/sessions/{id}/message → 聊天控制面（内部创建/绑定 Task）
GET  /api/v1/skills                → 查询可用 Skill
POST /api/v1/skills/{id}/install   → 安装 Skill
GET  /api/v1/connectors            → 查询 Connector 授权状态
POST /api/v1/approvals/{id}        → HITL 审批响应
GET  /api/v1/notifications         → 通知拉取
WS   /api/v1/ws/{session_id}       → WebSocket 双向通信

# Channel Webhook 接入
POST /api/v1/channels/feishu/webhook
POST /api/v1/channels/slack/events
POST /api/v1/channels/dingtalk/callback
```

**统一消息格式：**

```python
@dataclass
class InternalMessage:
    id: str
    user_id: str
    org_id: str
    session_id: str
    channel: ChannelType          # WEB | TUI | FEISHU | SLACK | ...
    content: str
    attachments: list[Attachment]  # 文件/图片
    metadata: dict                # channel-specific context
    created_at: datetime

@dataclass
class ChannelContext:
    channel_type: ChannelType
    capabilities: set[str]       # {"rich_text", "card", "button", "file_upload"}
    reply_format: str            # "markdown" | "feishu_card" | "slack_block"
    supports_streaming: bool
    supports_interaction: bool
```

---

### 2.1.1 MVP 企业任务闭环

MVP 第一条闭环以“汇总本周项目进展并发到飞书群”为验收场景：

1. Web/Chat/API 创建 Task。
2. Skill Resolver 解析 `weekly-summary`、`enterprise-search`、`feishu-message`。
3. Capability Planner 检查安装状态、飞书 Connector 授权、内部知识库 scope、HITL 策略。
4. Task Runtime 构建 LangGraph/DeepAgents 执行图，注入 Skill 文档和受控 gateway tools。
5. Tool Gateway 执行 Skill 工具，连接器 token 只通过 Secret Broker 注入到底层 Connector。
6. 发送飞书群消息前触发 ApprovalRequest，Task 进入 `waiting_hitl`。
7. 审批通过后 Task 恢复并完成发送。
8. 平台写入 task_events、audit log、notification 和 Artifact metadata。

这条闭环优先于完整插件市场、复杂工作流和 coding workspace。

---

### 2.2 Session Manager

**Session 状态机：**

```
Creating → Active → Idle(5min) → Suspended → Archived
             │         │            │
             │         └────────────┘
             │              │ resume
             │              ▼
             └────→ Waiting Approval → (approved) → Active
                          │
                          └──→ (timeout/rejected) → Failed
```

**并发控制：**

```yaml
per_user:
  max_active_sessions: 3
  max_async_tasks: 10
  total_cpu: "8 cores"
  total_memory: "16Gi"

per_org:
  max_total_sandboxes: 50
  monthly_token_budget: 10_000_000

queue_overflow_strategy: "reject" | "queue"
```

---

### 2.3 Skill/Plugin Task Runtime 核心

**任务执行创建流程：**

```python
async def create_task_runtime(user, session, task, request) -> TaskRuntime:
    # 1. 根据自然语言、入口 channel 或显式选择解析 Skill
    skills = await skill_resolver.resolve(
        user=user,
        org_id=user.org_id,
        task_intent=request.intent,
        requested_skill_ids=request.skill_ids,
    )

    # 2. 解析权限、第三方授权和凭证注入策略
    capability_plan = await permission_engine.plan(
        user=user,
        skills=skills,
        requested_scopes=request.scopes,
    )
    
    # 3. 根据 Skill 声明创建或复用 Sandbox
    sandbox = await sandbox_provider.ensure_for_task(
        user_id=user.id,
        task_id=task.id,
        runtime_requirements=skills.runtime_requirements,
        env_vars=await secret_broker.resolve_env(capability_plan),
        network_policy=capability_plan.network_policy,
    )
    
    # 4. 组合 Skill 文档、工具、连接器和 HITL 策略
    tools = await tool_router.build_tools(
        user=user,
        task=task,
        skills=skills,
        sandbox=sandbox,
        capability_plan=capability_plan,
    )
    system_prompt = await prompt_builder.from_skills(skills, task)
    
    # 5. 创建 LangGraph/DeepAgents 执行图
    graph = create_deep_agent(
        model=_get_llm(config.model, user),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=PostgresSaver(conn_string=DB_URL),
    )
    
    return TaskRuntime(graph=graph, sandbox=sandbox, skills=skills)
```

**工具调用网关：**

所有 Skill/Plugin 工具调用都经过统一网关，而不是由 Agent 直接调用底层函数：

```
Agent Tool Call
  → Tool Router
  → Permission Check
  → Secret Broker / OAuth Token Broker
  → HITL Policy Check
  → Sandbox or Connector Execution
  → Audit Log + Trace + Artifact Registration
```

**HITL 工具包装：**

```python
class HITLWrappedTool:
    """包装工具，在执行前检查是否需要审批"""
    
    async def invoke(self, input: dict, config: dict) -> Any:
        matched_rule = self._check_rules(input)
        
        if matched_rule:
            approval = interrupt({
                "type": "approval_request",
                "tool_name": self.name,
                "tool_input": input,
                "risk_level": matched_rule.risk_level,
                "approvers": matched_rule.get_approvers(config),
                "timeout": matched_rule.timeout,
            })
            
            if not approval.get("approved"):
                return f"操作被拒绝: {approval.get('reason')}"
        
        return await tool_gateway.execute(self.original_tool, input, config)
```

---

### 2.4 Task Scheduler

Task Runtime 是所有入口的执行主路径。Web Chat、TUI、飞书 Bot、API/SDK 都只负责创建任务、补充上下文、显示进度或提交审批。同步对话是短任务的一种表现形式，不是唯一执行模型。

**任务类型：**

```yaml
Synchronous:  # 用户在线等待
  timeout: 5min
  
Asynchronous:  # 后台执行
  timeout: 24h
  
Scheduled:  # Cron 触发
  cron: "0 9 * * 1-5"
  
Recurring:  # 循环轮询
  interval: "5m"
  until: condition_met
```

**状态机：**

```
Pending → Queued → Running → Completed
            │          │
            │          ├──→ Waiting HITL → (approved) → Running
            │          │                    │
            │          │                    └──→ Timeout → Failed
            │          │
            │          └──→ Failed → (retry?) → Dead
            │
            └──→ Cancelled
```

---

### 2.5 Sandbox Provider

**三级 Provider 实现：**

```python
class SandboxProvider(ABC):
    async def create(config: SandboxConfig) -> Sandbox
    async def destroy(sandbox_id: str)
    async def suspend(sandbox_id: str)
    async def resume(sandbox_id: str) -> Sandbox
    async def list(user_id: str) -> list[SandboxInfo]

class LocalSandboxProvider:      # 开发模式
class DockerSandboxProvider:     # 默认模式
class KubernetesSandboxProvider: # 生产模式
```

**Sandbox 内部结构：**

```
/workspace/          ← persistent (用户工作区)
/workspace/outputs/  ← 产物输出目录
/workspace/uploads/  ← 用户上传文件
/tmp/                ← ephemeral
/mnt/skills/         ← readonly (public+team skills)
/mnt/user-skills/    ← readonly (private skills)
```

**环境变量注入（三级）：**

```yaml
Platform:  # 管理员配置
  LLM_API_KEY: sk-xxx
  
Team:      # 团队管理员配置
  INTERNAL_API_BASE: https://api.internal.com
  
User:      # 个人配置
  GITHUB_TOKEN: ghp_xxx
  FEISHU_USER_TOKEN: t-xxx
```

---

### 2.6 Skill & Tool Registry

Skill/Plugin Registry 是 MVP P0 模块。它负责回答“用户能用哪些能力、每个能力需要什么权限、需要什么凭证、在哪运行、哪些步骤需要审批、会产出什么结果”。

**Skill 存储层级（OCI Registry）：**

```
registry/
├── public/                     # 平台级
│   ├── web-search:1.2.0
│   └── document-drafting:1.0.0
├── team-engineering/           # 团队级
│   └── internal-api:0.3.0
└── user-alice/                 # 个人级
    └── weekly-summary:0.1.0
```

**Skill 包结构：**

```yaml
my-skill/
├── skill.yaml          # 元数据 + 权限声明
├── SKILL.md            # Agent 可读的 skill 文档
├── ui.schema.json      # 可选: GUI 参数表单
├── tools/              # 工具实现
│   └── query.py
├── mcp_server/         # 可选: 独立 MCP server
│   └── server.py
├── prompts/            # 技能提示模板
│   └── default.md
├── artifacts/          # 产物声明和导出模板
│   └── report.schema.json
└── tests/
```

**skill.yaml 示例：**

```yaml
name: internal-api-client
version: 0.3.0
visibility: team
team: engineering

capabilities_required:
  - network:internal
  - secret:API_TOKEN
  - connector:internal_api.read

hitl:
  default: false
  dangerous_patterns:
    - "DELETE /api/v1/*"
  write_operations:
    - tool: query_api
      method: DELETE
      approval: team_admin

sandbox:
  isolation: task
  runtime: python3.11
  dependencies:
    - httpx>=0.25

tools:
  - name: query_api
    description: "Query internal API endpoints"
    entrypoint: tools.query:query_api

artifacts:
  - type: report
    mime_types: ["text/markdown", "application/pdf"]
```

**内置 Skill 策略：**

```yaml
builtin_skills:
  document_drafting:
    default_enabled: true
  enterprise_search:
    default_enabled: true
  feishu_actions:
    default_enabled: false
    requires_oauth: true
  shell_workspace:
    default_enabled: false
    reason: "coding/file/bash 能力仅对明确授权用户和任务开放"
```

---

### 2.7 权限系统

**RBAC 角色定义：**

```yaml
platform_admin:
  - admin:*

org_admin:
  - org:manage_members, org:manage_billing
  - skill:publish_public
  - sandbox:view_all

team_admin:
  - team:manage_members, team:manage_secrets
  - skill:publish_team
  - approval:approve_team

developer:
  - session:create, session:manage_own
  - task:create, task:manage_own
  - skill:use_public, skill:use_team, skill:manage_private
  - sandbox:create, sandbox:manage_own
  - secret:manage_own
  - mcp:register_own

viewer:
  - session:view_shared
  - skill:use_public
```

**第三方 OAuth 代理：**

```
用户授权流:
  User → Platform OAuth Page → 第三方 OAuth (飞书/GitHub)
       → 获取 access_token + refresh_token → 存入 Vault

Agent 调用流:
  Agent Tool Call → Permission Check → Token from Vault
                  → Scope Narrowing (降权) → Execute API Call
                  → Audit Log
```

---

### 2.8 可观测性

**三大支柱：**

```yaml
Metrics (Prometheus):
  - agent_runtime_active_sessions{org, team}
  - agent_runtime_sandbox_count{status}
  - agent_runtime_task_total{type, status}
  - llm_request_duration_seconds{model, provider}
  - llm_token_usage_total{model, user_id}

Traces (OpenTelemetry → Tempo):
  - session_request → gateway.auth → session.resolve → agent.invoke
    → llm.call → tool_gateway → connector/sandbox → response.stream

Logs (Loki):
  - Agent 推理日志
  - Tool 执行日志
  - 安全审计日志（不可关闭）
```

---

## 三、数据架构

### 3.1 核心表结构

```sql
-- 用户与组织
CREATE TABLE orgs (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    quota JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs(id),
    external_id VARCHAR(200),
    email VARCHAR(200),
    display_name VARCHAR(100),
    role VARCHAR(30) NOT NULL DEFAULT 'developer',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Session
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    org_id UUID NOT NULL REFERENCES orgs(id),
    sandbox_id UUID,
    langgraph_thread_id UUID NOT NULL,
    agent_config_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'creating',
    token_used BIGINT DEFAULT 0,
    token_budget BIGINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_active_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

-- Task
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    org_id UUID NOT NULL REFERENCES orgs(id),
    session_id UUID REFERENCES sessions(id),
    type VARCHAR(20) NOT NULL,  -- sync | async | scheduled | recurring
    priority SMALLINT DEFAULT 1,
    prompt TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress SMALLINT DEFAULT 0,
    cron_expr VARCHAR(100),
    timeout INTERVAL DEFAULT '1 hour',
    result_summary TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Approval
CREATE TABLE approval_requests (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    thread_id UUID NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    tool_input JSONB NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    approvers JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ
);
```

---

## 四、部署架构

### 4.1 Kubernetes 部署

```yaml
# Namespace: platform
Deployments:
  - api-gateway (3 pods)
  - session-manager (2 pods)
  - task-scheduler (2 pods)
  - notification-engine (2 pods)
  - agent-workers (HPA 3-20)
  - skill-loader (2 pods)
  - approval-engine (2 pods)
  - channel-workers (per-channel)

# Namespace: sandboxes
Sandbox Pods:
  - Per-user sandbox (gVisor runtime)
  - Warm pool controller

# Namespace: infra
Stateful Services:
  - PostgreSQL (HA, 3 node)
  - Redis (Cluster)
  - MinIO (HA)
  - Vault (HA, auto-unseal)
  - Keycloak (Auth)
  - Harbor (Registry)
  - Prometheus + Grafana + Tempo
```

---

## 五、关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 核心 | DeepAgents (LangGraph) | HITL interrupt + checkpoint 原生 |
| Sandbox 隔离 | gVisor on K8s | 生产级隔离，Pod 级管理 |
| 状态持久化 | PostgreSQL | 事务一致性，checkpoint 原生支持 |
| 任务队列 | Redis Streams | 轻量、支持消费组、优先级 |
| 认证 | Keycloak (OIDC) | 企业 SSO 集成成熟 |
| Secrets | HashiCorp Vault | 加密存储 + 动态 secret + 审计 |
| 文件存储 | MinIO (S3 兼容) | 自托管、产物管理 |
| 前端 | React + TypeScript | 生态成熟，适合复杂 SPA |
| 可观测 | OpenTelemetry + Prometheus | 云原生标准 |
| 部署 | Kubernetes + Kustomize | 多环境管理，HPA 弹性伸缩 |
