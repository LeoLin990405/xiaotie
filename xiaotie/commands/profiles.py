"""
Profiles management commands Mixin.
"""

from .base import CommandsBase

class ProfilesCommandsMixin(CommandsBase):
    """Profiles related commands like profiles, profile"""
    
    def cmd_profiles(self, args: str) -> tuple[bool, str]:
        """列出所有配置 profiles"""
        from xiaotie.profiles import ProfileManager

        mgr = ProfileManager()
        profiles = mgr.list_profiles()

        if not profiles:
            return True, "📭 暂无保存的 profiles\\n\\n使用 /profile-new <名称> 创建"

        lines = ["\\n📋 可用 Profiles:\\n"]
        for name in profiles:
            try:
                config = mgr.load_profile(name)
                lines.append(f"  • {name}: {config.description or '无描述'}")
            except Exception:
                lines.append(f"  • {name}: (加载失败)")

        return True, "\\n".join(lines)

    def cmd_profile(self, args: str) -> tuple[bool, str]:
        """切换或显示当前 profile (用法: /profile [名称])"""
        from xiaotie.profiles import ProfileManager

        mgr = ProfileManager()

        if not args:
            current = mgr.get_current_profile()
            if current:
                return True, f"📋 当前 Profile: {current.name}"
            return True, "📋 未设置 Profile"

        name = args.strip()
        try:
            mgr.set_current_profile(name)
            return True, f"✅ 已切换到 Profile: {name}"
        except ValueError as e:
            return True, f"❌ {e}"
