# 数据库详细设计

## 数据库选型

- **主数据库**: PostgreSQL 16
- **缓存/队列**: Redis 7
- **文件存储**: MinIO (S3-compatible)
- **搜索**: PostgreSQL Full-Text Search (初期) → Elasticsearch (后期)

---

## 核心表结构

### 1. 用户与组织

```sql
-- 组织表
CREATE TABLE orgs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(50) UNIQUE NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',  -- active, suspended, deleted
    settings        JSONB DEFAULT '{}',
    -- 配额配置
    quota           JSONB DEFAULT '{
        "max_users": 100,
        "max_sandboxes": 50,
        "max_concurrent_sessions": 30,
        "monthly_token_budget": 10000000
    }',
    -- 计费
    billing_info    JSONB,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ  -- 软删除
);

-- 团队表
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(50) NOT NULL,
    description TEXT,
    settings    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(org_id, slug)
);

-- 用户表
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    external_id     VARCHAR(200),  -- SSO provider ID
    email           VARCHAR(200) NOT NULL,
    display_name    VARCHAR(100),
    avatar_url      VARCHAR(500),
    -- 身份
    role            VARCHAR(30) NOT NULL DEFAULT 'developer',  -- platform_admin, org_admin, team_admin, developer, viewer
    status          VARCHAR(20) DEFAULT 'active',  -- active, inactive, suspended
    -- 个人设置
    settings        JSONB DEFAULT '{
        "default_model": "claude-sonnet-4-6",
        "stream_mode": true,
        "show_thinking": false,
        "notification_channels": ["in_app", "feishu"],
        "quiet_hours": {"enabled": false}
    }',
    -- 个人配额覆盖
    quota_override  JSONB,
    -- 安全
    password_hash   VARCHAR(255),  -- 可选，如果使用 SSO
    mfa_enabled     BOOLEAN DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    login_count     INTEGER DEFAULT 0,
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(org_id, email)
);

-- 用户-团队关联
CREATE TABLE user_teams (
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    team_id     UUID REFERENCES teams(id) ON DELETE CASCADE,
    role        VARCHAR(20) DEFAULT 'member',  -- member, admin
    joined_at   TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, team_id)
);

-- 索引
CREATE INDEX idx_users_org ON users(org_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_external ON users(external_id) WHERE external_id IS NOT NULL;
CREATE INDEX idx_teams_org ON teams(org_id);
```

---

### 2. 会话与 Sandbox

```sql
-- Session 表
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    -- 关联资源
    sandbox_id      VARCHAR(100),  -- Kubernetes pod name 或 container ID
    thread_id       UUID NOT NULL,  -- LangGraph checkpoint thread
    -- 基本信息
    title           VARCHAR(200),
    description     TEXT,
    status          VARCHAR(20) DEFAULT 'creating',  -- creating, active, idle, suspended, archived, error
    channel         VARCHAR(20) DEFAULT 'web',  -- web, tui, feishu, slack, etc.
    -- LLM 配置
    model_config    JSONB DEFAULT '{
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0.7,
        "max_tokens": 4096
    }',
    -- 配额使用
    token_used      BIGINT DEFAULT 0,
    token_budget    BIGINT,  -- NULL = use org default
    message_count   INTEGER DEFAULT 0,
    -- 超时配置
    idle_timeout    INTERVAL DEFAULT '5 minutes',
    max_lifetime    INTERVAL DEFAULT '24 hours',
    -- 时间戳
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_active_at  TIMESTAMPTZ DEFAULT now(),
    suspended_at    TIMESTAMPTZ,
    resumed_at      TIMESTAMPTZ,
    archived_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ DEFAULT (now() + interval '24 hours'),
    -- 元数据
    metadata        JSONB DEFAULT '{}'
);

-- Sandbox 表（运行时元数据）
CREATE TABLE sandboxes (
    id              VARCHAR(100) PRIMARY KEY,  -- pod/container ID
    session_id      UUID REFERENCES sessions(id) ON DELETE SET NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    -- 配置
    template        VARCHAR(50) DEFAULT 'default',
    image           VARCHAR(200) NOT NULL,
    -- 资源
    resources       JSONB DEFAULT '{
        "cpu_request": "0.5",
        "cpu_limit": "2",
        "memory_request": "1Gi",
        "memory_limit": "4Gi",
        "disk_limit": "20Gi"
    }',
    -- 网络策略
    network_policy  JSONB DEFAULT '{
        "egress_allow": [],
        "egress_deny": ["*"]
    }',
    -- 状态
    status          VARCHAR(20) DEFAULT 'creating',  -- creating, running, idle, suspended, terminated, error
    node_name       VARCHAR(100),  -- K8s node
    pod_ip          INET,
    -- 存储
    volume_name     VARCHAR(100),
    volume_size     BIGINT,  -- bytes
    -- 时间戳
    created_at      TIMESTAMPTZ DEFAULT now(),
    started_at      TIMESTAMPTZ,
    last_active_at  TIMESTAMPTZ,
    suspended_at    TIMESTAMPTZ,
    terminated_at   TIMESTAMPTZ,
    termination_reason VARCHAR(100)
);

-- 索引
CREATE INDEX idx_sessions_user_active ON sessions(user_id, status) 
    WHERE status IN ('creating', 'active', 'idle', 'suspended') AND deleted_at IS NULL;
CREATE INDEX idx_sessions_org ON sessions(org_id, created_at DESC);
CREATE INDEX idx_sessions_expires ON sessions(expires_at) 
    WHERE status IN ('active', 'idle');
CREATE INDEX idx_sandboxes_user ON sandboxes(user_id, status);
CREATE INDEX idx_sandboxes_status ON sandboxes(status, created_at) 
    WHERE status IN ('running', 'idle');
```

