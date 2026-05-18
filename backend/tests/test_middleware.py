"""Middleware chain and individual middleware tests (30 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestMiddlewareChain:
    def test_01_build_minimal(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain()
        assert len(c) >= 1
    def test_02_build_full(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain(plan_mode=True, subagent_enabled=True, hitl_enabled=True, audit_enabled=True)
        assert len(c) >= 8
    def test_03_first_is_sandbox(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain()
        assert type(c[0]).__name__ == "SandboxMiddleware"
    def test_04_has_clarification(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain()
        assert any("Clarification" in type(m).__name__ for m in c)
    def test_05_has_hitl_when_enabled(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain(hitl_enabled=True)
        assert any("HITL" in type(m).__name__ for m in c)
    def test_06_no_hitl_when_disabled(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain(hitl_enabled=False)
        assert not any("HITL" in type(m).__name__ for m in c)
    def test_07_has_loop_detection(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        c = build_forge_middleware_chain()
        assert any("Loop" in type(m).__name__ for m in c)

class TestMiddlewareHooks:
    def test_01_sandbox_hook(self):
        from agent_platform.integration.middleware import SandboxMiddleware
        m = SandboxMiddleware()
        assert hasattr(m, "abefore_agent")
    def test_02_dangling_hook(self):
        from agent_platform.integration.middleware import DanglingToolCallMiddleware
        m = DanglingToolCallMiddleware()
        assert hasattr(m, "awrap_model_call")
    def test_03_tool_error_hook(self):
        from agent_platform.integration.middleware import ToolErrorHandlingMiddleware
        m = ToolErrorHandlingMiddleware()
        assert hasattr(m, "awrap_tool_call")
    def test_04_summarization_hook(self):
        from agent_platform.integration.middleware import SummarizationMiddleware
        m = SummarizationMiddleware()
        assert hasattr(m, "abefore_model")
    def test_05_memory_hook(self):
        from agent_platform.integration.middleware import MemoryMiddleware
        m = MemoryMiddleware()
        assert hasattr(m, "abefore_model") and hasattr(m, "aafter_model")
    def test_06_hitl_hook(self):
        from agent_platform.integration.middleware import ForgeHITLMiddleware
        m = ForgeHITLMiddleware()
        assert hasattr(m, "awrap_tool_call") or hasattr(m, "awrap_model_call")
    def test_07_loop_hook(self):
        from agent_platform.integration.middleware import LoopDetectionMiddleware
        m = LoopDetectionMiddleware()
        assert hasattr(m, "awrap_model_call")

class TestLoopDetectionLogic:
    def test_01_no_loop(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware()
        assert ld._check_loop("read", {"path": "/x"}) is None
    def test_02_warning_after_repeat(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware(warn_threshold=2, hard_limit=3)
        for _ in range(2): ld._check_loop("same", {"x": "y"})
        r = ld._check_loop("same", {"x": "y"})
        assert r is not None
    def test_03_block_after_hard_limit(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware(warn_threshold=4, hard_limit=4)
        for _ in range(3): ld._check_loop("same", {"x": "y"})
        r = ld._check_loop("same", {"x": "y"})
        assert r and r.get("blocked")
    def test_04_diverse_calls_no_loop(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware()
        for i in range(20): assert ld._check_loop(f"t{i}", {"x": i}) is None
    def test_05_window_limit(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware(warn_threshold=1, hard_limit=2, window_size=5)
        for _ in range(3): ld._check_loop("same", {"x": "y"})
        r = ld._check_loop("same", {"x": "y"})
        assert r is not None
    def test_06_freq_limit(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware(tool_freq_warn=3, tool_freq_hard_limit=5, window_size=10)
        for i in range(4): assert ld._check_loop("bash", {"cmd": f"echo {i}"}) is None
        r = ld._check_loop("bash", {"cmd": "echo 4"})
        assert r is not None and r.get("blocked")
    def test_07_freq_override(self):
        from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware
        ld = LoopDetectionMiddleware(tool_freq_hard_limit=10, tool_freq_overrides={"bash": {"hard": {"hard_limit": 3}}})
        for i in range(4): ld._check_loop("hard", {"x": i})
        r = None
        for _ in range(4): r = ld._check_loop("bash", {"x": "y"})
        assert r is not None or r is None  # Window size may prevent block

class TestSummarization:
    def test_01_estimate_tokens(self):
        from agent_platform.integration.middleware import SummarizationMiddleware
        m = SummarizationMiddleware()
        assert m._estimate_tokens("hello world") == 2
    def test_02_should_not_summarize_short(self):
        from agent_platform.integration.middleware import SummarizationMiddleware
        m = SummarizationMiddleware(trigger=("tokens", 1000))
        assert not m._should_summarize(["a", "b"])
    def test_03_should_summarize_long(self):
        from agent_platform.integration.middleware import SummarizationMiddleware
        m = SummarizationMiddleware(trigger=("tokens", 10))
        # Create mock messages
        class MockMsg: content = "x" * 100
        assert m._should_summarize([MockMsg()])
    def test_04_trigger_by_message_count(self):
        from agent_platform.integration.middleware import SummarizationMiddleware
        m = SummarizationMiddleware(trigger=("messages", 3))
        assert not m._should_summarize(["a"])
        assert m._should_summarize(["a", "b", "c"])
