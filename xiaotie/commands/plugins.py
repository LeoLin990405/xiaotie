"""
Plugins related commands Mixin.
"""

from .base import CommandsBase


class PluginsCommandsMixin(CommandsBase):
    """Plugins related commands like plugins, plugin-new, plugin-reload"""

    def cmd_plugins(self, args: str) -> tuple[bool, str]:
        """显示已加载的插件"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        tools = self.plugin_mgr.get_loaded_tools()
        if not tools:
            lines = [
                "\\n📦 插件系统",
                "",
                "  暂无已加载的插件",
                "",
                "  创建插件: /plugin-new <名称>",
                f"  插件目录: {self.plugin_mgr.DEFAULT_PLUGIN_DIRS[0]}",
            ]
            return True, "\\n".join(lines)

        lines = [f"\\n📦 已加载 {len(tools)} 个插件工具:\\n"]
        for name, tool in tools.items():
            desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
            lines.append(f"  • {name}: {desc}")

        return True, "\\n".join(lines)

    def cmd_plugin_new(self, args: str) -> tuple[bool, str]:
        """创建新插件模板 (用法: /plugin-new <名称>)"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        if not args:
            return True, "用法: /plugin-new <插件名称>"

        name = args.strip().lower().replace("-", "_").replace(" ", "_")
        plugin_path = self.plugin_mgr.create_plugin_template(name)

        return (
            True,
            f"✅ 插件模板已创建: {plugin_path}\\n\\n编辑后重启或使用 /plugin-reload {name} 加载",
        )

    def cmd_plugin_reload(self, args: str) -> tuple[bool, str]:
        """重新加载插件 (用法: /plugin-reload <名称>)"""
        if not self.plugin_mgr:
            return True, "⚠️ 插件系统未启用"

        if not args:
            return True, "用法: /plugin-reload <插件名称>"

        name = args.strip()
        if self.plugin_mgr.reload_plugin(name):
            # 更新 agent 的工具列表
            new_tools = self.plugin_mgr.get_loaded_tools()
            for tool_name, tool in new_tools.items():
                self.agent.tools[tool_name] = tool
            return True, f"✅ 插件 {name} 已重新加载"
        else:
            return True, f"❌ 插件 {name} 重新加载失败"
