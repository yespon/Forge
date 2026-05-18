"""Base runtime kernel interface."""

from typing import AsyncIterator, Protocol

from agent_platform.runtime.context import RuntimeContext, RuntimeRun, RuntimeSnapshot
from agent_platform.runtime.events import RuntimeEvent


class RuntimeKernel(Protocol):
    """Protocol implemented by all runtime kernels."""

    name: str

    async def create_run(self, context: RuntimeContext) -> RuntimeRun: ...

    async def stream(
        self,
        run: RuntimeRun,
        input_message: str | None = None,
    ) -> AsyncIterator[RuntimeEvent]: ...

    async def resume(
        self,
        run_id: str,
        payload: dict,
    ) -> AsyncIterator[RuntimeEvent]: ...

    async def cancel(self, run_id: str) -> None: ...

    async def inspect(self, run_id: str) -> RuntimeSnapshot: ...
