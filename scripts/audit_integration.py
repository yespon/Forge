#!/usr/bin/env python3
"""Honest audit of every integration module - REAL vs STUB vs MISSING."""

import ast, os

base = "backend/src/agent_platform/integration"

def analyze_file(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {"error": "syntax", "lines": len(content.split('\n'))}
    
    lines = content.split('\n')
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    
    top_real = 0
    top_stub = 0
    for fn in funcs:
        if len(fn.body) == 1 and isinstance(fn.body[0], ast.Pass):
            top_stub += 1
        else:
            top_real += 1
    
    cls_methods = 0
    cls_stubs = 0
    for cls in classes:
        methods = [n for n in ast.walk(cls) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for m in methods:
            if len(m.body) == 1 and isinstance(m.body[0], ast.Pass):
                cls_stubs += 1
            else:
                cls_methods += 1
    
    return {"lines": len(lines), "top_real": top_real, "top_stub": top_stub, "cls_methods": cls_methods, "cls_stubs": cls_stubs}

def pct(s):
    if s is None:
        return 0
    t = s["top_real"] + s["top_stub"] + s["cls_methods"] + s["cls_stubs"]
    if t == 0:
        return 100 if s["lines"] > 0 else 0
    real = s["top_real"] + s["cls_methods"]
    return round(real / t * 100)

modules = [
    ("types.py", "类型定义", ""),
    ("config.py", "统一配置加载", ""),
    ("models.py", "多提供商模型工厂", ""),
    ("agent_factory.py", "Agent装配器", ""),
    ("middleware.py", "12层中间件链", ""),
    ("memory.py", "长期记忆系统", ""),
    ("subagents.py", "子代理执行器", ""),
    ("skills.py", "SKILL.md技能系统", ""),
    ("mcp.py", "MCP管理器", ""),
    ("channels.py", "多渠道IM服务", ""),
    ("tools/__init__.py", "工具加载器", ""),
    ("tools/file_ops.py", "文件操作工具", ""),
    ("tools/bash.py", "Shell执行工具", ""),
    ("tools/web_search.py", "网页搜索", ""),
    ("tools/web_fetch.py", "网页抓取", ""),
    ("tools/builtins.py", "内建工具", ""),
]

print("=" * 90)
print("FORGE INTEGRATION HONEST AUDIT")
print("=" * 90)
print()
print(f"{'模块':<20} {'完成度':<15} {'行数':<6} {'真实函数':<8} {'存根函数':<8} {'类方法':<8} {'类存根':<8}")
print("-" * 90)

results = []
for name, desc, _ in modules:
    path = f"{base}/{name}"
    s = analyze_file(path)
    if s is None:
        print(f"  {name:<20} {'NOT FOUND':>15}")
        continue
    score = pct(s)
    results.append(score)
    bar = "█" * (score // 10) + "░" * (10 - score // 10)
    results.append(score)
    print(f"  {name:<20} {bar} {score:3d}%  {s['lines']:<5} {s['top_real']:<8} {s['top_stub']:<8} {s['cls_methods']:<8} {s['cls_stubs']:<8}")

avg = round(sum(results) / len(results)) if results else 0
print(f"\n  整体完成度: {avg}%  ({len(results)}模块)")
print()

# DETAILED BREAKDOWN
print("=" * 90)
print("逐功能诚实评估")
print("=" * 90)

print("""
✅ 已实现 (REAL) ─── 有实际执行逻辑的代码

  配置系统 (config.py)          100% - YAML+Pydantic合并，环境变量解析
  类型系统 (types.py)           100% - 15个数据类覆盖所有配置域
  文件操作 (file_ops.py)        90% - read/write/ls，路径穿越防护
  Shell执行 (bash.py)           90% - subprocess+超时+危险命令拦截
  网页搜索 (web_search.py)      90% - DuckDuckGo集成+结果截断
  网页抓取 (web_fetch.py)       90% - httpx+markdownify转换
  模型工厂 (models.py)          85% - 5大提供商检测，思维模式切换
  记忆系统 (memory.py)          80% - JSON持久化，关键词检索(评分排序)
  中间件链构建 (middleware.py)   70% - 12层链构建，Summarization阈值检测，
                                        LoopDetection滑动窗口追踪，
                                        HITL规则引擎集成

◐ 半完成 (STUB) ─── 框架存在，缺少运行时执行

  Agent装配 (agent_factory.py)  60% - create_forge_agent组装逻辑完整，
                                        但从未在真实Agent流程中被调用
  子代理 (subagents.py)          65% - TaskRuntime集成(create/execute/cancel)，
                                        回退路径仅sleep 0.5s
  SKILL.md加载 (skills.py)      75% - 正确解析YAML前置元+指令，
                                        无运行时allowed-tools验证
  工具加载器 (tools/__init__)   70% - 7个工具加载，子代理和MCP存根
  MCP管理 (mcp.py)              40% - 配置CRUD完整，
                                        get_tools()返回空列表
  多渠道IM (channels.py)        30% - 生命周期+消息数据类，
                                        无实际渠道实现

❌ 未实现 (MISSING) ─── 完全缺失的能力

  中间件运行时钩子               - 12个中间件类，0个实现on_xxx回调
  子Agent LLM执行                - 创建Forge Task但不启动子Agent调用
  Summarization LLM调用          - 检测到阈值但不生成摘要
  记忆LLM提取                    - 存储事实但不提取新事实
  MCP传输层                      - 无langchain-mcp-adapters  - 无stdio/SSE工具发现
  7个IM协议实现                  - 0/7个IM渠道有实现
  前端UI展示                     - 无模型选择器/技能列表/记忆查看
  自定义Agent (SOUL.md)          - 无用户创建自定义Agent能力
  ACP集成(Claude Code/Codex)    - 无外部Agent接入
  国际化(i18n)                   - 仅中文
  端到端测试                     - 无集成测试

  核心原因:
  ┌─────────────────────────────────────────────────────────┐
  │ DeerFlow的Pro属于"运行时能力"而不仅仅是"数据类和框架"。   │
  │                                                         │
  │ 真正有价值的是：                                          │
  │ 1. 中间件的on_message钩子实际拦截和处理消息                │
  │ 2. MCP的stdio子进程实际连接外部工具                       │
  │ 3. IM渠道的WebSocket/轮询实际收发消息                     │
  │ 4. ！这些都需要实际的网络IO和外部系统交互                    │
  │                                                         │
  │ 当前集成层 = 架构框架(好) + 数据层(好)                   │
  │        缺少 = 运行时引擎(关键) + 外部连接(关键)          │
  └─────────────────────────────────────────────────────────┘
""")