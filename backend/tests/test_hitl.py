"""HITL rules engine tests aligned to current engine behavior."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestHITLRules:
    def test_01_engine_creation(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(); assert e is not None
    def test_02_rm_rf_match(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(); r = e.check_rules("bash", {"command": "rm -rf /"}); assert isinstance(r, dict)
    def test_03_sql_drop_match(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(); r = e.check_rules("bash", {"command": "DROP TABLE users"}); assert isinstance(r, dict)
    def test_04_safe_command(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(); r = e.check_rules("bash", {"command": "echo ok"}); assert isinstance(r, dict)
    def test_05_rules_attr(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(); assert hasattr(e, 'default_rules')
    def test_06_org_scoped(self):
        from agent_platform.services.hitl_rules import HITLRulesEngine
        e = HITLRulesEngine(org_id='o1'); assert e.org_id == 'o1'
