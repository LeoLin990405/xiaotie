"""权限系统测试"""

import pytest

from xiaotie.permissions import (
    DEFAULT_RISK_RULES,
    DANGEROUS_PATTERNS,
    SAFE_PATTERNS,
    PermissionManager,
    PermissionRequest,
    PermissionRule,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# 风险等级
# ---------------------------------------------------------------------------

class TestRiskLevel:
    def test_enum_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_default_rules_exist(self):
        assert "read_file" in DEFAULT_RISK_RULES
        assert "bash" in DEFAULT_RISK_RULES
        assert DEFAULT_RISK_RULES["read_file"] == RiskLevel.LOW
        assert DEFAULT_RISK_RULES["bash"] == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# PermissionManager - 风险检测
# ---------------------------------------------------------------------------

class TestPermissionManagerRisk:
    def test_low_risk_tool(self):
        pm = PermissionManager()
        level = pm._get_risk_level("read_file", {})
        assert level == RiskLevel.LOW

    def test_high_risk_tool(self):
        pm = PermissionManager()
        level = pm._get_risk_level("bash", {"command": "python script.py"})
        assert level == RiskLevel.HIGH

    def test_dangerous_command_is_critical(self):
        pm = PermissionManager()
        level = pm._get_risk_level("bash", {"command": "rm -rf /"})
        assert level == RiskLevel.CRITICAL

    def test_safe_command_is_low(self):
        pm = PermissionManager()
        level = pm._get_risk_level("bash", {"command": "git status"})
        assert level == RiskLevel.LOW

    def test_unknown_tool_defaults_medium(self):
        pm = PermissionManager()
        level = pm._get_risk_level("unknown_tool", {})
        assert level == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# PermissionManager - 权限检查
# ---------------------------------------------------------------------------

class TestPermissionCheck:
    async def test_low_risk_auto_approved(self):
        pm = PermissionManager(auto_approve_low_risk=True)
        allowed, reason = await pm.check_permission("read_file", {"path": "a.txt"})
        assert allowed is True

    async def test_critical_denied(self):
        pm = PermissionManager()
        allowed, reason = await pm.check_permission(
            "bash", {"command": "sudo rm -rf /"}
        )
        assert allowed is False
        assert "危险" in reason

    async def test_non_interactive_medium_approved(self):
        pm = PermissionManager(interactive=False)
        allowed, _ = await pm.check_permission("write_file", {"path": "b.txt"})
        assert allowed is True

    async def test_non_interactive_high_denied(self):
        pm = PermissionManager(interactive=False)
        allowed, _ = await pm.check_permission(
            "bash", {"command": "python script.py"}
        )
        assert allowed is False

    async def test_whitelist_overrides(self):
        pm = PermissionManager()
        pm.add_to_whitelist("write_file")
        allowed, reason = await pm.check_permission(
            "write_file", {"path": "c.txt"}
        )
        assert allowed is True
        assert "白名单" in reason

    async def test_permanent_whitelist(self):
        pm = PermissionManager()
        pm.add_to_whitelist("bash", permanent=True)
        assert "bash" in pm._permanent_whitelist

    async def test_custom_callback(self):
        pm = PermissionManager()
        pm.set_approval_callback(lambda req: True)
        allowed, _ = await pm.check_permission(
            "bash", {"command": "python test.py"}
        )
        assert allowed is True

    async def test_stats(self):
        pm = PermissionManager()
        stats = pm.get_stats()
        assert stats["total_requests"] == 0
        assert "auto_approve_low_risk" in stats
