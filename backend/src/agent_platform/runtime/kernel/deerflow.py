"""DeerFlow-backed runtime kernel adapter."""

import uuid
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage

from agent_platform.integration.agent_factory import create_forge_agent
from agent_platform.runtime.context import RuntimeContext, RuntimeRun, RuntimeSnapshot
from agent_platform.runtime.events import RuntimeEvent, make_runtime_event
from agent_platform.runtime.kernel.base import RuntimeKernel


class DeerFlowKernel(RuntimeKernel):
    """Runtime kernel using the integrated DeerFlow agent harness."""

    name = "deerflow"

    def __init__(self):
        self._runs: dict[str, dict[str, Any]] = {}

    async def create_run(self, context: RuntimeContext) -> RuntimeRun:
        run_id = str(uuid.uuid4())
        run = RuntimeRun(
            run_id=run_id,
            task_id=context.task_id,
            thread_id=context.thread_id,
            kernel=self.name,
            status="created",
            metadata={"model_name": context.model_name},
        )
        self._runs[run_id] = {"context": context, "run": run, "agent": None}
        return run

    async def stream(
        self,
        run: RuntimeRun,
        input_message: str | None = None,
    ) -> AsyncIterator[RuntimeEvent]:
        state = self._runs.get(run.run_id)
        if not state:
            raise ValueError(f"Unknown runtime run: {run.run_id}")

        context: RuntimeContext = state["context"]
        agent = state.get("agent")
        if agent is None:
            agent = create_forge_agent(
                model_name=context.model_name,
                system_prompt=context.system_prompt,
                session=context.metadata.get("session"),
                user=context.metadata.get("user"),
                db=context.metadata.get("db"),
                hitl_enabled=context.metadata.get("enable_hitl", False),
            )
            state["agent"] = agent

        yield make_runtime_event("run_started", run_id=run.run_id, task_id=run.task_id)

        message = input_message or context.input_message or ""
        async for chunk in agent.astream(
            {"messages": [HumanMessage(content=message)]},
            stream_mode="updates",
        ):
            content_emitted = False
            if isinstance(chunk, dict):
                for _node, data in chunk.items():
                    if not isinstance(data, dict):
                        continue
                    messages = data.get("messages", [])
                    for msg in messages:
                        msg_content = getattr(msg, "content", None)
                        if msg_content:
                            content_emitted = True
                            yield make_runtime_event(
                                "message_delta",
                                run_id=run.run_id,
                                task_id=run.task_id,
                                content=msg_content,
                            )
            if not content_emitted and isinstance(chunk, dict) and "interrupt" in chunk:
                yield make_runtime_event(
                    "approval_required",
                    run_id=run.run_id,
                    task_id=run.task_id,
                    interrupt=chunk.get("interrupt", {}),
                )

        yield make_runtime_event("run_completed", run_id=run.run_id, task_id=run.task_id)

    async def resume(
        self,
        run_id: str,
        payload: dict,
    ) -> AsyncIterator[RuntimeEvent]:
        raise NotImplementedError("DeerFlow kernel resume is not wired in Phase 1")

    async def cancel(self, run_id: str) -> None:
        state = self._runs.get(run_id)
        if state:
            state["run"].status = "cancelled"

    async def inspect(self, run_id: str) -> RuntimeSnapshot:
        state = self._runs.get(run_id)
        if not state:
            raise ValueError(f"Unknown runtime run: {run_id}")
        run: RuntimeRun = state["run"]
        return RuntimeSnapshot(run_id=run.run_id, status=run.status, metadata=run.metadata)
