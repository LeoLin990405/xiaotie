"""代码库映射模块

学习自 Aider 的 RepoMap 设计：
- 自动分析项目结构
- 提取代码定义（类、函数）
- 智能上下文选择
- Token 预算管理
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

# 常见的忽略模式
DEFAULT_IGNORE_PATTERNS = {
    # 目录
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".pytest_cache",
    "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "target", "out", "bin", "obj",
    ".idea", ".vscode", ".eclipse",
    "coverage", ".nyc_output",
    # 文件模式
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib",
    "*.egg-info", "*.egg",
    "*.min.js", "*.min.css",
    "*.map", "*.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
}

# 代码文件扩展名
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt", ".scala",
    ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".swift", ".m",
    ".cs", ".fs", ".vb",
    ".lua", ".pl", ".r",
    ".sh", ".bash", ".zsh",
    ".sql", ".graphql",
    ".vue", ".svelte",
}

# 重要文件（优先显示）
IMPORTANT_FILES = {
    "README.md", "README.rst", "README.txt", "README",
    "setup.py", "pyproject.toml", "setup.cfg",
    "package.json", "tsconfig.json",
    "Cargo.toml", "go.mod", "build.gradle",
    "Makefile", "CMakeLists.txt",
    "Dockerfile", "docker-compose.yml",
    ".env.example", "config.yaml", "config.json",
}


@dataclass
class CodeDefinition:
    """代码定义"""
    name: str
    kind: str  # class, function, method, variable
    file_path: str
    line_number: int
    signature: str = ""


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    relative_path: str
    size: int
    lines: int = 0
    definitions: List[CodeDefinition] = field(default_factory=list)
    is_important: bool = False


class RepoMap:
    """代码库映射"""

    def __init__(
        self,
        workspace_dir: str,
        ignore_patterns: Optional[Set[str]] = None,
        max_file_size: int = 100_000,  # 100KB
    ):
        self.workspace = Path(workspace_dir).absolute()
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        self.max_file_size = max_file_size
        self._cache: Dict[str, FileInfo] = {}

    def _should_ignore(self, path: Path) -> bool:
        """检查是否应该忽略"""
        name = path.name

        # 检查目录/文件名
        if name in self.ignore_patterns:
            return True

        # 检查通配符模式
        for pattern in self.ignore_patterns:
            if pattern.startswith("*") and name.endswith(pattern[1:]):
                return True

        # 检查隐藏文件（除了重要的配置文件）
        if name.startswith(".") and name not in {".env.example", ".gitignore"}:
            return True

        return False

    def _is_code_file(self, path: Path) -> bool:
        """检查是否是代码文件"""
        return path.suffix.lower() in CODE_EXTENSIONS

    def _extract_python_definitions(self, content: str, file_path: str) -> List[CodeDefinition]:
        """提取 Python 代码定义"""
        definitions = []

        # 匹配类定义
        class_pattern = r'^class\s+(\w+)(?:\([^)]*\))?:'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            line_num = content[:match.start()].count('\n') + 1
            definitions.append(CodeDefinition(
                name=match.group(1),
                kind="class",
                file_path=file_path,
                line_number=line_num,
                signature=match.group(0).rstrip(':'),
            ))

        # 匹配函数定义
        func_pattern = r'^(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?:'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            line_num = content[:match.start()].count('\n') + 1
            # 检查是否是方法（缩进）
            line_start = content.rfind('\n', 0, match.start()) + 1
            indent = match.start() - line_start
            kind = "method" if indent > 0 else "function"

            definitions.append(CodeDefinition(
                name=match.group(1),
                kind=kind,
                file_path=file_path,
                line_number=line_num,
                signature=match.group(0).rstrip(':'),
            ))

        return definitions

    def _extract_js_definitions(self, content: str, file_path: str) -> List[CodeDefinition]:
        """提取 JavaScript/TypeScript 代码定义"""
        definitions = []

        # 匹配类定义
        class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*\{'
        for match in re.finditer(class_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            definitions.append(CodeDefinition(
                name=match.group(1),
                kind="class",
                file_path=file_path,
                line_number=line_num,
            ))

        # 匹配函数定义
        func_patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(',
            r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function',
        ]
        for pattern in func_patterns:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count('\n') + 1
                definitions.append(CodeDefinition(
                    name=match.group(1),
                    kind="function",
                    file_path=file_path,
                    line_number=line_num,
                ))

        return definitions

    def _extract_definitions(self, content: str, file_path: str) -> List[CodeDefinition]:
        """提取代码定义"""
        suffix = Path(file_path).suffix.lower()

        if suffix == ".py":
            return self._extract_python_definitions(content, file_path)
        elif suffix in {".js", ".ts", ".jsx", ".tsx"}:
            return self._extract_js_definitions(content, file_path)

        return []

    def scan_files(self) -> List[FileInfo]:
        """扫描工作目录中的文件"""
        files = []

        for root, dirs, filenames in os.walk(self.workspace):
            # 过滤目录
            dirs[:] = [d for d in dirs if not self._should_ignore(Path(root) / d)]

            for filename in filenames:
                file_path = Path(root) / filename

                if self._should_ignore(file_path):
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size > self.max_file_size:
                        continue

                    relative_path = str(file_path.relative_to(self.workspace))
                    is_important = filename in IMPORTANT_FILES

                    file_info = FileInfo(
                        path=str(file_path),
                        relative_path=relative_path,
                        size=stat.st_size,
                        is_important=is_important,
                    )

                    # 对代码文件提取定义
                    if self._is_code_file(file_path):
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            file_info.lines = content.count('\n') + 1
                            file_info.definitions = self._extract_definitions(content, relative_path)
                        except Exception:
                            pass

                    files.append(file_info)
                    self._cache[relative_path] = file_info

                except (OSError, PermissionError):
                    continue

        return files

    def get_tree(self, max_depth: int = 3) -> str:
        """生成目录树"""
        lines = [f"📁 {self.workspace.name}/"]

        def add_tree(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return

            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return

            # 过滤
            items = [i for i in items if not self._should_ignore(i)]

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                new_prefix = prefix + ("    " if is_last else "│   ")

                if item.is_dir():
                    lines.append(f"{prefix}{connector}📁 {item.name}/")
                    add_tree(item, new_prefix, depth + 1)
                else:
                    icon = "📄"
                    if item.name in IMPORTANT_FILES:
                        icon = "⭐"
                    elif self._is_code_file(item):
                        icon = "📝"
                    lines.append(f"{prefix}{connector}{icon} {item.name}")

        add_tree(self.workspace, "", 1)
        return "\n".join(lines)

    def get_repo_map(self, max_tokens: int = 2000) -> str:
        """生成代码库概览

        Args:
            max_tokens: 最大 token 数（粗略估算）

        Returns:
            代码库概览文本
        """
        files = self.scan_files()

        # 按重要性和定义数量排序
        files.sort(key=lambda f: (
            -int(f.is_important),
            -len(f.definitions),
            f.relative_path,
        ))

        lines = ["# 代码库概览\n"]

        # 添加目录树
        tree = self.get_tree(max_depth=2)
        lines.append("## 目录结构\n```")
        lines.append(tree)
        lines.append("```\n")

        # 添加代码定义
        lines.append("## 代码定义\n")

        current_tokens = sum(len(line) // 4 for line in lines)

        for file_info in files:
            if not file_info.definitions:
                continue

            file_section = [f"### {file_info.relative_path}"]
            for defn in file_info.definitions:
                if defn.kind == "class":
                    file_section.append(f"  - 📦 `{defn.name}` (class, L{defn.line_number})")
                elif defn.kind == "function":
                    file_section.append(f"  - 🔧 `{defn.name}` (function, L{defn.line_number})")
                elif defn.kind == "method":
                    file_section.append(f"  - 🔹 `{defn.name}` (method, L{defn.line_number})")

            section_tokens = sum(len(line) // 4 for line in file_section)

            if current_tokens + section_tokens > max_tokens:
                lines.append("\n... (更多文件省略)")
                break

            lines.extend(file_section)
            current_tokens += section_tokens

        return "\n".join(lines)

    def find_relevant_files(self, query: str, limit: int = 10) -> List[FileInfo]:
        """根据查询找相关文件

        Args:
            query: 搜索查询
            limit: 最大返回数量

        Returns:
            相关文件列表
        """
        if not self._cache:
            self.scan_files()

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_files = []

        for file_info in self._cache.values():
            score = 0

            # 文件名匹配
            filename = Path(file_info.relative_path).name.lower()
            if query_lower in filename:
                score += 10
            for word in query_words:
                if word in filename:
                    score += 5

            # 路径匹配
            path_lower = file_info.relative_path.lower()
            for word in query_words:
                if word in path_lower:
                    score += 2

            # 定义名称匹配
            for defn in file_info.definitions:
                defn_name_lower = defn.name.lower()
                if query_lower in defn_name_lower:
                    score += 8
                for word in query_words:
                    if word in defn_name_lower:
                        score += 3

            # 重要文件加分
            if file_info.is_important:
                score += 3

            if score > 0:
                scored_files.append((score, file_info))

        # 按分数排序
        scored_files.sort(key=lambda x: -x[0])

        return [f for _, f in scored_files[:limit]]
