# Testing Guide

## Running Tests
```bash
# All tests
poetry run pytest backend/tests/

# Specific file
poetry run pytest backend/tests/test_integration.py

# With coverage
poetry run pytest --cov=agent_platform backend/tests/
```

## Test Structure
- `test_integration.py` - Configuration and pipeline tests
- `test_memory.py` - Memory system tests
- `test_middleware.py` - Middleware chain tests
- `test_tools.py` - Tool implementation tests
- `test_subagent.py` - Sub-agent system tests
- `test_mcp.py` - MCP configuration tests
- `test_custom_agent.py` - Custom agent tests
- `test_channels.py` - IM channel tests
- `test_acp.py` - ACP agent integration tests
- `test_skills.py` - SKILL.md loading tests
- `test_performance.py` - Performance benchmarks

## Writing Tests
See existing tests for patterns. Use `pytest.mark.asyncio` for async tests.