---

### 3. 任务与调度

```sql
-- 任务表
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES sessions(id) ON DELETE SET NULL,
    -- 任务定义
    type            VARCHAR(20) NOT NULL,  -- sync, async, scheduled, recurring
    mode            VARCHAR(20) DEFAULT 'async',  -- sync, async
    priority        SMALLINT DEFAULT 1,  -- 0=urgent, 1=normal, 2=background
    intent          TEXT NOT NULL,  -- 用户自然语言任务意图
    prompt          TEXT NOT NULL, -- 兼容字段；MVP 可由 intent + Skill 上下文生成
    inputs          JSONB DEFAULT '{}',  -- GUI/Skill 参数输入
    requested_skill_ids JSONB DEFAULT '[]',
    resolved_skills JSONB DEFAULT '[]',  -- [{name, version, skill_id}]
    capability_plan JSONB DEFAULT '{}',  -- connectors/scopes/secrets/sandbox/hitl
    template_id     UUID REFERENCES task_templates(id),
    -- LangGraph
    thread_id       UUID,  -- LangGraph checkpoint thread
    run_id          UUID,  -- current run
    -- 状态
    status          VARCHAR(20) DEFAULT 'pending',  -- pending, queued, running, waiting_hitl, completed, failed, cancelled, timeout
    current_approval_id UUID,
    progress        SMALLINT DEFAULT 0,  -- 0-100
    stage           VARCHAR(100),  -- 当前执行阶段描述
    -- 调度
    scheduled_at    TIMESTAMPTZ,  -- 计划执行时间
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    max_retries     SMALLINT DEFAULT 3,
    retry_count     SMALLINT DEFAULT 0,
    timeout         INTERVAL DEFAULT '1 hour',
    -- 定时任务配置
    cron_expr       VARCHAR(100),
    cron_timezone   VARCHAR(50) DEFAULT 'Asia/Shanghai',
    next_run_at     TIMESTAMPTZ,
    recurrence_end  TIMESTAMPTZ,
    -- 结果
    result_summary  TEXT,
    result_data     JSONB,  -- 结构化结果
    error_message   TEXT,
    error_code      VARCHAR(50),
    error_details   JSONB,
    -- 资源使用
    token_used      BIGINT,
    execution_time  INTERVAL,
    -- 产物
    artifacts       JSONB DEFAULT '[]',  -- [{name, path, size, mime_type}]
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    cancelled_by    UUID REFERENCES users(id),
    cancelled_at    TIMESTAMPTZ,
    cancel_reason   TEXT
);

-- 任务模板表
CREATE TABLE task_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    visibility      VARCHAR(10) DEFAULT 'private',  -- public, team, private
    team_id         UUID REFERENCES teams(id),
    -- 内容
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    icon            VARCHAR(50),  -- emoji or icon name
    prompt_template TEXT NOT NULL,
    variables       JSONB DEFAULT '[]',  -- [{name, type, required, default, description}]
    -- 默认配置
    default_model   VARCHAR(50),
    default_skills  JSONB DEFAULT '[]',
    -- 使用统计
    usage_count     INTEGER DEFAULT 0,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 任务事件表（审计与调试）
CREATE TABLE task_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    event_type  VARCHAR(50) NOT NULL,  -- created, queued, started, tool_called, hitl_requested, resumed, completed, failed, cancelled
    -- 事件详情
    payload     JSONB,
    -- 时间戳
    created_at  TIMESTAMPTZ DEFAULT now()
) PARTITION BY RANGE (created_at);

-- 按时间分区（每月一个分区）
CREATE TABLE task_events_2026_05 PARTITION OF task_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE task_events_2026_06 PARTITION OF task_events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- 索引
CREATE INDEX idx_tasks_user_status ON tasks(user_id, status, created_at DESC);
CREATE INDEX idx_tasks_org ON tasks(org_id, created_at DESC);
CREATE INDEX idx_tasks_session ON tasks(session_id);
CREATE INDEX idx_tasks_scheduled ON tasks(status, scheduled_at) 
    WHERE status IN ('pending', 'scheduled');
CREATE INDEX idx_tasks_next_run ON tasks(next_run_at) 
    WHERE type IN ('scheduled', 'recurring') AND status = 'active';
CREATE INDEX idx_task_events_task ON task_events(task_id, created_at DESC);
CREATE INDEX idx_task_events_type ON task_events(event_type, created_at DESC);
```

