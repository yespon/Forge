# API 参考文档

## 基础信息

- **Base URL**: `https://api.agent-platform.com/v1`
- **协议**: HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8
- **时间格式**: ISO 8601 (RFC 3339)

## 认证

### Bearer Token

所有 API 请求（除登录外）需要在 Header 中携带 JWT Token：

```
Authorization: Bearer <jwt_token>
```

Token 通过登录接口获取，有效期 2 小时，可使用 refresh token 续期。

### 权限错误

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Token expired or invalid"
  }
}
```

---

## 错误处理

### 错误响应格式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {
      "field": "specific error detail"
    }
  }
}
```

### 错误码列表

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `BAD_REQUEST` | 请求参数错误 |
| 401 | `UNAUTHORIZED` | 未认证或 Token 过期 |
| 403 | `FORBIDDEN` | 权限不足 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` | 资源冲突（如会话已存在） |
| 422 | `VALIDATION_ERROR` | 数据验证失败 |
| 429 | `RATE_LIMITED` | 请求频率超限 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |

---

## 认证接口

### POST /auth/login

用户登录，获取访问令牌。

**请求**: application/json

```json
{
  "username": "alice@company.com",
  "password": "********"
}
```

**响应**: 200 OK

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 7200,
  "user": {
    "id": "user-123",
    "email": "alice@company.com",
    "display_name": "Alice",
    "role": "developer",
    "org": {
      "id": "org-456",
      "name": "Engineering Team"
    }
  }
}
```

---

### POST /auth/refresh

使用 refresh token 获取新的 access token。

**请求**: application/json

```json
{
  "refresh_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**响应**: 200 OK

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "expires_in": 7200
}
```

---

### GET /auth/me

获取当前登录用户信息。

**响应**: 200 OK

```json
{
  "id": "user-123",
  "email": "alice@company.com",
  "display_name": "Alice",
  "role": "developer",
  "permissions": [
    "session:create",
    "task:create",
    "skill:use_public"
  ],
  "quota": {
    "max_concurrent_sessions": 3,
    "max_async_tasks": 10,
    "monthly_token_budget": 1000000,
    "tokens_used_this_month": 234567
  },
  "org": {
    "id": "org-456",
    "name": "Engineering Team",
    "teams": [
      {"id": "team-1", "name": "Backend"},
      {"id": "team-2", "name": "Frontend"}
    ]
  }
}
```

---

## 会话管理 (Sessions)

### POST /sessions

创建新会话。

**请求**: application/json

```json
{
  "title": "数据分析任务",
  "model": "claude-sonnet-4-6",
  "sandbox_template": "python-data-science",
  "initial_message": "帮我分析上周的用户留存数据"
}
```

**响应**: 201 Created

```json
{
  "id": "sess-abc123",
  "title": "数据分析任务",
  "status": "creating",
  "model": "claude-sonnet-4-6",
  "sandbox_id": "sb-xyz789",
  "thread_id": "thread-def456",
  "created_at": "2026-05-03T10:00:00Z",
  "expires_at": "2026-05-04T10:00:00Z",
  "streaming_url": "wss://api.agent-platform.com/v1/sessions/sess-abc123/stream"
}
```

**错误响应**:
- 429: 并发会话数超过限制

---

### GET /sessions

列出用户的会话列表。

**查询参数**:
- `status` (optional): 过滤状态 (active, idle, suspended, all)
- `limit` (optional): 返回数量，默认 20，最大 100
- `offset` (optional): 分页偏移

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "sess-abc123",
      "title": "数据分析任务",
      "status": "active",
      "model": "claude-sonnet-4-6",
      "token_used": 15234,
      "created_at": "2026-05-03T10:00:00Z",
      "last_active_at": "2026-05-03T10:30:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

### GET /sessions/{id}

获取会话详情。

**响应**: 200 OK

```json
{
  "id": "sess-abc123",
  "title": "数据分析任务",
  "status": "active",
  "model": "claude-sonnet-4-6",
  "sandbox_id": "sb-xyz789",
  "thread_id": "thread-def456",
  "token_used": 15234,
  "token_budget": 100000,
  "created_at": "2026-05-03T10:00:00Z",
  "last_active_at": "2026-05-03T10:30:00Z",
  "expires_at": "2026-05-04T10:00:00Z",
  "skills": [
    {"name": "web-search", "version": "1.2.0"},
    {"name": "weekly-summary", "version": "0.1.0"}
  ]
}
```

