# Phase 1 Runtime Refactor Plan

## Goal

Introduce a minimal runtime abstraction layer without breaking current APIs, then route `TaskRuntime` through a unified kernel interface.

## Scope

Phase 1 only:
- Add `runtime/` abstraction skeleton
- Add a DeerFlow-backed kernel adapter
- Refactor `TaskRuntime` to use kernel registry
- Preserve existing task APIs and streaming behavior
- Do not yet fully unify ToolGateway across all tools

## Non-Goals

- No large DB schema changes
- No physical migration of all integration/provider files
- No full subtask tree implementation
- No full MCP governance refactor

## Step Plan

### Step 1 — Add runtime skeleton
Files:
- `backend/src/agent_platform/runtime/__init__.py`
- `backend/src/agent_platform/runtime/context.py`
- `backend/src/agent_platform/runtime/events.py`
- `backend/src/agent_platform/runtime/interrupts.py`
- `backend/src/agent_platform/runtime/registry.py`
- `backend/src/agent_platform/runtime/kernel/__init__.py`
- `backend/src/agent_platform/runtime/kernel/base.py`
- `backend/src/agent_platform/runtime/kernel/deerflow.py`

Deliverables:
- `RuntimeContext`, `RuntimeRun`, `RuntimeSnapshot`
- `RuntimeEvent`
- `ApprovalInterrupt`
- `RuntimeKernel` protocol
- `RuntimeRegistry`
- `DeerFlowKernel` adapter

### Step 2 — Refactor TaskRuntime to use kernel
Files:
- `backend/src/agent_platform/services/task_runtime.py`

Deliverables:
- Build `RuntimeContext` from `Task + Session + User + CapabilityPlan`
- Resolve kernel from registry
- Translate `RuntimeEvent` -> `TaskStreamEvent`
- Persist task events using existing `TaskEvent` model

### Step 3 — Compatibility verification
Checks:
- Existing create/execute task flow still works
- Existing SSE stream event types remain compatible (`content`, `hitl_required`, `error`, `done`)
- Existing task event persistence still works

## Default kernel strategy

- Default to `deerflow`
- Allow fallback naming via task metadata later
- Keep old `agent/factory.py` path untouched for now

## Risks

1. Event shape mismatch between DeerFlow runtime streaming and current task SSE output
2. Interrupt mapping may need refinement once approval resume is wired
3. Future Forge-native kernel should reuse the same interfaces

## Execution order

1. Add skeleton
2. Wire TaskRuntime to registry + deerflow kernel
3. Run targeted tests / import checks
4. Summarize remaining follow-up work