---

### 4. HITL 审批

```sql
-- 审批请求表
CREATE TABLE approval_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES tasks(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES sessions(id) ON DELETE SET NULL,
    thread_id       UUID NOT NULL,  -- LangGraph thread
    checkpoint_ns   TEXT,  -- LangGraph checkpoint namespace
    -- 请求内容
    tool_name       VARCHAR(100) NOT NULL,
    tool_input      JSONB NOT NULL,
    tool_input_hash VARCHAR(64),  -- 用于检测重复请求
    risk_level      VARCHAR(10) NOT NULL,  -- low, medium, high, critical
    description     TEXT NOT NULL,
    context_summary TEXT,
    -- 匹配的规则
    rule_matched    VARCHAR(100),
    -- 审批配置
    approvers       JSONB NOT NULL,  -- [{user_id, role, required}]
    strategy        VARCHAR(20) DEFAULT 'single',  -- single, multi, escalation
    min_approvals   SMALLINT DEFAULT 1,
    -- 状态
    status          VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected, expired, escalated
    -- 决策记录
    decisions       JSONB DEFAULT '[]',  -- [{user_id, decision, reason, decided_at}]
    decided_by      UUID REFERENCES users(id),
    final_decision  VARCHAR(20),  -- approved, rejected
    final_reason    TEXT,
    -- 时间戳
    requested_at    TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    decided_at      TIMESTAMPTZ,
    notified_at     TIMESTAMPTZ  -- 通知发送时间
);

-- 审批规则表
CREATE TABLE approval_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    team_id         UUID REFERENCES teams(id),
    -- 规则定义
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    priority        SMALLINT DEFAULT 0,  -- 数字越大优先级越高
    enabled         BOOLEAN DEFAULT TRUE,
    -- 匹配条件
    conditions      JSONB NOT NULL,  -- {tool_name, pattern, args_match, risk_level}
    -- 审批配置
    approvers       JSONB NOT NULL,  -- {type: "user"|"role", id: "user_id"|"team_admin"}
    strategy        VARCHAR(20) DEFAULT 'single',
    auto_approve    BOOLEAN DEFAULT FALSE,  -- 符合条件自动通过
    auto_reject     BOOLEAN DEFAULT FALSE,
    -- 超时配置
    timeout         INTERVAL DEFAULT '4 hours',
    escalation_to   UUID REFERENCES users(id),  -- 升级审批人
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID REFERENCES users(id)
);

-- 索引
CREATE INDEX idx_approvals_task ON approval_requests(task_id);
CREATE INDEX idx_approvals_requester ON approval_requests(session_id, status);
CREATE INDEX idx_approvals_pending ON approval_requests(status, expires_at) 
    WHERE status = 'pending';
CREATE INDEX idx_approvals_user ON approval_requests(status, approvers) 
    WHERE status = 'pending';  -- 需要 GIN 索引
```

