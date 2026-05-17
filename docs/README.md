# 企业 Agent Runtime 平台 — 设计文档

## 文档目录

| 序号 | 文档 | 说明 |
|------|------|------|
| 00 | [产品定位](./00-product-positioning.md) | Skill/Plugin 优先的产品定位与 Brainstorm 结论 |
| 00a | [企业任务运行时规格](./superpowers/specs/2026-05-05-enterprise-task-runtime-design.md) | Superpowers Brainstorming 产出的 MVP 主规格 |
| 01 | [需求清单](./01-requirements.md) | 完整需求列表（20项 + 补充） |
| 02 | [框架选型](./02-framework-selection.md) | DeerFlow vs DeepAgents 对比分析 |
| 03 | [架构设计](./03-architecture-design.md) | 详细系统架构设计 |
| 04 | [MVP 规划](./04-mvp-plan.md) | 12周 MVP 开发计划 |
| 05 | [API 参考](./05-api-reference.md) | 完整 API 规范与示例 |
| 06 | [数据库设计](./06-database-schema.md) | 详细表结构、索引、分区策略 |
| 07 | [Week 1 实现](./07-week1-implementation.md) | 项目初始化与代码实现指南 |
| 08 | [前端开发指南](./08-frontend-guide.md) | React 任务工作台 + Skill/审批/产物视图 |
| 09 | [部署运维手册](./09-deployment-ops.md) | K8s manifests、监控、升级流程 |

---

## 快速导航

### 如果你是决策者

1. 先看 [00-产品定位](./00-product-positioning.md) 确认产品边界
2. 再看 [02-框架选型](./02-framework-selection.md) 了解技术选型理由
3. 再看 [04-MVP 规划](./04-mvp-plan.md) 了解开发节奏

### 如果你是开发者

1. 先看 [00-产品定位](./00-product-positioning.md) 理解为什么 Skill/Plugin 是主路径
2. 再看 [03-架构设计](./03-architecture-design.md) 了解系统结构
3. 参考 [04-MVP 规划](./04-mvp-plan.md) Week 1 开始实施

### 如果你是产品经理

1. 先看 [00-产品定位](./00-product-positioning.md) 确认产品主线
2. 再看 [01-需求清单](./01-requirements.md) 确认需求覆盖
3. 再看 [04-MVP 规划](./04-mvp-plan.md) 确认优先级

---

## 核心决策

- **产品主线**: Skill/Plugin Runtime + Task Runtime，非默认 coding agent
- **Agent Runtime**: DeepAgents/LangGraph 能力作为底层执行图，不直接暴露 coding 工具为默认能力
- **Sandbox**: Docker (MVP) → K8s (生产)
- **多租户层**: 自建 (用户/组织/团队/权限)
- **移植组件**: DeerFlow (Sandbox Provider + Skill 系统 + IM Channel)

---

## 后续文档规划

- [ ] 05-api-reference.md — API 详细规范
- [ ] 06-database-schema.md — 数据库详细设计
- [ ] 07-frontend-guide.md — 前端开发指南
- [ ] 08-deployment-guide.md — 部署运维手册
- [ ] 09-security-guide.md — 安全合规指南
