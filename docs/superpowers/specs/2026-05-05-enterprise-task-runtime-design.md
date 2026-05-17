# Enterprise Task Runtime Design

## Summary

The MVP should prove one enterprise task can run safely from request to result:

User asks for a business outcome, the platform creates a Task, resolves the required Skills, checks connector permissions, executes through a controlled Tool Gateway, pauses for HITL when needed, resumes after approval, notifies users, and stores artifacts plus audit history.

This platform is not a default coding agent. It borrows the Codex-style endpoint/cloud continuity model, but its primary abstraction is Skill/Plugin driven enterprise work.

---

## Product Boundary

### In Scope

- A Task-first runtime for enterprise and personal work.
- Skill/Plugin Registry and Resolver for installed and permitted capabilities.
- Connector-mediated execution for systems such as Feishu and internal APIs.
- HITL approval for high-risk writes and sensitive access.
- Task event streaming, audit trail, notifications, and artifact metadata.
- Sandbox execution for plugins that need dependencies, file staging, or isolated processing.

### Out of Scope for MVP

- A coding workspace as the default experience.
- A full plugin marketplace with OCI publishing workflows.
- Full enterprise connector ecosystem.
- Complex workflow builders.
- Advanced artifact sharing permissions.
- Full task replay UI.

Coding, shell, and file editing remain possible later as restricted Skills such as `shell-workspace`, but they are not installed or enabled by default.

---

## Reference Demo Scenario

The first demo should be:

> "Summarize this week's Agent Platform progress and send it to the project Feishu group."

The platform should:

1. Create a Task from the Web workspace or Chat control surface.
2. Resolve Skills such as `weekly-summary`, `enterprise-search`, and `feishu-message`.
3. Check whether the user has installed these Skills and has an authorized Feishu connector.
4. Retrieve or synthesize the summary through Skill tools.
5. Detect that sending a group message is a write operation requiring approval.
6. Create an ApprovalRequest and set the Task to `waiting_hitl`.
7. Notify the approver in-app and through Feishu.
8. Resume the Task after approval.
9. Send the Feishu message.
10. Store a report Artifact, task events, audit records, and final status.

---

## Core Modules

### 1. Task Runtime

Task Runtime is the execution owner. All entry points create or bind a Task before invoking Agent/Skill logic.

Responsibilities:

- Create tasks from Web, Chat, API, TUI, or IM channels.
- Own the status machine: `pending`, `queued`, `running`, `waiting_hitl`, `completed`, `failed`, `cancelled`, `timeout`.
- Emit ordered task events for UI streaming and audit.
- Bind tasks to sessions without making sessions the execution owner.
- Persist LangGraph thread/checkpoint identifiers.
- Resume or terminate tasks after approval decisions.

### 2. Skill Registry and Resolver

The Registry stores Skill manifests and user installations. The Resolver decides which Skills participate in a task.

Responsibilities:

- Store Skill metadata, versions, visibility, manifest, runtime requirements, and HITL policy.
- Track user/org/team installations and configuration.
- Filter available Skills by user, organization, team, status, and requested task intent.
- Return resolved Skill docs, tool declarations, connector requirements, and artifact declarations.

MVP can use database records plus seeded local Skill manifests. Full OCI packaging can come later.

### 3. Capability Planner

Capability Planner turns resolved Skills into an executable capability plan.

Responsibilities:

- Determine required connectors, scopes, secrets, sandbox needs, and network policy.
- Detect missing authorization before the task starts.
- Produce explicit denial reasons when a task cannot run.
- Attach default HITL policies based on Skill manifests and org rules.
- Keep credentials out of prompts and Agent-visible context.

### 4. Tool Gateway

Tool Gateway is the only allowed execution path for Skill/Plugin tools.

Execution order:

1. Validate tool name and arguments against the resolved Skill manifest.
2. Check user and task permissions.
3. Resolve connector credentials or sandbox environment references.
4. Evaluate HITL policy.
5. Execute the connector or sandbox call.
6. Emit task event, audit log, trace span, and artifact metadata.

Agents must not receive raw connector tokens or direct access to arbitrary backend functions.

### 5. Connector Layer

Connectors translate platform tool calls to enterprise or third-party APIs.

MVP connectors:

- `feishu`: send message, send approval cards, read limited user/chat metadata.
- `internal_api`: template/mock connector for internal enterprise APIs.

Connector credentials are stored outside the database in Vault or a Secret Broker; database rows store only `vault_ref`, scopes, owner, and status.

### 6. HITL and Notification

HITL is a governance path inside Tool Gateway.

Responsibilities:

- Match Tool Gateway calls against Skill-level and org-level rules.
- Create ApprovalRequest with tool input hash, context summary, approvers, strategy, and expiry.
- Put the Task into `waiting_hitl`.
- Notify approvers in-app and via Feishu.
- Resume the Task with an approval decision, or fail/cancel on rejection or timeout.

The approver identity comes from authenticated user context, never from client-supplied `user_id`.

### 7. Artifact and History

Artifacts and history close the task loop.

Responsibilities:

- Store generated reports, documents, tables, attachments, or structured data metadata.
- Link artifacts to task, session, user, org, and producing Skill.
- Keep task event history queryable for debugging and user-facing timelines.
- Support a later "continue from this task" workflow.

MVP only requires metadata and download references, not full sharing policy.

---

## Data Flow

```text
Ingress(Chat/Web/API/Feishu)
  -> Task.create
  -> SkillResolver.resolve
  -> CapabilityPlanner.plan
  -> Runtime.build_graph(skill docs + gateway tools)
  -> ToolGateway.execute
  -> Connector/Sandbox
  -> Events + Audit + Artifact
  -> Task.completed / waiting_hitl / failed
```

