# 企业 Agent Runtime 平台 — MVP 规划

## MVP 目标

构建一个可运行的多用户 Skill/Plugin Runtime 平台，支持：
- 多用户隔离与基础 RBAC
- Skill/Plugin Registry、安装、权限声明和运行时解析
- Task Runtime 作为所有入口的执行主路径
- 基础 Sandbox 隔离，用于插件执行、临时文件和产物生成
- HITL 审批、飞书通知和任务恢复
- 基础 Web GUI，重点是任务工作台、Skill 选择、审批和产物

MVP 不把 coding 作为默认产品能力。bash/read/write/code-edit 仅作为受限内置 Skill，在明确授权和审计下启用。

第一条验收闭环：

> 用户要求“汇总本周项目进展并发到飞书群”，平台创建 Task，解析 Skill，检查 Connector 授权，触发飞书发送审批，审批后恢复并发送消息，最终生成报告 Artifact 和任务历史。

---

## Phase 1: 基础运行时 (Week 1-4)

### Week 1: 环境搭建与数据模型

**目标**: 建立开发环境，完成核心数据模型和 Skill/Task 主抽象

**任务清单**:
- [ ] 项目初始化 (Monorepo 结构)
- [ ] Docker Compose 开发环境
- [ ] PostgreSQL schema 初始化 (Alembic)
- [ ] 核心表: orgs, users, sessions, tasks, skills, user_skills
- [ ] Skill manifest schema 草案
- [ ] 基础测试数据

**技术栈**:
- Python 3.12 + FastAPI
- PostgreSQL 16
- Alembic migrations
- pytest + testcontainers

**交付物**:
```
backend/
├── alembic/versions/001_initial_schema.py
├── src/core/models.py
├── tests/
└── docker-compose.yml
```

---

### Week 2: 认证与多租户

**目标**: 实现多用户认证与基础权限

**任务清单**:
- [ ] Keycloak 集成 (Docker)
- [ ] JWT token 验证中间件
- [ ] User context 注入
- [ ] 基础 RBAC (org_admin, developer, viewer)
- [ ] API 权限装饰器

**API 实现**:
```python
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me

# 受保护路由
@require_permission("session:create")
POST /api/v1/sessions
```

**交付标准**:
- 可通过 Keycloak 登录获取 token
- API 能识别用户身份与角色
- 跨用户数据隔离验证通过

---

### Week 3: Skill/Plugin Registry 与 Resolver

**目标**: 实现 MVP 主路径的 Skill 管理和运行时解析

**任务清单**:
- [ ] Skill 数据模型和 manifest 校验
- [ ] Skill 安装/卸载 API
- [ ] Skill Resolver: public/team/private 可用性过滤
- [ ] Capability Resolver: 权限、scope、secret、sandbox 要求解析
- [ ] 内置基础 Skill: enterprise-search、document-drafting、feishu-message
- [ ] shell-workspace 作为默认关闭的受限内置 Skill

**核心代码**:
```python
async def resolve_task_capabilities(user, task_request):
    skills = await skill_resolver.resolve(
        user=user,
        task_intent=task_request.intent,
        requested_skill_ids=task_request.skill_ids,
    )
    capability_plan = await permission_engine.plan(user, skills)
    return skills, capability_plan
```

**交付标准**:
- 用户可查看、安装、卸载可用 Skill
- Resolver 能按用户/组织/团队过滤 Skill
- Skill 声明的权限、凭证、HITL 和 sandbox 要求可被解析

---

### Week 4: Task Runtime + LangGraph 执行图

**目标**: 集成 LangGraph/DeepAgents 作为底层执行图，并以 Task 为主路径执行 Skill

**任务清单**:
- [ ] DeepAgents/LangGraph 依赖集成
- [ ] PostgresSaver checkpointer 配置
- [ ] Task 创建、状态机和同步短任务 API
- [ ] Skill docs + tool declarations 注入执行图
- [ ] Tool Gateway: permission → secret → HITL → execute → audit
- [ ] SSE 流式任务事件

**核心流程**:
```python
POST /api/v1/tasks
  → create Task
  → resolve skills/capabilities
  → build task runtime
  → stream task events
```