---

### DELETE /sessions/{id}

结束并删除会话。

**查询参数**:
- `force` (optional): 强制删除，即使正在运行

**响应**: 204 No Content

---

### POST /sessions/{id}/messages

聊天控制面消息。服务端必须创建或绑定 Task，再通过 Task Runtime 执行；Session 不直接拥有执行逻辑。

**请求**: application/json

```json
{
  "content": "汇总本周项目进展并发到飞书群",
  "skill_ids": ["weekly-summary", "feishu-message"],
  "attachments": [
    {
      "name": "data.csv",
      "storage_path": "uploads/user-123/data.csv",
      "mime_type": "text/csv"
    }
  ]
}
```

**响应**: 200 OK (SSE Stream)

```
Content-Type: text/event-stream

id: 1
event: task_status
data: {"task_id": "task-xyz789", "status": "running"}

id: 2
event: tool_call
data: {"task_id": "task-xyz789", "tool": "enterprise_search.query", "input": {"query": "Agent Platform 本周进展"}}

id: 3
event: approval_required
data: {"task_id": "task-xyz789", "approval_id": "appr-123", "tool": "feishu.send_message"}

id: 4
event: message
data: {"task_id": "task-xyz789", "content": "已生成周报，等待发送审批。"}

id: 5
event: done
data: {}
```

---

### WebSocket /sessions/{id}/stream

WebSocket 实时通信（双向）。

**连接**:
```
wss://api.agent-platform.com/v1/sessions/sess-abc123/stream?token=<jwt>
```

**客户端 → 服务器**:
```json
{
  "type": "message",
  "content": "帮我分析数据",
  "attachments": []
}
```

**服务器 → 客户端**:
```json
{
  "type": "thinking",
  "content": "正在分析..."
}
```

```json
{
  "type": "tool_call",
  "tool": "enterprise_search.query",
  "input": {"query": "本周项目进展"}
}
```

```json
{
  "type": "message",
  "content": "分析结果如下...",
  "artifacts": [
    {"name": "report.md", "path": "outputs/report.md"}
  ]
}
```

```json
{
  "type": "approval_required",
  "approval_id": "appr-123",
  "tool": "feishu.send_message",
  "description": "向项目群发送周报摘要",
  "risk_level": "high"
}
```

---

### POST /tasks/{id}/resume

继续被暂停的任务（HITL 审批后由平台内部或审批 API 触发）。

**请求**: application/json

```json
{
  "approval_id": "appr-123",
  "decision": "approved",  // or "rejected"
  "reason": "确认执行"
}
```

**响应**: 200 OK (SSE Stream)

---

## 文件操作

### POST /sessions/{id}/files

上传文件到会话。

**请求**: multipart/form-data

```
file: <binary data>
path: /workspace/uploads/data.csv  // 可选，默认上传到 uploads/
```

**响应**: 201 Created

```json
{
  "name": "data.csv",
  "path": "/workspace/uploads/data.csv",
  "size": 1024567,
  "mime_type": "text/csv",
  "uploaded_at": "2026-05-03T10:15:00Z"
}
```

---

### GET /sessions/{id}/files

列出会话中的文件。

**查询参数**:
- `path` (optional): 目录路径，默认 `/workspace/`

**响应**: 200 OK

```json
{
  "path": "/workspace/",
  "items": [
    {
      "name": "uploads",
      "type": "directory",
      "modified_at": "2026-05-03T10:00:00Z"
    },
    {
      "name": "outputs",
      "type": "directory",
      "modified_at": "2026-05-03T10:30:00Z"
    },
    {
      "name": "report.md",
      "type": "file",
      "size": 4567,
      "mime_type": "text/markdown",
      "modified_at": "2026-05-03T10:30:00Z"
    }
  ]
}
```

---

### GET /sessions/{id}/files/{path}/download

下载文件。

**响应**: 200 OK (binary)

Content-Disposition: attachment; filename="report.md"

---

### DELETE /sessions/{id}/files/{path}

删除文件或目录。

**响应**: 204 No Content

---

## 任务管理 (Tasks)

### POST /tasks

创建任务并按需解析 Skill/Plugin。所有入口最终都创建或绑定 Task，`prompt` 是兼容字段，推荐使用 `intent + skill_ids + inputs`。

**请求**: application/json