---

### 5. Skill 系统

Skill 是平台的核心能力单元。它不仅包含 Agent 可读说明，还声明工具、权限、凭证、HITL、运行环境、UI schema 和产物类型。Plugin 是 Skill 的可安装交付包，可包含一个或多个 Skill、MCP server、工具实现和模板。

```sql
-- Skill 注册表
CREATE TABLE skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 标识
    name            VARCHAR(100) NOT NULL,
    version         VARCHAR(20) NOT NULL,
    -- 归属
    visibility      VARCHAR(10) NOT NULL,  -- public, team, private
    owner_type      VARCHAR(10) NOT NULL,  -- platform, org, team, user
    owner_id        UUID NOT NULL,
    team_id         UUID REFERENCES teams(id),
    -- 元数据
    display_name    VARCHAR(100),
    description     TEXT,
    long_description TEXT,
    author          VARCHAR(100),
    icon            VARCHAR(50),
    tags            JSONB DEFAULT '[]',
    -- 包信息
    registry_ref    VARCHAR(500),  -- OCI registry reference
    package_type    VARCHAR(20) DEFAULT 'skill',  -- skill, plugin, connector_bundle
    source_url      VARCHAR(500),  -- Git repo URL
    checksum        VARCHAR(64),   -- SHA-256
    -- 能力声明
    capabilities_required JSONB DEFAULT '[]',
    connectors_required   JSONB DEFAULT '[]',  -- [{connector, scopes}]
    dependencies    JSONB DEFAULT '[]',  -- [{name, version}]
    runtime_config  JSONB DEFAULT '{}',  -- sandbox/runtime/dependencies/network
    ui_schema       JSONB,  -- GUI 参数表单 schema
    artifact_schema JSONB DEFAULT '[]',  -- [{type, mime_types, export_options}]
    -- HITL 配置
    hitl_config     JSONB,
    -- 统计
    download_count  INTEGER DEFAULT 0,
    rating_sum      INTEGER DEFAULT 0,
    rating_count    INTEGER DEFAULT 0,
    -- 状态
    status          VARCHAR(20) DEFAULT 'active',  -- active, deprecated, disabled, pending_review
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    published_at    TIMESTAMPTZ,
    created_by      UUID REFERENCES users(id),
    UNIQUE(name, version, owner_type, owner_id)
);

-- 用户 Skill 安装记录
CREATE TABLE user_skills (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    skill_id    UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    -- 安装配置
    config      JSONB DEFAULT '{}',
    granted_capabilities JSONB DEFAULT '[]',
    connector_bindings JSONB DEFAULT '{}',  -- {connector_name: connection_id}
    version_locked BOOLEAN DEFAULT FALSE,  -- 是否锁定版本
    auto_update BOOLEAN DEFAULT TRUE,
    -- 状态
    status      VARCHAR(20) DEFAULT 'active',  -- active, disabled, error
    error_message TEXT,
    -- 时间戳
    installed_at TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    UNIQUE(user_id, skill_id)
);

-- Skill 版本历史
CREATE TABLE skill_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id    UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    version     VARCHAR(20) NOT NULL,
    changelog   TEXT,
    registry_ref VARCHAR(500),
    checksum    VARCHAR(64),
    created_at  TIMESTAMPTZ DEFAULT now(),
    created_by  UUID REFERENCES users(id),
    UNIQUE(skill_id, version)
);

-- 索引
CREATE INDEX idx_skills_visibility ON skills(visibility, status) 
    WHERE visibility = 'public' AND status = 'active';
CREATE INDEX idx_skills_owner ON skills(owner_type, owner_id, status);
CREATE INDEX idx_skills_tags ON skills USING GIN(tags);
CREATE INDEX idx_user_skills_user ON user_skills(user_id, status);
```

