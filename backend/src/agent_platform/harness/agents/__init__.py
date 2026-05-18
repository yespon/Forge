"""Agent factory and type definitions."""
from .types import *  # noqa: F401,F403


def create_forge_agent(*args, **kwargs):
    """Lazy import to avoid circular dependency with harness.config."""
    from .factory import create_forge_agent as _create
    return _create(*args, **kwargs)


def get_available_models(*args, **kwargs):
    from .factory import get_available_models as _get
    return _get(*args, **kwargs)


def resolve_model(*args, **kwargs):
    from .factory import resolve_model as _resolve
    return _resolve(*args, **kwargs)


__all__ = ["create_forge_agent", "get_available_models", "resolve_model"]
