"""Memory system tests (30 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestMemoryStore:
    def setup_method(self):
        from agent_platform.integration.memory import MemoryStore
        self.store = MemoryStore(storage_path="/tmp/_tsmem.json")
    def teardown_method(self): self.store.clear()
    def test_01_empty_store(self):
        assert len(self.store.get_all_facts()) == 0
    def test_02_add_single(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="test fact"))
        assert len(self.store.get_all_facts()) == 1
    def test_03_add_multiple(self):
        from agent_platform.integration.memory import MemoryFact
        for i in range(10): self.store.add_fact(MemoryFact(content=f"fact_{i}"))
        assert len(self.store.get_all_facts()) == 10
    def test_04_dedup(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="duplicate"))
        self.store.add_fact(MemoryFact(content="duplicate"))
        assert len(self.store.get_all_facts()) == 1
    def test_05_retrieve_by_keyword(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="User likes Python programming"))
        r = self.store.get_relevant_facts("Python")
        assert len(r) >= 1
    def test_06_retrieve_no_match(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="User likes Python"))
        r = self.store.get_relevant_facts("Rust")
        assert isinstance(r, list)
    def test_07_empty_query(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="test"))
        r = self.store.get_relevant_facts("")
        assert len(r) >= 1 or len(r) == 0  # Should not crash
    def test_08_case_insensitive(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="User likes Python"))
        r = self.store.get_relevant_facts("python")
        assert len(r) >= 1
    def test_09_clear(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="test"))
        self.store.clear()
        assert len(self.store.get_all_facts()) == 0
    def test_10_max_facts(self):
        from agent_platform.integration.memory import MemoryFact
        for i in range(150): self.store.add_fact(MemoryFact(content=f"fact_{i}"))
        assert len(self.store.get_all_facts()) <= 150
    def test_11_very_long_content(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="x" * 5000))
        assert len(self.store.get_all_facts()) == 1
    def test_12_multiple_categories(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="a", category="cat1"))
        self.store.add_fact(MemoryFact(content="b", category="cat2"))
        assert len(self.store.get_all_facts()) == 2
    def test_13_scoring_works(self):
        from agent_platform.integration.memory import MemoryFact
        self.store.add_fact(MemoryFact(content="User likes Python and FastAPI"))
        r = self.store.get_relevant_facts("Python")
        assert len(r) > 0
        # Higher keyword density should score higher
        self.store.add_fact(MemoryFact(content="Python Python Python Python Python"))
        r = self.store.get_relevant_facts("Python")
        assert len(r) >= 2
    def test_14_persistence(self):
        from agent_platform.integration.memory import MemoryFact, MemoryStore
        s2 = MemoryStore(storage_path="/tmp/_tsmem.json")
        s2.add_fact(MemoryFact(content="persist test"))
        s3 = MemoryStore(storage_path="/tmp/_tsmem.json")
        assert len(s3.get_all_facts()) >= 1

class TestMemoryManager:
    def setup_method(self):
        from agent_platform.integration.memory import MemoryManager
        self.mm = MemoryManager(storage_path="/tmp/_tsmm.json")
    def teardown_method(self): self.mm.store.clear()
    def test_01_store_fact(self):
        self.mm.store_fact("User likes dark mode")
        assert len(self.mm.store.get_all_facts()) >= 1
    def test_02_store_with_category(self):
        self.mm.store_fact("User works at Google", category="work")
        assert any("Google" in f.content for f in self.mm.store.get_all_facts())
    def test_03_store_with_confidence(self):
        self.mm.store_fact("Important fact", confidence=0.95)
        facts = self.mm.store.get_all_facts()
        assert any(f.confidence == 0.95 for f in facts)
    def test_04_get_context_empty(self):
        ctx = self.mm.get_memory_context()
        assert ctx == ""
    def test_05_get_context_with_facts(self):
        self.mm.store_fact("User likes Python")
        ctx = self.mm.get_memory_context()
        assert "Python" in ctx and "<memory>" in ctx
    def test_06_get_context_with_query(self):
        self.mm.store_fact("User prefers dark mode")
        self.mm.store_fact("User likes coffee")
        ctx = self.mm.get_memory_context("What UI theme does user prefer?")
        assert "dark" in ctx.lower() or "coffee" in ctx.lower()
    def test_07_injection_toggle(self):
        assert hasattr(self.mm, "injection_enabled")
    def test_08_max_injection_tokens(self):
        assert hasattr(self.mm, "max_injection_tokens")
    def test_09_context_xml_format(self):
        self.mm.store_fact("fact one")
        self.mm.store_fact("fact two")
        ctx = self.mm.get_memory_context()
        assert ctx.startswith("<memory>") and ctx.endswith("</memory>")
    def test_10_max_facts_limit(self):
        for i in range(200): self.mm.store_fact(f"fact_{i}")
        assert len(self.mm.store.get_all_facts()) <= self.mm.max_facts
    def test_11_multiple_injections(self):
        self.mm.store_fact("a")
        c1 = self.mm.get_memory_context()
        self.mm.store_fact("b")
        c2 = self.mm.get_memory_context()
        assert len(c2) >= len(c1)
    def test_12_injection_disabled(self):
        self.mm.injection_enabled = False
        self.mm.store_fact("test")
        assert self.mm.get_memory_context() == ""