```json
{
  "type": "async",
  "intent": "汇总本周项目进展并发到飞书群",
  "skill_ids": ["weekly-summary", "feishu-message"],
  "inputs": {
    "project": "Agent Platform",
    "target_chat_id": "oc_xxx"
  },
  "session_id": "sess-abc123",  // 可选，关联现有会话
  "priority": "normal",  // urgent, normal, background
  "approval_policy": "skill_default",
  "timeout": "24h"
}
```

**响应**: 201 Created

```json
{
  "id": "task-xyz789",
  "type": "async",
  "status": "pending",
  "intent": "汇总本周项目进展并发到飞书群",
  "resolved_skills": [
    {"name": "weekly-summary", "version": "0.1.0"},
    {"name": "feishu-message", "version": "1.0.0"}
  ],
  "requires_authorization": false,
  "priority": "normal",
  "created_at": "2026-05-03T11:00:00Z",
  "position": 3,  // 队列位置
  "estimated_start": "2026-05-03T11:05:00Z",
  "stream_url": "/api/v1/tasks/task-xyz789/stream"
}
```

---

### POST /tasks/scheduled

创建定时任务。

**请求**: application/json

```json
{
  "prompt": "生成每日数据报告",
  "cron": "0 9 * * 1-5",  // 工作日早上 9 点
  "timezone": "Asia/Shanghai",
  "enabled": true
}
```

**响应**: 201 Created

```json
{
  "id": "task-sched-001",
  "prompt": "生成每日数据报告",
  "cron": "0 9 * * 1-5",
  "status": "active",
  "next_run_at": "2026-05-04T09:00:00+08:00",
  "created_at": "2026-05-03T11:00:00Z"
}
```

---

### GET /tasks

列出任务列表。

**查询参数**:
- `type` (optional): async | scheduled
- `status` (optional): pending, running, completed, failed
- `session_id` (optional): 过滤特定会话的任务
- `limit`, `offset` (optional): 分页

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "task-xyz789",
      "type": "async",
      "status": "running",
      "prompt": "分析全量用户数据...",
      "progress": 45,
      "created_at": "2026-05-03T11:00:00Z",
      "started_at": "2026-05-03T11:02:00Z"
    }
  ],
  "total": 10
}
```

---

### GET /tasks/{id}

获取任务详情。

**响应**: 200 OK

```json
{
  "id": "task-xyz789",
  "type": "async",
  "status": "completed",
  "prompt": "分析全量用户数据并生成周报",
  "result_summary": "分析完成，共处理 150 万用户数据...",
  "progress": 100,
  "artifacts": [
    {"name": "weekly_report.md", "path": "outputs/weekly_report.md"},
    {"name": "charts.png", "path": "outputs/charts.png"}
  ],
  "token_used": 52345,
  "created_at": "2026-05-03T11:00:00Z",
  "started_at": "2026-05-03T11:02:00Z",
  "completed_at": "2026-05-03T11:30:00Z"
}
```

---

### GET /tasks/{id}/stream

SSE 流式获取任务输出（用于实时查看后台任务）。

**事件类型**:

| type | 说明 |
|------|------|
| `task_status` | pending/queued/running/waiting_hitl/completed/failed |
| `agent_message` | Agent 可见输出 |
| `tool_call` | Skill/Connector 工具调用 |
| `approval_required` | 等待人工审批 |
| `artifact_created` | 产物已生成 |
| `error` | 错误 |
| `done` | 流结束 |

**响应**: 200 OK (SSE Stream)

---

### POST /tasks/{id}/cancel

取消任务。

**响应**: 200 OK

```json
{
  "id": "task-xyz789",
  "status": "cancelled",
  "cancelled_at": "2026-05-03T11:15:00Z"
}
```

---

### DELETE /tasks/{id}

删除任务（包括历史记录）。

**响应**: 204 No Content

---

### GET /tasks/{id}/artifacts

获取任务产物列表。

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "artifact-1",
      "type": "report",
      "name": "weekly-summary.md",
      "mime_type": "text/markdown",
      "size": 4096,
      "created_at": "2026-05-03T10:12:00Z",
      "download_url": "/api/v1/artifacts/artifact-1/download"
    }
  ]
}
```

---

## 审批管理 (Approvals)

### GET /approvals/pending

获取待处理的审批列表。