---

### 5.1 Connector 与权限传导

```sql
-- Connector 注册表，如 feishu、email、calendar、crm、internal_api
CREATE TABLE connectors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    display_name    VARCHAR(100),
    description     TEXT,
    auth_type       VARCHAR(30) NOT NULL,  -- oauth2, api_key, service_account, none
    supported_scopes JSONB DEFAULT '[]',
    config_schema   JSONB DEFAULT '{}',
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 用户/组织连接器授权绑定。密钥本体存 Vault，这里只保存引用。
CREATE TABLE connector_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id    UUID NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    team_id         UUID REFERENCES teams(id) ON DELETE CASCADE,
    visibility      VARCHAR(10) DEFAULT 'user',  -- org, team, user
    scopes          JSONB DEFAULT '[]',
    vault_ref       VARCHAR(500) NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',  -- active, expired, revoked, error
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_connector_connections_user ON connector_connections(user_id, status);
CREATE INDEX idx_connector_connections_org ON connector_connections(org_id, visibility, status);
```

---

### 5.2 Artifact 产物

```sql
CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         UUID REFERENCES tasks(id) ON DELETE SET NULL,
    session_id      UUID REFERENCES sessions(id) ON DELETE SET NULL,
    skill_id        UUID REFERENCES skills(id) ON DELETE SET NULL,
    -- 内容
    type            VARCHAR(50) NOT NULL,  -- report, spreadsheet, document, image, archive, data
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    mime_type       VARCHAR(100),
    storage_ref     VARCHAR(500) NOT NULL, -- MinIO/S3/object storage ref
    size_bytes      BIGINT,
    checksum        VARCHAR(64),
    metadata        JSONB DEFAULT '{}',
    -- 分享与导出
    visibility      VARCHAR(20) DEFAULT 'private', -- private, team, org, public_link
    export_options  JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_artifacts_task ON artifacts(task_id, created_at DESC);
CREATE INDEX idx_artifacts_user ON artifacts(user_id, created_at DESC);
```

---

### 6. 通知系统

```sql
-- 通知表
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    -- 内容
    type        VARCHAR(50) NOT NULL,  -- approval_required, approval_responded, task_completed, task_failed, system_announcement
    title       VARCHAR(200) NOT NULL,
    body        TEXT,
    payload     JSONB,  -- 结构化数据 {task_id, approval_id, ...}
    -- 状态
    read        BOOLEAN DEFAULT FALSE,
    read_at     TIMESTAMPTZ,
    -- 渠道
    channels_sent JSONB DEFAULT '[]',  -- ["in_app", "feishu", "email"]
    channel_status JSONB DEFAULT '{}',  -- {feishu: {message_id, status}}
    -- 时间戳
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ  -- 过期自动清理
) PARTITION BY RANGE (created_at);

-- 按月分区
CREATE TABLE notifications_2026_05 PARTITION OF notifications
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 用户通知设置
CREATE TABLE user_notification_settings (
    user_id     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    -- 渠道配置
    channels    JSONB DEFAULT '{
        "in_app": {"enabled": true},
        "feishu": {"enabled": false, "user_id": null},
        "email": {"enabled": true, "address": null},
        "slack": {"enabled": false, "webhook_url": null}
    }',
    -- 事件偏好
    preferences JSONB DEFAULT '{
        "approval_required": ["in_app", "feishu"],
        "approval_responded": ["in_app"],
        "task_completed": ["in_app"],
        "task_failed": ["in_app", "feishu"],
        "system_announcement": ["in_app", "email"]
    }',
    -- 静默时段
    quiet_hours JSONB DEFAULT '{
        "enabled": false,
        "start": "22:00",
        "end": "08:00",
        "timezone": "Asia/Shanghai"
    }',
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, read, created_at DESC) 
    WHERE read = FALSE;
CREATE INDEX idx_notifications_user_type ON notifications(user_id, type, created_at DESC);
CREATE INDEX idx_notifications_expires ON notifications(expires_at) 
    WHERE expires_at IS NOT NULL;
```

