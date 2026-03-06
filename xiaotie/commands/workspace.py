"""
Workspace mapping and visualization commands Mixin.
"""

from .base import CommandsBase

class WorkspaceCommandsMixin(CommandsBase):
    """Workspace related commands like tree, map, find"""
    
    def cmd_tree(self, args: str) -> tuple[bool, str]:
        """显示项目目录结构"""
        from xiaotie.repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        max_depth = 3
        if args:
            try:
                max_depth = int(args.strip())
            except ValueError:
                pass

        tree = repo_map.get_tree(max_depth=max_depth)
        return True, f"\\n{tree}"

    def cmd_map(self, args: str) -> tuple[bool, str]:
        """显示代码库概览（类、函数定义）"""
        from xiaotie.repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        max_tokens = 2000
        if args:
            try:
                max_tokens = int(args.strip())
            except ValueError:
                pass

        repo_overview = repo_map.get_repo_map(max_tokens=max_tokens)
        return True, f"\\n{repo_overview}"

    def cmd_find(self, args: str) -> tuple[bool, str]:
        """搜索相关文件 (用法: /find <关键词>)"""
        if not args:
            return True, "用法: /find <关键词>"

        from xiaotie.repomap import RepoMap

        workspace = self.agent.workspace_dir
        repo_map = RepoMap(workspace)

        files = repo_map.find_relevant_files(args.strip(), limit=10)

        if not files:
            return True, f"未找到与 '{args}' 相关的文件"

        lines = [f"\\n🔍 搜索结果: {args}\\n"]
        for f in files:
            defn_count = len(f.definitions)
            icon = "⭐" if f.is_important else "📄"
            lines.append(f"  {icon} {f.relative_path}")
            if defn_count > 0:
                lines.append(f"      └─ {defn_count} 个定义")

        return True, "\\n".join(lines)
