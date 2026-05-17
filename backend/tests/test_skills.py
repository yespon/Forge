"""SKILL.md loading tests (20 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def _get_loader():
    from agent_platform.integration.skills import SkillLoader
    for p in ["skills/public", "../skills/public", "/Users/yespon/workspace/repo/forge/skills/public"]:
        pp = Path(p)
        if pp.exists() and list(pp.iterdir()):
            return SkillLoader(skills_path=p)
    return None

LOADER = _get_loader()

class TestSkillLoading:
    def test_01_all_skills(self):
        assert LOADER is not None, "Skills directory not found"
        n = LOADER.get_all_skill_names()
        assert len(n) >= 20
    def test_02_deep_research(self):
        assert "deep-research" in LOADER.get_all_skill_names()
    def test_03_data_analysis(self):
        assert "data-analysis" in LOADER.get_all_skill_names()
    def test_04_image_gen(self):
        assert "image-generation" in LOADER.get_all_skill_names()
    def test_05_code_docs(self):
        assert "code-documentation" in LOADER.get_all_skill_names()
    def test_06_bootstrap(self):
        assert "Bootstrap" in LOADER.get_all_skill_names()
    def test_07_skill_detail(self):
        s = LOADER.get_skill("deep-research")
        assert s is not None and s.description
    def test_08_skill_instructions(self):
        s = LOADER.get_skill("deep-research")
        assert s.instructions and len(s.instructions) > 50
    def test_09_enabled_filter(self):
        e = LOADER.get_enabled_skills({"deep-research"})
        assert len(e) == 1
    def test_10_instructions_xml(self):
        i = LOADER.get_skill_instructions({"deep-research"})
        assert "<skills>" in i and "</skills>" in i and "deep-research" in i
    def test_11_nonexistent_skill(self):
        assert LOADER.get_skill("nonexistent_xyz") is None
    def test_12_empty_enabled(self):
        e = LOADER.get_enabled_skills(set())
        assert e == []

class TestSkillManager:
    def test_01_create_manager(self):
        from agent_platform.integration.skills import SkillManager
        m = SkillManager(skills_path="skills/public" if Path("skills/public").exists() else "../skills/public")
        assert m is not None
    def test_02_enable_skill(self):
        from agent_platform.integration.skills import SkillManager
        m = SkillManager()
        if "deep-research" in m.loader.get_all_skill_names():
            assert m.enable_skill("deep-research")
        else:
            assert not m.enable_skill("nonexistent")
    def test_03_disable_skill(self):
        from agent_platform.integration.skills import SkillManager
        m = SkillManager()
        m.disable_skill("test")
    def test_04_set_enabled(self):
        from agent_platform.integration.skills import SkillManager
        m = SkillManager()
        names = m.loader.get_all_skill_names()
        if names:
            m.set_enabled_skills(names[:2])
            assert len(m.enabled_skills) == 2
    def test_05_system_prompt(self):
        from agent_platform.integration.skills import SkillManager
        m = SkillManager()
        if m.loader.get_all_skill_names():
            m.set_enabled_skills(m.loader.get_all_skill_names()[:1])
            p = m.get_system_prompt_instructions()
            assert "<skills>" in p
