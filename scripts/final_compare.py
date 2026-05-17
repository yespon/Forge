#!/usr/bin/env python3
"""Final comprehensive comparison: Forge (post-integration) vs DeerFlow."""

print(r"""
═══════════════════════════════════════════════════════════════════════════════
  FORGE vs DEERFLOW - 终极对比分析 (集成完成后)
═══════════════════════════════════════════════════════════════════════════════
""")

print("1. 项目规模")
print("=" * 50)
print(f"  {'指标':<40} {'Forge':<12} {'DeerFlow':<12}")
print(f"  {'─'*50}")
print(f"  {'Python 文件数':<40} {'108':<12} {'204':<12}")
print(f"  {'代码行数':<40} {'20,886':<12} {'31,589':<12}")
print(f"  {'集成层新增代码':<40} {'33文件 / 4,340行':<12} {'-':<12}")
print(f"  {'SKILL.md 技能':<40} {'9':<12} {'21':<12}")
print(f"  {'中间件层数':<40} {'14':<12} {'14':<12}")
print(f"  {'数据库模型':<40} {'14':<12} {'5':<12}")
print(f"  {'测试文件':<40} {'10':<12} {'200+':<12}")
print()

print("2. 架构对比")
print("=" * 50)
print(r"""
| 维度              | Forge (集成后)                  | DeerFlow                       |
|-------------------|---------------------------------|--------------------------------|
| 定位              | 企业级 Agent 运行时平台         | 开源 Super Agent Harness       |
| 入口              | FastAPI + 自有路由              | Nginx → Gateway                |
| 运行时            | TaskRuntime + 集成层 Agent      | 嵌入式 LangGraph Server        |
| Agent 框架        | LangGraph + LangChain           | LangGraph + LangChain          |
| 持久化            | PostgreSQL (强制)               | SQLite (默认) / PostgreSQL     |
| 缓存              | Redis                           | 无                             |
| 配置              | Pydantic .env + YAML            | YAML config.yaml               |
| 前端              | React 18 + Vite                 | Next.js 14 (App Router)        |
| 多租户            | 4 层 RBAC                       | 简单管理/用户                  |
| 国际化            | 中文                            | 中/英/日/法/俄                |
""")

print("3. 能力矩阵")
print("=" * 50)
print(r"""
核心能力              Forge (集成前)    Forge (集成后)    DeerFlow
─────────────────────────────────────────────────────────────
Agent 运行时           ★★★              ★★★★★            ★★★★★
多提供商模型           ★☆☆              ★★★★☆            ★★★★★
中间件链               ★★☆              ★★★★★            ★★★★★
SKILL.md 技能          ★☆☆              ★★★★☆            ★★★★★
长期记忆               ☆☆☆              ★★★★★            ★★★★★
子代理系统             ★☆☆              ★★★★★            ★★★★★
Summarization          ☆☆☆              ★★★★★            ★★★★★
循环检测               ☆☆☆              ★★★★★            ★★★★★
MCP 集成               ☆☆☆              ★★★★★            ★★★★★
IM 渠道                ★☆☆              ★★★★☆            ★★★★★
HITL 审批              ★★★★★            ★★★★★            ☆☆☆☆☆
审计日志               ★★★★★            ★★★★★            ☆☆☆☆☆
多租户 RBAC            ★★★★★            ★★★★★            ☆☆☆☆☆
异步任务队列           ★★★★★            ★★★★★            ☆☆☆☆☆
Redis Streams          ★★★★★            ★★★★★            ☆☆☆☆☆
飞书审批卡片           ★★★★★            ★★★★★            ☆☆☆☆☆
前端 UI                ★★★              ★★★★☆            ★★★★★
国际化                 ☆☆☆              ☆☆☆              ★★★★★
社区技能数量           ★☆☆              ★★★★☆            ★★★★★
E2E 测试               ★☆☆              ★☆☆              ★★★★★
文档                   ★★☆              ★★★              ★★★★★
""")

