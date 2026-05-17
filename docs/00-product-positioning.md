# 产品定位与 Brainstorm 结论

## 一句话定位

企业内的端云一体 Agent 任务平台。它像 Codex 一样提供持续会话、任务运行时、工具调用、审批、通知和产物管理，但默认目标不是 coding，而是通过 Skill、Plugin、MCP 和企业系统连接器完成个人与企业任务。

---

## 设计边界

### 是什么

- 面向企业和个人任务的 Skill/Plugin Runtime。
- 多用户、多租户、可审计、可审批、可长程执行的 Agent OS。
- 能代表用户在飞书、知识库、工单、CRM、报表、日程、邮件、内部 API 等系统中完成任务。
- 支持 GUI/TUI/IM/API 多入口，但统一落到同一套 Task Runtime。
- Sandbox 是任务执行和插件隔离环境，不是默认代码工作区。

### 不是什么

- 不是默认 coding agent。
- 不是把 bash、文件读写、代码编辑作为核心能力的平台。
- 不是 Dify 式工作流编排器，工作流可以作为 Skill 或模板存在，但不是核心抽象。
- 不是单纯 chatbot，聊天只是发起、澄清、观察和控制任务的一种界面。

---

## Brainstorm 后的核心洞察

1. Skill/Plugin 是产品主语。
   Agent Runtime 的第一步不是加载 bash/read/write，而是根据用户、组织、任务意图和安装状态解析可用 Skill，并把 Skill 声明的工具、权限、凭证、HITL 策略和运行环境组装成一次可执行任务。

2. 权限传导是企业价值的关键。
   每次工具调用都必须回答“代表谁调用、调用哪个系统、使用什么 scope、是否需要审批、审计归属是谁”。OAuth token、企业内部 token、API key 和敏感配置必须通过 Secret Broker/Vault 注入，不能由 Agent 明文持有。

3. Task Runtime 是主路径，Chat 是控制面。
   企业任务经常等待外部系统、审批、定时触发、失败重试或长时间运行，因此同步对话不能是唯一执行模型。所有入口都应该创建或绑定 Task，Task 再驱动 Agent/Skill 执行。

4. Sandbox 是隔离边界，不是产品目标。
   Sandbox 用于插件运行、文件暂存、依赖隔离、网络策略、数据脱敏和产物生成。coding/file/bash 能力可以作为受限 Skill 出现，但不能默认暴露给所有 Agent。

5. HITL 是写操作治理，不是附加功能。
   任何跨系统写操作、批量变更、外发消息、删除/修改数据、权限提升、敏感数据访问，都应能由 Skill 声明审批规则并由平台统一执行。

6. 产物、历史、可观测性是企业任务闭环。
   任务完成后要留下可复用的历史、结构化结果、附件、审计日志、成本和可观察链路，而不是只保留一段聊天记录。

---

## 重排后的核心抽象

| 抽象 | 职责 |
|------|------|
| Skill | 面向 Agent 的能力说明、提示、工具声明、权限声明、HITL 规则和运行时要求 |
| Plugin | Skill 的可安装包，可包含 MCP server、工具实现、UI schema、prompt、依赖和测试 |
| Connector | 企业或第三方系统连接器，如飞书、邮件、日历、CRM、知识库、内部 API |
| Task | 一次可追踪的任务运行，支持同步、异步、定时、循环、暂停审批和恢复 |
| Session | 用户与 Agent 的持续上下文，用于发起、澄清、观察和继续任务 |
| Sandbox | 插件执行和文件/产物隔离环境 |
| Approval | 对高风险工具调用、跨系统写操作和敏感数据访问的人工确认 |
| Artifact | Agent/Skill 生成的文档、表格、报告、附件、数据结果或导出包 |

---

## MVP 主路径

MVP 的第一条演示闭环是企业任务闭环：

> 用户要求“汇总本周项目进展并发到飞书群”，平台创建 Task，解析 weekly-summary、enterprise-search、feishu-message 等 Skill，检查飞书授权和写操作审批，等待审批后恢复任务，发送飞书消息，并沉淀报告 Artifact、审计日志和任务历史。

步骤：

1. 用户登录并进入任务工作台。
2. 用户选择 Skill 或用自然语言描述企业任务。
3. 平台创建 Task，而不是让 Chat 直接调用 Agent。
4. Skill Resolver 解析可用 Skill、安装状态、权限、凭证和运行环境。
5. Capability Planner 生成本次任务的 connector、scope、secret、sandbox 和 HITL 计划。
6. Agent 根据 Skill 文档和工具声明执行任务，但所有工具调用必须经过 Tool Gateway。
7. 高风险写操作触发 HITL，Task 暂停并通知审批人。
8. 审批后 Task 从 checkpoint 或 continuation 恢复，拒绝则进入 failed/cancelled。
9. 任务持续流式展示进度、工具调用、等待状态和结果。
10. 结果沉淀为 Artifact、审计日志、成本记录和可复用历史。

---

## 对现有设计的调整原则

- 将 Skill/Plugin Registry 从后期功能提前到 MVP P0。
- 将 bash/read/write 从默认工具改为受限内置 Skill。
- 将异步 Task Runtime 从 Phase 2 提前为核心运行模型。
- 将 HITL 与权限传导纳入 Tool/Connector 调用的统一网关。
- 将 Sandbox 与 Session 解耦为 Task/Plugin 运行环境，可按需复用或销毁。
- 将 GUI 从“聊天页面”调整为“任务工作台”，聊天只是其中一个控制面。
