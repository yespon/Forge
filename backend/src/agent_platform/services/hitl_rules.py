"""HITL Rules Engine for determining when human approval is required."""

import hashlib
import json
import re
from typing import Any, Optional

from agent_platform.models.approval import ApprovalStrategy, RiskLevel


class HITLRulesEngine:
    """Rules engine for Human-in-the-Loop approval system.

    This engine evaluates tool calls against defined rules to determine
    if human approval is required before execution.
    """

    # Default rules for common dangerous operations
    DEFAULT_RULES = [
        {
            "name": "Block rm -rf commands",
            "description": "Critical risk: rm -rf can delete entire directory trees",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"rm\s+-rf.*|rm\s+-fr.*|rm\s+.*-rf.*|rm\s+.*-fr.*"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block dangerous SQL DROP",
            "description": "Critical risk: DROP statements can destroy data",
            "tool_name_pattern": "execute_sql",
            "argument_patterns": {
                "command": r"(?i)DROP\s+(TABLE|DATABASE|SCHEMA|INDEX)"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.MULTI,
            "min_approvals_required": 2,
        },
        {
            "name": "Block dangerous SQL DELETE without WHERE",
            "description": "High risk: DELETE without WHERE clause removes all rows",
            "tool_name_pattern": "execute_sql",
            "argument_patterns": {
                "command": r"(?i)DELETE\s+FROM\s+\w+\s*;?$|DELETE\s+FROM\s+\w+\s*$"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block SQL DELETE with WHERE",
            "description": "Medium risk: DELETE operations on data",
            "tool_name_pattern": "execute_sql",
            "argument_patterns": {
                "command": r"(?i)DELETE\s+FROM\s+\w+\s+WHERE"
            },
            "risk_level": RiskLevel.MEDIUM,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block dangerous SQL UPDATE without WHERE",
            "description": "High risk: UPDATE without WHERE modifies all rows",
            "tool_name_pattern": "execute_sql",
            "argument_patterns": {
                "command": r"(?i)UPDATE\s+\w+\s+SET\s+.*;?$|UPDATE\s+\w+\s+SET\s+[^W]*$"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block database truncation",
            "description": "Critical risk: TRUNCATE removes all data instantly",
            "tool_name_pattern": "execute_sql",
            "argument_patterns": {
                "command": r"(?i)TRUNCATE\s+(TABLE\s+)?\w+"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.MULTI,
            "min_approvals_required": 2,
        },
        {
            "name": "Block filesystem writes to system directories",
            "description": "High risk: Writing to system directories",
            "tool_name_pattern": "write_file",
            "argument_patterns": {
                "path": r"^/(etc|bin|sbin|lib|usr|var|opt|sys|dev|boot)/.*"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block shell redirection to system files",
            "description": "Critical risk: Redirecting output to system files",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r">\s*/(etc|bin|sbin|lib|usr|var|opt|sys|dev|boot)/.*"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.MULTI,
        },
        {
            "name": "Block dd command to disk devices",
            "description": "Critical risk: dd can overwrite disk devices",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"dd\s+.*of=/dev/[sh]d[a-z]|dd\s+.*of=/dev/nvme"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.MULTI,
            "min_approvals_required": 2,
        },
        {
            "name": "Block mkfs commands",
            "description": "Critical risk: mkfs formats filesystems",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"mkfs\.?\w*\s+/dev/"
            },
            "risk_level": RiskLevel.CRITICAL,
            "strategy": ApprovalStrategy.MULTI,
            "min_approvals_required": 2,
        },
        {
            "name": "Block dangerous curl/wget with output",
            "description": "High risk: Downloading and executing remote scripts",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"curl\s+.*\|\s*(sh|bash|zsh)|wget\s+.*-O-\s*\|\s*(sh|bash|zsh)"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block sudo privilege escalation",
            "description": "High risk: Commands using sudo",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"^sudo\s+|\|\s*sudo\s+|&&\s*sudo\s+"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block chmod on system files",
            "description": "High risk: Changing permissions on system files",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"chmod\s+.*\s+/.*etc.*|chmod\s+.*\s+/.*bin.*"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block dangerous find with exec",
            "description": "High risk: find with -exec can execute arbitrary commands",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"find\s+.*-exec\s+(rm|mv|chmod|chown)"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block kill commands",
            "description": "Medium risk: Process termination commands",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"kill\s+-9|killall|pkill"
            },
            "risk_level": RiskLevel.MEDIUM,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block systemctl stop/restart",
            "description": "High risk: Stopping system services",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"systemctl\s+(stop|restart|disable)\s+"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.SINGLE,
        },
        {
            "name": "Block user deletion commands",
            "description": "High risk: Deleting user accounts",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"userdel|userdel\s+-r|deluser"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.MULTI,
        },
        {
            "name": "Block network configuration changes",
            "description": "High risk: Modifying network settings",
            "tool_name_pattern": "(execute_)?bash",
            "argument_patterns": {
                "command": r"iptables|nftables|ip\s+link\s+set|ifconfig.*\s+(up|down)"
            },
            "risk_level": RiskLevel.HIGH,
            "strategy": ApprovalStrategy.MULTI,
        },
    ]

    def __init__(
        self,
        custom_rules: Optional[list[dict]] = None,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ):
        """Initialize the HITL rules engine.

        Args:
            custom_rules: Optional list of custom rules to add
            org_id: Optional organization ID for fetching org-specific rules
            team_id: Optional team ID for fetching team-specific rules
        """
        self.org_id = org_id
        self.team_id = team_id
        self.default_rules = self.DEFAULT_RULES.copy()
        self.custom_rules = custom_rules or []

    @property
    def all_rules(self) -> list[dict]:
        """Get all active rules (default + custom)."""
        return self.default_rules + self.custom_rules

    def check_rules(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Check if a tool call matches any HITL rules.

        Args:
            tool_name: Name of the tool being called
            tool_input: Input arguments for the tool
            context: Optional additional context

        Returns:
            Dictionary with:
                - requires_approval: bool
                - risk_level: RiskLevel or None
                - matched_rule: Name of matched rule or None
                - description: Description of why approval is needed
                - strategy: ApprovalStrategy to use
                - min_approvals_required: int
        """
        matched_rules = []

        for rule in self.all_rules:
            if not rule.get("is_active", True):
                continue

            match_result = self._match_rule(rule, tool_name, tool_input)
            if match_result:
                matched_rules.append((rule, match_result))

        if not matched_rules:
            return {
                "requires_approval": False,
                "risk_level": None,
                "matched_rule": None,
                "description": None,
                "strategy": None,
                "min_approvals_required": 0,
            }

        # Sort by risk level (highest first)
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        matched_rules.sort(
            key=lambda x: risk_order.get(RiskLevel(x[0].get("risk_level", "low")), 0),
            reverse=True,
        )

        # Return the highest risk match
        highest_rule, match_details = matched_rules[0]

        return {
            "requires_approval": True,
            "risk_level": RiskLevel(highest_rule.get("risk_level", "medium")),
            "matched_rule": highest_rule.get("name"),
            "description": highest_rule.get("description"),
            "strategy": highest_rule.get("strategy", ApprovalStrategy.SINGLE),
            "min_approvals_required": highest_rule.get("min_approvals_required", 1),
            "matched_patterns": match_details,
        }

    def _match_rule(
        self,
        rule: dict,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> Optional[dict]:
        """Check if a specific rule matches the tool call.

        Args:
            rule: Rule definition to check
            tool_name: Name of the tool
            tool_input: Tool input arguments

        Returns:
            Dictionary of matched patterns if rule matches, None otherwise
        """
        # Check tool name pattern
        rule_tool_pattern = rule.get("tool_name_pattern", "")
        if not self._pattern_matches(rule_tool_pattern, tool_name):
            return None

        # Check argument patterns
        argument_patterns = rule.get("argument_patterns", {})
        matched_patterns = {}

        for arg_name, pattern in argument_patterns.items():
            arg_value = tool_input.get(arg_name, "")
            if isinstance(arg_value, str):
                if self._pattern_matches(pattern, arg_value):
                    matched_patterns[arg_name] = pattern
                else:
                    # Pattern didn't match, rule doesn't apply
                    return None
            elif isinstance(arg_value, (dict, list)):
                # For complex types, convert to string for pattern matching
                str_value = json.dumps(arg_value)
                if self._pattern_matches(pattern, str_value):
                    matched_patterns[arg_name] = pattern
                else:
                    return None
            else:
                # Non-string value didn't match
                return None

        return matched_patterns if matched_patterns else {"tool_name": rule_tool_pattern}

    def _pattern_matches(self, pattern: str, value: str) -> bool:
        """Check if a value matches a pattern.

        Args:
            pattern: Regex pattern to match
            value: Value to check

        Returns:
            True if value matches pattern
        """
        try:
            return bool(re.search(pattern, value))
        except re.error:
            # If regex is invalid, do simple string containment
            return pattern in value

    def compute_input_hash(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Compute a hash of the tool input for deduplication.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input arguments

        Returns:
            SHA-256 hash of the tool call
        """
        data = {
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    def add_rule(self, rule: dict) -> None:
        """Add a custom rule to the engine.

        Args:
            rule: Rule definition dictionary
        """
        self.custom_rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a custom rule by name.

        Args:
            rule_name: Name of the rule to remove

        Returns:
            True if rule was found and removed
        """
        for i, rule in enumerate(self.custom_rules):
            if rule.get("name") == rule_name:
                self.custom_rules.pop(i)
                return True
        return False

    def get_rules_for_risk_level(self, risk_level: RiskLevel) -> list[dict]:
        """Get all rules for a specific risk level.

        Args:
            risk_level: Risk level to filter by

        Returns:
            List of matching rules
        """
        return [
            rule for rule in self.all_rules
            if RiskLevel(rule.get("risk_level", "low")) == risk_level
        ]

    def is_tool_blocked(self, tool_name: str) -> bool:
        """Check if a tool is completely blocked (always requires approval).

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is blocked
        """
        for rule in self.all_rules:
            if rule.get("tool_name_pattern") == tool_name:
                if rule.get("risk_level") == RiskLevel.CRITICAL:
                    if not rule.get("argument_patterns"):
                        return True
        return False