---

### 7. 审计日志

```sql
-- 审计日志表（不可删除，保留长期）
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 时间戳（分区键）
    timestamp       TIMESTAMPTZ DEFAULT now(),
    -- 操作者
    user_id         UUID REFERENCES users(id),
    org_id          UUID REFERENCES orgs(id),
    -- 操作
    action          VARCHAR(50) NOT NULL,  -- login, logout, session_create, session_delete, task_create, task_cancel, approval_decide, skill_install, etc.
    action_category VARCHAR(20),  -- auth, session, task, approval, skill, admin, system
    -- 资源
    resource_type   VARCHAR(50),  -- user, session, task, approval, skill, org
    resource_id     VARCHAR(100),
    -- 详情
    details         JSONB,
    -- 请求上下文
    ip_address      INET,
    user_agent      VARCHAR(500),
    request_id      VARCHAR(100),
    -- 变更前/后（敏感操作）
    before_state    JSONB,
    after_state     JSONB,
    -- 结果
    success         BOOLEAN DEFAULT TRUE,
    error_message   TEXT
) PARTITION BY RANGE (timestamp);

-- 按月分区，保留 2 年
CREATE TABLE audit_logs_2026_05 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- 索引
CREATE INDEX idx_audit_user ON audit_logs(user_id, timestamp DESC);
CREATE INDEX idx_audit_org ON audit_logs(org_id, timestamp DESC);
CREATE INDEX idx_audit_action ON audit_logs(action, timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id, timestamp DESC);
```

---

## 数据保留策略

| 数据类型 | 保留时间 | 清理策略 |
|---------|---------|---------|
| Sessions | 90 天 | 归档到冷存储 |
| Tasks | 1 年 | 归档到冷存储 |
| Task Events | 90 天 | 自动删除 |
| Notifications | 30 天 | 自动删除 |
| Audit Logs | 2 年 | 归档到对象存储 |
| Sandbox logs | 7 天 | 自动删除 |

---

## 关键查询优化

### 1. 活跃会话查询（Dashboard 首页）

```sql
-- 为 Dashboard 优化的查询
CREATE MATERIALIZED VIEW mv_user_sessions_summary AS
SELECT 
    user_id,
    org_id,
    COUNT(*) FILTER (WHERE status IN ('active', 'idle')) as active_count,
    COUNT(*) FILTER (WHERE status = 'suspended') as suspended_count,
    SUM(token_used) as total_tokens,
    MAX(last_active_at) as last_active
FROM sessions
WHERE created_at > now() - interval '30 days'
GROUP BY user_id, org_id;

-- 刷新策略：每 5 分钟或会话状态变更时
CREATE INDEX idx_mv_user_sessions ON mv_user_sessions_summary(user_id);
```

### 2. 待审批查询（审批人 Dashboard）

```sql
-- 使用 GIN 索引优化 approvers 查询
CREATE INDEX idx_approvals_approvers_gin ON approval_requests 
    USING GIN (approvers jsonb_path_ops);

-- 查询示例
SELECT * FROM approval_requests 
WHERE status = 'pending' 
  AND expires_at > now()
  AND approvers @> '[{"user_id": "user-123"}]'::jsonb
ORDER BY requested_at DESC;
```

### 3. 任务队列查询

```sql
-- 优先级队列查询
SELECT * FROM tasks 
WHERE status = 'pending' 
  AND (scheduled_at IS NULL OR scheduled_at <= now())
ORDER BY priority ASC, created_at ASC
LIMIT 100;
```

---

## 连接池配置建议

```yaml
# 后端服务数据库连接池
database:
  pool_size: 20              # 基础连接数
  max_overflow: 30           # 最大溢出
  pool_timeout: 30           # 获取连接超时
  pool_recycle: 1800         # 连接回收时间
  
# 任务 Worker（高并发）
worker_database:
  pool_size: 10
  max_overflow: 20
```