**API**:
```python
POST /api/v1/tasks
GET  /api/v1/tasks/{id}
GET  /api/v1/tasks/{id}/stream
POST /api/v1/sessions/{id}/messages  # thin wrapper around Task Runtime
```

**交付标准**:
- 可通过 API 发起 Skill 任务
- 流式输出任务状态、工具调用和结果
- 对话历史与任务历史持久化到 PostgreSQL

---

## Phase 2: 隔离、治理与通知 (Week 5-8)

### Week 5: Docker Sandbox 与插件执行隔离

**目标**: 实现 Docker-based Sandbox 隔离，用于插件执行和产物生成

**任务清单**:
- [ ] Docker Sandbox Provider
- [ ] Sandbox 生命周期管理 (create/destroy/reuse)
- [ ] 插件工具在 sandbox 内执行
- [ ] Secret/env 注入
- [ ] 文件上传/下载和 Artifact 注册
- [ ] 默认网络隔离，按 Skill capability 开放

**API**:
```python
POST /api/v1/tasks/{id}/sandbox/create
POST /api/v1/tasks/{id}/sandbox/execute
GET  /api/v1/tasks/{id}/artifacts
```

**交付标准**:
- 插件执行与后端进程隔离
- 文件读写和产物生成被归属到 task
- shell-workspace Skill 默认关闭，开启时经过权限和审计

---

### Week 6: HITL 审批系统

**目标**: 实现 Human-in-the-Loop 审批

**任务清单**:
- [ ] HITL 规则引擎
- [ ] HITLWrappedTool 实现
- [ ] LangGraph interrupt 集成
- [ ] Approval Request 数据模型
- [ ] 审批 API
- [ ] 审批后 Task 恢复或终止

**核心实现**:
```python
# HITL 规则配置
HITL_RULES = [
    {
        "tool_name": "connector.write",
        "pattern": "send_message|update_record|delete_record|batch_update",
        "risk_level": "high",
        "requires_approval": True,
    }
]

# 工具包装
class HITLWrappedTool:
    async def invoke(self, input: dict, config: dict):
        if self._matches_hitl_rule(input):
            approval = interrupt({
                "tool_name": self.name,
                "tool_input": input,
                "risk_level": "high",
            })
            if not approval["approved"]:
                return "操作被拒绝"
        
        return await tool_gateway.execute(self.original_tool, input, config)
```

**API**:
```python
GET  /api/v1/approvals/pending     → 获取待审批列表
POST /api/v1/approvals/{id}        → 提交审批结果
```

**交付标准**:
- 危险操作自动触发审批
- 任务暂停等待审批
- 审批后任务正确恢复或终止

---

### Week 7: 通知系统 (飞书)

**目标**: 实现基础通知，集成飞书

**任务清单**:
- [ ] 通知数据模型
- [ ] 飞书 Bot 接入
- [ ] 交互卡片实现
- [ ] 审批通知推送
- [ ] 任务完成通知

