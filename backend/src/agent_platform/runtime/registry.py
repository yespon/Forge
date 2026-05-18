"""Runtime kernel registry."""

from agent_platform.runtime.kernel.base import RuntimeKernel


class RuntimeRegistry:
    """Registry for runtime kernels."""

    def __init__(self):
        self._kernels: dict[str, RuntimeKernel] = {}

    def register(self, kernel: RuntimeKernel) -> None:
        self._kernels[kernel.name] = kernel

    def get(self, name: str) -> RuntimeKernel:
        if name not in self._kernels:
            raise KeyError(f"Unknown runtime kernel: {name}")
        return self._kernels[name]


_registry: RuntimeRegistry | None = None


def get_runtime_registry() -> RuntimeRegistry:
    global _registry
    if _registry is None:
        _registry = RuntimeRegistry()
    return _registry
