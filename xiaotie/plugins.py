"""插件系统

支持自定义工具和命令的热加载

使用方法:
1. 在 ~/.xiaotie/plugins/ 目录下创建 Python 文件
2. 定义继承自 Tool 的类
3. 启动时自动发现和加载

示例插件:
```python
# ~/.xiaotie/plugins/my_tool.py
from xiaotie.tools import Tool, ToolResult

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "我的自定义工具"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入参数"}
            },
            "required": ["input"]
        }

    async def execute(self, input: str) -> ToolResult:
        return ToolResult(success=True, content=f"处理结果: {input}")
```
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Optional

from .tools.base import Tool


class PluginManager:
    """插件管理器"""

    DEFAULT_PLUGIN_DIRS = [
        Path.home() / ".xiaotie" / "plugins",
        Path.cwd() / "plugins",
    ]

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        """初始化插件管理器

        Args:
            plugin_dirs: 插件目录列表，默认为 ~/.xiaotie/plugins 和 ./plugins
        """
        self.plugin_dirs = plugin_dirs or self.DEFAULT_PLUGIN_DIRS
        self._loaded_tools: dict[str, Tool] = {}
        self._loaded_modules: dict[str, object] = {}

    def discover_plugins(self) -> List[Path]:
        """发现所有插件文件"""
        plugin_files = []

        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue

            # 查找所有 .py 文件（排除 __init__.py 和 _ 开头的文件）
            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                plugin_files.append(py_file)

        return plugin_files

    def load_plugin(self, plugin_path: Path) -> List[Tool]:
        """加载单个插件文件

        Args:
            plugin_path: 插件文件路径

        Returns:
            加载的工具列表
        """
        tools = []

        try:
            # 动态导入模块
            module_name = f"xiaotie_plugin_{plugin_path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)

            if spec is None or spec.loader is None:
                print(f"⚠️ 无法加载插件: {plugin_path}")
                return tools

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            self._loaded_modules[module_name] = module

            # 查找所有 Tool 子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # 检查是否是 Tool 的子类（但不是 Tool 本身）
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Tool)
                    and attr is not Tool
                    and not attr_name.startswith("_")
                ):
                    try:
                        # 实例化工具
                        tool_instance = attr()
                        tools.append(tool_instance)
                        self._loaded_tools[tool_instance.name] = tool_instance
                        print(f"  ✓ 加载工具: {tool_instance.name}")
                    except Exception as e:
                        print(f"  ✗ 实例化工具 {attr_name} 失败: {e}")

        except Exception as e:
            print(f"⚠️ 加载插件 {plugin_path.name} 失败: {e}")

        return tools

    def load_all_plugins(self) -> List[Tool]:
        """加载所有插件

        Returns:
            所有加载的工具列表
        """
        all_tools = []
        plugin_files = self.discover_plugins()

        if not plugin_files:
            return all_tools

        print(f"📦 发现 {len(plugin_files)} 个插件...")

        for plugin_path in plugin_files:
            tools = self.load_plugin(plugin_path)
            all_tools.extend(tools)

        return all_tools

    def get_loaded_tools(self) -> dict[str, Tool]:
        """获取所有已加载的工具"""
        return self._loaded_tools.copy()

    def reload_plugin(self, plugin_name: str) -> bool:
        """重新加载指定插件

        Args:
            plugin_name: 插件名称（不含 .py 后缀）

        Returns:
            是否成功重新加载
        """
        # 查找插件文件
        for plugin_dir in self.plugin_dirs:
            plugin_path = plugin_dir / f"{plugin_name}.py"
            if plugin_path.exists():
                # 卸载旧模块
                module_name = f"xiaotie_plugin_{plugin_name}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                if module_name in self._loaded_modules:
                    del self._loaded_modules[module_name]

                # 重新加载
                tools = self.load_plugin(plugin_path)
                return len(tools) > 0

        return False

    def create_plugin_template(self, name: str, plugin_dir: Optional[Path] = None) -> Path:
        """创建插件模板

        Args:
            name: 插件名称
            plugin_dir: 插件目录，默认为 ~/.xiaotie/plugins

        Returns:
            创建的插件文件路径
        """
        if plugin_dir is None:
            plugin_dir = self.DEFAULT_PLUGIN_DIRS[0]

        # 确保目录存在
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_path = plugin_dir / f"{name}.py"

        template = f'''"""自定义插件: {name}

创建时间: 自动生成
"""

from xiaotie.tools import Tool, ToolResult


class {name.title().replace("_", "")}Tool(Tool):
    """自定义工具示例"""

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def description(self) -> str:
        return "自定义工具描述"

    @property
    def parameters(self) -> dict:
        return {{
            "type": "object",
            "properties": {{
                "input": {{
                    "type": "string",
                    "description": "输入参数",
                }},
            }},
            "required": ["input"],
        }}

    async def execute(self, input: str) -> ToolResult:
        """执行工具

        Args:
            input: 输入参数

        Returns:
            工具执行结果
        """
        try:
            # 在这里实现你的逻辑
            result = f"处理结果: {{input}}"
            return ToolResult(success=True, content=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
'''

        plugin_path.write_text(template, encoding="utf-8")
        return plugin_path
