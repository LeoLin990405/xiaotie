"""权限系统

参考 Claude Code 的 Human-in-the-Loop 设计：
- 工具调用前请求确认
- 风险分类（低/中/高）
- 白名单机制
- 批量审批
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"           # 只读操作
    MEDIUM = "medium"     # 可逆操作
    HIGH = "high"         # 不可逆/危险操作
    CRITICAL = "critical" # 系统级危险操作


@dataclass
class PermissionRule:
    """权限规则"""
    tool_name: str
    risk_level: RiskLevel
    patterns: List[str] = field(default_factory=list)  # 参数匹配模式
    description: str = ""
    auto_approve: bool = False  # 是否自动批准


# 默认风险规则
DEFAULT_RISK_RULES: Dict[str, RiskLevel] = {
    # 只读工具 - 低风险
    "read_file": RiskLevel.LOW,
    "calculator": RiskLevel.LOW,
    "web_search": RiskLevel.LOW,
    "web_fetch": RiskLevel.LOW,
    "code_analysis": RiskLevel.LOW,
    "git_status": RiskLevel.LOW,
    "git_diff": RiskLevel.LOW,
    "git_log": RiskLevel.LOW,

    # 写入工具 - 中风险
    "write_file": RiskLevel.MEDIUM,
    "edit_file": RiskLevel.MEDIUM,
    "python": RiskLevel.MEDIUM,

    # 系统命令 - 高风险
    "bash": RiskLevel.HIGH,
    "git_commit": RiskLevel.MEDIUM,
}

# 危险命令模式
DANGEROUS_PATTERNS = [
    # 删除操作
    r"rm\s+-rf",
    r"rm\s+-r",
    r"rmdir",
    r"del\s+/[sS]",

    # 系统修改
    r"sudo\s+",
    r"chmod\s+777",
    r"chown\s+-R",

    # 网络操作
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"curl.*\|\s*bash",

    # Git 危险操作
    r"git\s+push\s+.*--force",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-fd",

    # 进程操作
    r"kill\s+-9",
    r"pkill",
    r"killall",

    # 磁盘操作
    r"dd\s+if=",
    r"mkfs",
    r"fdisk",
]

# 安全命令模式（自动批准）
SAFE_PATTERNS = [
    r"^ls\s",
    r"^pwd$",
    r"^echo\s",
    r"^cat\s",
    r"^head\s",
    r"^tail\s",
    r"^grep\s",
    r"^find\s",
    r"^which\s",
    r"^whoami$",
    r"^date$",
    r"^git\s+status",
    r"^git\s+diff",
    r"^git\s+log",
    r"^git\s+branch",
    r"^npm\s+list",
    r"^pip\s+list",
    r"^python\s+--version",
    r"^node\s+--version",
]


@dataclass
class PermissionRequest:
    """权限请求"""
    tool_name: str
    arguments: Dict[str, Any]
    risk_level: RiskLevel
    description: str
    requires_approval: bool = True


class PermissionManager:
    """权限管理器"""

    def __init__(
        self,
        auto_approve_low_risk: bool = True,
        auto_approve_patterns: Optional[List[str]] = None,
        deny_patterns: Optional[List[str]] = None,
        interactive: bool = True,
    ):
        self.auto_approve_low_risk = auto_approve_low_risk
        self.auto_approve_patterns = auto_approve_patterns or SAFE_PATTERNS
        self.deny_patterns = deny_patterns or DANGEROUS_PATTERNS
        self.interactive = interactive

        # 会话级白名单
        self._session_whitelist: Set[str] = set()
        # 永久白名单
        self._permanent_whitelist: Set[str] = set()
        # 审批历史
        self._approval_history: List[PermissionRequest] = []
        # 自定义审批回调
        self._approval_callback: Optional[Callable[[PermissionRequest], bool]] = None

    def set_approval_callback(self, callback: Callable[[PermissionRequest], bool]):
        """设置自定义审批回调"""
        self._approval_callback = callback

    def add_to_whitelist(self, pattern: str, permanent: bool = False):
        """添加到白名单"""
        if permanent:
            self._permanent_whitelist.add(pattern)
        else:
            self._session_whitelist.add(pattern)

    def _get_risk_level(self, tool_name: str, arguments: Dict[str, Any]) -> RiskLevel:
        """获取风险等级"""
        base_risk = DEFAULT_RISK_RULES.get(tool_name, RiskLevel.MEDIUM)

        # 对 bash 命令进行额外检查
        if tool_name == "bash":
            command = arguments.get("command", "")

            # 检查危险模式
            for pattern in self.deny_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return RiskLevel.CRITICAL

            # 检查安全模式
            for pattern in self.auto_approve_patterns:
                if re.match(pattern, command, re.IGNORECASE):
                    return RiskLevel.LOW

        return base_risk

    def _is_whitelisted(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查是否在白名单中"""
        # 构建检查字符串
        if tool_name == "bash":
            check_str = arguments.get("command", "")
        else:
            check_str = f"{tool_name}:{arguments}"

        # 检查白名单
        for pattern in self._session_whitelist | self._permanent_whitelist:
            if re.search(pattern, check_str, re.IGNORECASE):
                return True

        return False

    def _format_request(self, request: PermissionRequest) -> str:
        """格式化权限请求显示"""
        risk_icons = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }

        icon = risk_icons.get(request.risk_level, "⚪")

        lines = [
            f"\n{icon} 权限请求 [{request.risk_level.value.upper()}]",
            f"   工具: {request.tool_name}",
        ]

        # 格式化参数
        for key, value in request.arguments.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            lines.append(f"   {key}: {value_str}")

        return "\n".join(lines)

    async def check_permission(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> tuple[bool, str]:
        """检查权限

        Returns:
            (是否允许, 原因)
        """
        risk_level = self._get_risk_level(tool_name, arguments)

        # 创建请求
        request = PermissionRequest(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            description=self._format_request_description(tool_name, arguments),
        )

        # 检查白名单
        if self._is_whitelisted(tool_name, arguments):
            return True, "白名单"

        # 低风险自动批准
        if self.auto_approve_low_risk and risk_level == RiskLevel.LOW:
            return True, "低风险自动批准"

        # 危险操作拒绝
        if risk_level == RiskLevel.CRITICAL:
            return False, f"危险操作被拒绝: {request.description}"

        # 非交互模式
        if not self.interactive:
            if risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
                return True, "非交互模式自动批准"
            return False, "非交互模式拒绝高风险操作"

        # 自定义回调
        if self._approval_callback:
            approved = self._approval_callback(request)
            self._approval_history.append(request)
            return approved, "用户决定"

        # 默认交互式确认
        return await self._interactive_confirm(request)

    def _format_request_description(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """格式化请求描述"""
        if tool_name == "bash":
            return f"执行命令: {arguments.get('command', '')[:50]}"
        elif tool_name == "write_file":
            return f"写入文件: {arguments.get('path', '')}"
        elif tool_name == "edit_file":
            return f"编辑文件: {arguments.get('path', '')}"
        else:
            return f"{tool_name}({', '.join(f'{k}={v}' for k, v in list(arguments.items())[:3])})"

    async def _interactive_confirm(self, request: PermissionRequest) -> tuple[bool, str]:
        """交互式确认"""
        print(self._format_request(request))
        print("\n   [y] 允许  [n] 拒绝  [a] 允许并加入白名单  [q] 退出")

        try:
            response = input("   选择: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False, "用户取消"

        if response == "y":
            self._approval_history.append(request)
            return True, "用户允许"
        elif response == "a":
            # 添加到会话白名单
            if request.tool_name == "bash":
                pattern = re.escape(request.arguments.get("command", "")[:30])
            else:
                pattern = request.tool_name
            self.add_to_whitelist(pattern)
            self._approval_history.append(request)
            return True, "用户允许并加入白名单"
        elif response == "q":
            raise KeyboardInterrupt("用户退出")
        else:
            return False, "用户拒绝"

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": len(self._approval_history),
            "session_whitelist": len(self._session_whitelist),
            "permanent_whitelist": len(self._permanent_whitelist),
            "auto_approve_low_risk": self.auto_approve_low_risk,
        }