**飞书卡片示例**:
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": true},
    "header": {
      "title": {"tag": "plain_text", "content": "🤖 Agent 请求审批"},
      "template": "red"
    },
    "elements": [
      {"tag": "div", "text": {"tag": "lark_md", "content": "**操作**: DELETE /api/v1/users"}},
      {"tag": "div", "text": {"tag": "lark_md", "content": "**风险**: 🔴 高"}},
      {"tag": "action", "actions": [
        {"tag": "button", "type": "primary", "value": {"action": "approve"}, "text": {"tag": "plain_text", "content": "✅ 通过"}},
        {"tag": "button", "type": "danger", "value": {"action": "reject"}, "text": {"tag": "plain_text", "content": "❌ 拒绝"}}
      ]}
    ]
  }
}
```

**交付标准**:
- 审批自动推送飞书
- 可通过卡片按钮审批
- 任务状态变更通知用户

---

### Week 8: 基础 GUI

**目标**: 实现基础 Web GUI

**任务清单**:
- [ ] React + TypeScript 项目初始化
- [ ] 登录页面
- [ ] Agent 工作台基础布局
- [ ] 对话界面 (流式输出)
- [ ] Session 列表
- [ ] 审批面板

**页面结构**:
```
App
├── Login
├── Layout
│   ├── Sidebar (Sessions, Tasks, Skills)
│   └── Main Content
│       ├── Chat (对话界面)
│       ├── TaskList
│       └── ApprovalList
```

**交付标准**:
- 用户可通过 GUI 登录
- 可发起对话并看到流式输出
- 可查看和处理审批请求

---

## Phase 3: 完整 MVP (Week 9-12)

### Week 9: 企业 Connector 与凭证传导

**目标**: 实现企业系统连接器和用户权限传导

**任务清单**:
- [ ] Connector Registry 数据模型
- [ ] OAuth/Token Broker 抽象
- [ ] 飞书 Connector 首版
- [ ] 内部 API Connector 模板
- [ ] Connector scope 与 Skill capability 映射
- [ ] 凭证访问审计

**API**:
```python
GET  /api/v1/connectors
POST /api/v1/connectors/{id}/authorize
GET  /api/v1/connectors/{id}/status
```

---

### Week 10: Artifact 与任务历史

**目标**: 沉淀任务结果、产物和可复用历史

**任务清单**:
- [ ] Artifact 数据模型
- [ ] 文档/表格/附件产物注册
- [ ] 任务执行链查询
- [ ] “基于此任务继续”接口
- [ ] 产物导出/分享基础能力

---

### Week 11: 管理后台

**目标**: 实现管理功能

**任务清单**:
- [ ] 用户管理
- [ ] 组织/团队管理
- [ ] 配额配置
- [ ] 审计日志查看
- [ ] 系统监控 Dashboard

---

### Week 12: 集成测试 & 优化

**目标**: 确保 MVP 稳定可用

**任务清单**:
- [ ] 端到端测试
- [ ] 性能测试
- [ ] 安全审计
- [ ] 文档完善
- [ ] 部署脚本

---

## MVP 功能清单

### ✅ 包含功能

| 需求 | 功能 | 优先级 |
|------|------|--------|
| 1 | Skill/Plugin Runtime + LangGraph 执行图 | P0 |
| 2 | 多用户 + 基础 RBAC | P0 |
| 3 | Docker Sandbox 插件隔离 | P0 |
| 4 | 基础权限隔离 | P0 |
| 5 | Skill Registry + public/team/private 基础隔离 | P0 |
| 7 | Task Runtime + 异步任务 + HITL 审批 | P0 |
| 8 | 基础 Web GUI | P1 |
| 10 | MCP/Connector/Tool Registry 基础 | P0 |
| 11 | HITL (interrupt + task resume) | P1 |
| 12 | 每用户 3 并发 session | P1 |
| 13 | 流式输出 | P1 |
| 15 | 飞书通知 | P1 |
| 17 | Artifact 基础管理 | P1 |
| 6 | 基础日志 + 审计 | P2 |

### ❌ 不包含功能 (后续迭代)

| 需求 | 功能 | 计划 |
|------|------|------|
| 7 | Cron 定时任务高级策略 | Phase 4 |
| 9 | TUI 模式 | Phase 4 |
| 14 | Sandbox 控制台完整版 | Phase 4 |
| 16 | 任务模板 | Phase 5 |
| 17 | 产物管理完整版、分享权限 | Phase 5 |
| 18 | 任务历史重放 | Phase 5 |
| 19 | Sub-agent | Phase 6 |
| 20 | 多 Channel (除飞书外) | Phase 6 |
| 21-26 | 高级功能 | Phase 7+ |

---

## 技术栈总结

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript 5 + TailwindCSS |
| 后端 | Python 3.12 + FastAPI |
| Runtime | Skill/Plugin Runtime + Task Runtime |
| Agent 执行图 | LangGraph/DeepAgents |
| 数据库 | PostgreSQL 16 |
| 缓存/队列 | Redis 7 |
| 认证 | Keycloak (OIDC) |
| Sandbox | Docker |
| 部署 | Docker Compose |
| 测试 | pytest + Playwright |

---

## 成功标准

- [ ] 支持 10+ 并发用户
- [ ] 首 token 响应 < 3s
- [ ] Sandbox 启动 < 5s
- [ ] 任务成功率 > 95%
- [ ] HITL 审批流程完整可用
- [ ] 飞书通知正常送达