**查询参数**:
- `as_approver` (optional): true 表示作为审批人查询，false 作为发起人查询

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "appr-123",
      "task_id": "task-xyz789",
      "tool_name": "feishu.send_message",
      "description": "向项目群发送周报摘要",
      "risk_level": "high",
      "requested_by": {
        "id": "user-123",
        "display_name": "Alice"
      },
      "requested_at": "2026-05-03T12:00:00Z",
      "expires_at": "2026-05-03T16:00:00Z",
      "context": {
        "session_id": "sess-abc123",
        "task_description": "项目周报发送任务"
      }
    }
  ],
  "total": 2
}
```

---

### GET /approvals/{id}

获取审批详情。

**响应**: 200 OK

```json
{
  "id": "appr-123",
  "task_id": "task-xyz789",
  "tool_name": "feishu.send_message",
  "tool_input": {
    "chat_id": "oc_xxx",
    "message_type": "interactive",
    "title": "Agent Platform 周报"
  },
  "risk_level": "high",
  "description": "向项目群发送周报摘要",
  "context_summary": "Agent 已生成周报，准备通过飞书发送到项目群...",
  "status": "pending",
  "requested_by": {
    "id": "user-123",
    "display_name": "Alice",
    "email": "alice@company.com"
  },
  "requested_at": "2026-05-03T12:00:00Z",
  "expires_at": "2026-05-03T16:00:00Z",
  "approvers": [
    {"id": "user-456", "display_name": "Bob", "role": "team_admin"}
  ]
}
```

---

### POST /approvals/{id}

提交审批决策。

**请求**: application/json

```json
{
  "decision": "approved",  // or "rejected"
  "reason": "确认执行，数据已备份"
}
```

**响应**: 200 OK

```json
{
  "id": "appr-123",
  "status": "approved",
  "decision": "approved",
  "decided_by": {
    "id": "user-456",
    "display_name": "Bob"
  },
  "decided_at": "2026-05-03T12:05:00Z",
  "reason": "确认执行，数据已备份"
}
```

---

## Skill/Plugin 管理

### GET /skills

列出当前用户可用 Skills。返回结果已经经过 public/team/private、安装状态、组织策略和用户权限过滤。

**查询参数**:
- `visibility` (optional): public, team, private, all
- `installed_only` (optional): 只返回已安装的

**响应**: 200 OK

```json
{
  "items": [
    {
      "name": "web-search",
      "version": "1.2.0",
      "description": "搜索网络信息",
      "visibility": "public",
      "author": "Platform",
      "capabilities_required": ["network:external"],
      "runtime": {"sandbox": "none"},
      "installed": true,
      "installed_at": "2026-05-01T10:00:00Z"
    },
    {
      "name": "internal-api",
      "version": "0.3.0",
      "description": "调用内部 API",
      "visibility": "team",
      "team": "engineering",
      "capabilities_required": ["network:internal", "secret:API_TOKEN"],
      "hitl": {"write_operations": true},
      "installed": false
    }
  ]
}
```

---

### POST /skills/{name}/install

安装 Skill。安装时平台会校验用户是否有使用权限，并提示需要授权的 Connector、Secret 或审批策略。

**请求**: application/json

```json
{
  "version": "1.2.0",
  "config": {
    "default_engine": "internal_search"
  }
}
```

**响应**: 201 Created

```json
{
  "name": "web-search",
  "version": "1.2.0",
  "status": "installed",
  "capabilities_granted": ["network:external"],
  "requires_authorization": false,
  "installed_at": "2026-05-03T10:00:00Z"
}
```

---

### POST /skills/{name}/uninstall

卸载 Skill。

**响应**: 200 OK

---

### GET /skills/{name}

获取 Skill 详情。

**响应**: 200 OK

```json
{
  "name": "web-search",
  "version": "1.2.0",
  "description": "搜索网络信息",
  "long_description": "支持多搜索引擎...",
  "visibility": "public",
  "author": "Platform Team",
  "capabilities_required": ["network:external"],
  "connectors_required": [],
  "hitl_policy": {
    "default": false,
    "write_operations": []
  },
  "runtime": {
    "sandbox": "none",
    "dependencies": []
  },
  "artifact_types": ["report"],
  "tools": [
    {
      "name": "web_search",
      "description": "执行网络搜索",
      "parameters": {
        "query": {"type": "string", "required": true},
        "limit": {"type": "integer", "default": 10}
      }
    }
  ],
  "installed": true,
  "config": {
    "default_engine": "google",
    "safe_search": true
  }
}
```

---

### POST /skills/{name}/config

配置 Skill 参数。

**请求**: application/json

```json
{
  "default_engine": "bing",
  "safe_search": false
}
```

**响应**: 200 OK

---

## 通知管理

### GET /notifications

获取通知列表。

**查询参数**:
- `unread_only` (optional): 只返回未读
- `types` (optional): 过滤类型，逗号分隔

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "notif-123",
      "type": "approval_required",
      "title": "需要审批",
      "body": "Alice 请求执行高风险操作",
      "payload": {
        "approval_id": "appr-123",
        "task_id": "task-xyz789"
      },
      "read": false,
      "created_at": "2026-05-03T12:00:00Z"
    },
    {
      "id": "notif-124",
      "type": "task_completed",
      "title": "任务完成",
      "body": "数据分析任务已完成",
      "payload": {
        "task_id": "task-xyz789"
      },
      "read": true,
      "created_at": "2026-05-03T11:30:00Z"
    }
  ],
  "unread_count": 1,
  "total": 15
}
```