Approval resume flow:

```text
ToolGateway detects approval_required
  -> ApprovalRequest.create
  -> Task.status = waiting_hitl
  -> Notification.send
  -> Approver decision
  -> TaskRuntime.resume(checkpoint, decision)
  -> ToolGateway continues or aborts
```

---

## API Impact

### Task API

- `POST /api/v1/tasks`
  - Creates a task.
  - Accepts `intent`, optional `skill_ids`, optional `inputs`, optional `session_id`, `mode`, `priority`, and `approval_policy`.
  - Returns resolved Skills, missing authorization flags, status, and stream URL.

- `GET /api/v1/tasks/{id}`
  - Returns task detail, status, resolved Skills, progress, current stage, and artifact summary.

- `GET /api/v1/tasks/{id}/stream`
  - Streams `task_status`, `agent_message`, `tool_call`, `approval_required`, `artifact_created`, `error`, and `done`.

- `POST /api/v1/tasks/{id}/cancel`
  - Cancels active or queued tasks.

- `GET /api/v1/tasks/{id}/artifacts`
  - Lists generated artifacts.

### Skill API

- `GET /api/v1/skills`
  - Lists available Skills after visibility and permission filtering.

- `POST /api/v1/skills/{name}/install`
  - Installs a Skill and validates required capabilities.

- `POST /api/v1/skills/{name}/config`
  - Updates user-specific Skill config.

### Connector API

- `GET /api/v1/connectors`
  - Lists connectors and authorization status.

- `POST /api/v1/connectors/{id}/authorize`
  - Starts OAuth or credential binding.

- `GET /api/v1/connectors/{id}/status`
  - Returns scopes, expiry, and status.

### Approval API

- `GET /api/v1/approvals/pending`
- `GET /api/v1/approvals/{id}`
- `POST /api/v1/approvals/{id}`
  - Uses authenticated approver identity for decisions.
  - Never accepts `user_id` as the decision-maker.

---

## Database Impact

Required MVP tables or fields:

- `tasks`
  - Add `intent`, `inputs`, `resolved_skills`, `capability_plan`, `current_approval_id`, `mode`, and status values for `waiting_hitl` and `timeout`.

- `task_events`
  - Store ordered event stream and audit-friendly payloads.

- `skills`
  - Store manifest data, package type, connector requirements, runtime config, UI schema, artifact schema, and HITL config.

- `user_skills`
  - Store installation config, granted capabilities, and connector bindings.

- `connectors`
  - Register connector metadata, auth type, scopes, and config schema.

- `connector_connections`
  - Bind connectors to user/team/org with scopes and `vault_ref`.

- `approval_requests`
  - Link approval to task, thread/checkpoint, tool call, approvers, decisions, expiry, and final decision.

- `artifacts`
  - Store task outputs and download/storage references.

---

## Error Handling

- Missing Skill: Task creation returns 422 with `missing_skills`.
- Skill not installed: Task creation returns 409 with `install_required`.
- Missing connector authorization: Task creation returns 409 with `authorization_required`.
- Insufficient scope: Task creation or Tool Gateway returns 403 with required scopes.
- Approval timeout: Task status becomes `failed` or `timeout` based on task policy.
- Connector failure: Tool Gateway records retryable/non-retryable error and emits `error` event.
- Sandbox failure: Task moves to `failed` unless the Skill declares a fallback connector path.
- Artifact storage failure after successful tool execution: task becomes `completed_with_warnings` in a later phase; MVP can mark failed if artifact is required.

---

## Testing Strategy

Follow TDD during implementation.

Unit tests:

- Skill manifest validation.
- Skill visibility and installation filtering.
- Capability planning for allowed, missing authorization, and missing scope cases.
- Tool Gateway execution ordering.
- HITL rule matching and decision identity.
- Task status transitions.

Integration tests:

- Create enterprise task with seeded Skills and mocked connectors.
- Trigger approval and verify Task enters `waiting_hitl`.
- Approve and verify Task resumes and completes.
- Reject and verify Task fails/cancels predictably.
- Generate artifact metadata.

Frontend tests:

- Task creation form or chat-to-task flow.
- Task timeline event rendering.
- Approval panel action flow.
- Artifact list rendering.

Review checks:

- No Agent path bypasses Tool Gateway.
- No connector token appears in prompts, task events, or logs.
- No approval decision trusts client-supplied `user_id`.
- `shell-workspace` remains disabled unless explicitly installed and authorized.

---

## Parallel Implementation Slices

After this spec is approved, implementation can be split across subagents with disjoint write scopes:

1. Task Runtime worker
   - Owns task models, task API, task events, status transition tests.

2. Skill Registry worker
   - Owns Skill models, manifest parser, resolver, install/config API, tests.

3. Tool Gateway + HITL worker
   - Owns gateway abstraction, approval creation/resume integration, identity-safe decisions, tests.

4. Connector worker
   - Owns connector registry, Feishu/internal mock connector, credential reference model, tests.

5. Frontend worker
   - Owns task workspace UI, timeline, approval panel integration, artifact list, UI verification.

6. Integration reviewer
   - Runs cross-module tests and reviews that no execution path bypasses the gateway.

---

## Open Decisions

These are intentionally fixed for MVP to avoid scope drift:

- Use seeded local Skill manifests instead of full OCI plugin publishing.
- Use Feishu and internal API mock/template as the first connectors.
- Store credential bodies outside the database; database stores `vault_ref`.
- Make Task Runtime the only execution owner.
- Keep Chat as a control surface, not an execution owner.
- Keep shell/coding tools disabled by default.