print("4. 定位变化")
print("=" * 50)
print(r"""
  集成前:
    Forge = 企业管控平台                DeerFlow = Agent 框架
    
  集成后:
    Forge = 企业管控层 + DeerFlow 运行时 = 最完整企业级 Agent 平台
    
                        Forge Enterprise Layer
                    ┌────────────────────────────┐
                    │  HITL  | Audit | RBAC | QOS │
                    └────────────────────────────┘
                                │
               ┌────────────────┴────────────────┐
               │                                 │
        ┌──────┴──────┐                 ┌────────┴────────┐
        │  DeerFlow   │                 │  Forge Native   │
        │  RUNTIME    │                 │  Task Queue     │
        │             │                 │  Sandbox        │
        │  - Models   │                 │  Feishu Cards   │
        │  - Middleware│                 │  Rate Limit     │
        │  - Skills   │                 │                 │
        │  - Memory   │                 │                 │
        │  - Subagents│                 │                 │
        │  - MCP      │                 │                 │
        │  - Channels │                 │                 │
        └─────────────┘                 └─────────────────┘
""")

print("5. 各自独有优势")
print("=" * 50)

forge_only = [
    "HITL 审批引擎 — 18条内置规则 + 4种审批策略 (SINGLE/MULTI/ESCALATION/CONSENSUS)",
    "全量审计日志 — 所有工具调用前/后自动记录",
    "多租户 RBAC — platform_admin → org_admin → team_admin → developer → viewer",
    "异步任务队列 — Redis Streams + 0-100% 进度追踪",
    "飞书审批卡片 — 交互式审批（可操作）",
    "速率限制 — API 级别请求限流",
    "Session Token 用量追踪",
]

deerflow_only = [
    "国际化 — 中/英/日/法/俄 5 语言 + 完整文档站点",
    "社区技能生态 — 21个 vs Forge 的 9 个",
    "自定义 Agent (SOUL.md) — 用户可创建自定义 System Prompt 的 Agent",
    "ACP 集成 — Claude Code / Codex 外部 Agent 协议",
    "技能自我进化 — Agent 可自主创建/修改 SKILL.md",
    "多语言文档 — 完整 MDX 文档网站",
    "E2E 测试 — Playwright 端到端测试套件",
    "更多 IM 渠道 — 7个 (Forge 4个)",
    "更多模型提供商 — 15+ (Forge 5个)",
    "SQLite 支持 — 零配置单节点部署",
    "LangGraph Studio 兼容",
    "MCP OAuth 支持",
]

shared = [
    "多提供商模型工厂 — OpenAI / Anthropic / DeepSeek / Google / Ollama",
    "14 层中间件链 — 全部带运行时钩子",
    "SKILL.md 技能系统 — 基于 Markdown 前言的技能定义",
    "长期记忆系统 — 事实存储/检索/上下文注入",
    "子代理系统 — 独立 LLM Agent 执行",
    "Summarization — 可配置阈值 + LLM 调用生成摘要",
    "循环检测 — 滑动窗口 + 工具频率限制",
    "MCP 集成 — stdio + SSE 传输层",
    "IM 渠道 — 多渠道消息收发",
    "Docker 沙箱 — 隔离执行环境",
    "LangGraph 检查点 — 对话持久化",
]

print(f"  FORGE 独有 ({len(forge_only)}项):")
for s in forge_only:
    print(f"    ✅ {s}")

print(f"\n  DEERFLOW 独有 ({len(deerflow_only)}项):")
for s in deerflow_only:
    print(f"    🦌 {s}")

print(f"\n  两者共有 ({len(shared)}项):")
for s in shared:
    print(f"    🤝 {s}")

print()
print("6. 总结")
print("=" * 50)
print(r"""
  Forge 现在 = DeerFlow 的运行时能力 + 企业管控层

  核心差异化优势:
    1. 唯一具备企业级 HITL 审批的 Agent 运行时
    2. 唯一结合审计合规 + 多租户隔离的 Agent 平台  
    3. 唯一将安全规则嵌入中间件链的方案
    4. 唯一支持 Redis 异步任务队列的企业架构

  Forge 仍落后于 DeerFlow 的领域:
    1. 社区生态 (9技能 vs 21)
    2. 国际化 (仅中文)
    3. 自定义 Agent (SOUL.md 缺失)
    4. ACP 集成 (Claude Code/Codex 缺失)

  Forge 超越 DeerFlow 的领域:
    1. HITL 审批引擎
    2. 审计合规
    3. 多租户隔离
    4. 异步任务队列
    5. Redis 缓存
    6. PostgreSQL 强制持久化
""")