---

### POST /notifications/{id}/read

标记通知为已读。

**响应**: 200 OK

---

### POST /notifications/read-all

标记所有通知为已读。

**响应**: 200 OK

---

### GET /notifications/settings

获取通知设置。

**响应**: 200 OK

```json
{
  "channels": {
    "in_app": {"enabled": true},
    "feishu": {"enabled": true, "user_id": "u-xxx"},
    "email": {"enabled": false}
  },
  "preferences": {
    "task_completed": ["in_app", "feishu"],
    "approval_required": ["in_app", "feishu", "email"],
    "task_failed": ["in_app"],
    "system_announcement": ["in_app", "email"]
  },
  "quiet_hours": {
    "enabled": true,
    "start": "22:00",
    "end": "08:00",
    "timezone": "Asia/Shanghai"
  }
}
```

---

### PUT /notifications/settings

更新通知设置。

**请求**: application/json

```json
{
  "channels": {
    "feishu": {"enabled": true, "webhook_url": "https://..."}
  },
  "preferences": {
    "task_completed": ["in_app"]
  }
}
```

**响应**: 200 OK

---

## 管理接口 (Admin)

### GET /admin/users

列出组织用户（需 org_admin 权限）。

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "user-123",
      "email": "alice@company.com",
      "display_name": "Alice",
      "role": "developer",
      "status": "active",
      "last_login_at": "2026-05-03T10:00:00Z",
      "quota_usage": {
        "sessions": 2,
        "tasks": 5,
        "tokens": 234567
      }
    }
  ]
}
```

---

### PUT /admin/users/{id}/role

修改用户角色。

**请求**: application/json

```json
{
  "role": "team_admin"
}
```

---

### GET /admin/audit-logs

获取审计日志。

**查询参数**:
- `user_id` (optional)
- `action` (optional): login, session_create, task_create, approval_decide, etc.
- `from`, `to` (optional): 时间范围

**响应**: 200 OK

```json
{
  "items": [
    {
      "id": "log-123",
      "timestamp": "2026-05-03T12:05:00Z",
      "user_id": "user-456",
      "action": "approval_decide",
      "resource_type": "approval",
      "resource_id": "appr-123",
      "details": {
        "decision": "approved",
        "reason": "确认执行"
      },
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0..."
    }
  ],
  "total": 100
}
```

---

### GET /admin/metrics

获取平台指标（需 platform_admin 权限）。

**响应**: 200 OK

```json
{
  "timestamp": "2026-05-03T12:00:00Z",
  "active_sessions": 23,
  "active_sandboxes": 25,
  "queued_tasks": 3,
  "running_tasks": 8,
  "token_usage_last_hour": 1250000,
  "api_requests_per_minute": 150,
  "error_rate": 0.02
}
```

---

## 限流说明

| 接口类型 | 限流策略 |
|---------|---------|
| 认证接口 | 5次/分钟/IP |
| 普通 API | 1000次/分钟/用户 |
| 消息发送 | 60次/分钟/会话 |
| 文件上传 | 10次/分钟/用户，单文件最大 100MB |
| WebSocket | 每个连接保持最多 4 小时 |

超限返回 429，响应头包含:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1714830000
Retry-After: 60
```
