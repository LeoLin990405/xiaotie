"""代码分析工具

提供代码结构分析、依赖分析等功能
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Tool, ToolResult


@dataclass
class CodeDefinition:
    """代码定义"""

    name: str
    type: str  # class, function, method, variable
    line: int
    docstring: Optional[str] = None
    signature: Optional[str] = None
    decorators: List[str] = None

    def __post_init__(self):
        if self.decorators is None:
            self.decorators = []


@dataclass
class CodeAnalysis:
    """代码分析结果"""

    file_path: str
    language: str
    lines: int
    classes: List[CodeDefinition]
    functions: List[CodeDefinition]
    imports: List[str]
    dependencies: List[str]
    complexity: int  # 简单复杂度估算


class CodeAnalysisTool(Tool):
    """代码分析工具"""

    def __init__(self, workspace_dir: str = "."):
        super().__init__()
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "analyze_code"

    @property
    def description(self) -> str:
        return "分析代码文件，提取类、函数定义、依赖关系等信息。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要分析的文件路径",
                },
                "include_docstrings": {
                    "type": "boolean",
                    "description": "是否包含文档字符串（默认 True）",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        include_docstrings: bool = True,
    ) -> ToolResult:
        """执行代码分析"""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = self.workspace_dir / file_path

            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"不是文件: {path}")

            # 读取文件内容
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            # 根据文件类型分析
            suffix = file_path.suffix.lower()
            if suffix == ".py":
                analysis = self._analyze_python(file_path, content, include_docstrings)
            elif suffix in (".js", ".ts", ".jsx", ".tsx"):
                analysis = self._analyze_javascript(file_path, content)
            else:
                analysis = self._analyze_generic(file_path, content)

            # 格式化输出
            output = self._format_analysis(analysis)
            return ToolResult(success=True, content=output)

        except Exception as e:
            return ToolResult(success=False, error=f"分析失败: {e}")

    def _analyze_python(
        self,
        file_path: Path,
        content: str,
        include_docstrings: bool,
    ) -> CodeAnalysis:
        """分析 Python 代码"""
        classes = []
        functions = []
        imports = []
        dependencies = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # 类定义
                if isinstance(node, ast.ClassDef):
                    decorators = [
                        ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                        for d in node.decorator_list
                    ]
                    docstring = ast.get_docstring(node) if include_docstrings else None
                    classes.append(
                        CodeDefinition(
                            name=node.name,
                            type="class",
                            line=node.lineno,
                            docstring=docstring[:100] if docstring else None,
                            decorators=decorators,
                        )
                    )

                # 函数定义
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    # 跳过类方法（已在类中处理）
                    decorators = [
                        ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                        for d in node.decorator_list
                    ]
                    docstring = ast.get_docstring(node) if include_docstrings else None

                    # 获取函数签名
                    args = []
                    for arg in node.args.args:
                        args.append(arg.arg)
                    signature = f"({', '.join(args)})"

                    func_type = (
                        "async function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                    )
                    functions.append(
                        CodeDefinition(
                            name=node.name,
                            type=func_type,
                            line=node.lineno,
                            docstring=docstring[:100] if docstring else None,
                            signature=signature,
                            decorators=decorators,
                        )
                    )

                # 导入
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                        # 提取顶级包名作为依赖
                        dep = alias.name.split(".")[0]
                        if dep not in dependencies:
                            dependencies.append(dep)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(f"from {node.module}")
                        dep = node.module.split(".")[0]
                        if dep not in dependencies:
                            dependencies.append(dep)

        except SyntaxError:
            pass

        # 计算复杂度（简单估算：类数 + 函数数 + 条件语句数）
        complexity = len(classes) + len(functions)
        complexity += content.count("if ") + content.count("for ") + content.count("while ")
        complexity += content.count("try:") + content.count("except ")

        return CodeAnalysis(
            file_path=str(file_path),
            language="python",
            lines=len(content.splitlines()),
            classes=classes,
            functions=functions,
            imports=imports,
            dependencies=dependencies,
            complexity=complexity,
        )

    def _analyze_javascript(self, file_path: Path, content: str) -> CodeAnalysis:
        """分析 JavaScript/TypeScript 代码"""
        classes = []
        functions = []
        imports = []
        dependencies = []

        # 简单的正则匹配
        # 类定义
        class_pattern = r"class\s+(\w+)"
        for match in re.finditer(class_pattern, content):
            line = content[: match.start()].count("\n") + 1
            classes.append(
                CodeDefinition(
                    name=match.group(1),
                    type="class",
                    line=line,
                )
            )

        # 函数定义
        func_patterns = [
            r"function\s+(\w+)\s*\(",
            r"const\s+(\w+)\s*=\s*(?:async\s*)?\(",
            r"(\w+)\s*:\s*(?:async\s*)?\(",
        ]
        for pattern in func_patterns:
            for match in re.finditer(pattern, content):
                line = content[: match.start()].count("\n") + 1
                functions.append(
                    CodeDefinition(
                        name=match.group(1),
                        type="function",
                        line=line,
                    )
                )

        # 导入
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            module = match.group(1)
            imports.append(module)
            if not module.startswith("."):
                dep = module.split("/")[0]
                if dep not in dependencies:
                    dependencies.append(dep)

        # require 导入
        require_pattern = r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
        for match in re.finditer(require_pattern, content):
            module = match.group(1)
            imports.append(module)
            if not module.startswith("."):
                dep = module.split("/")[0]
                if dep not in dependencies:
                    dependencies.append(dep)

        complexity = len(classes) + len(functions)
        complexity += content.count("if ") + content.count("for ") + content.count("while ")

        suffix = file_path.suffix.lower()
        language = "typescript" if suffix in (".ts", ".tsx") else "javascript"

        return CodeAnalysis(
            file_path=str(file_path),
            language=language,
            lines=len(content.splitlines()),
            classes=classes,
            functions=functions,
            imports=imports,
            dependencies=dependencies,
            complexity=complexity,
        )

    def _analyze_generic(self, file_path: Path, content: str) -> CodeAnalysis:
        """通用代码分析"""
        return CodeAnalysis(
            file_path=str(file_path),
            language=file_path.suffix.lstrip(".") or "unknown",
            lines=len(content.splitlines()),
            classes=[],
            functions=[],
            imports=[],
            dependencies=[],
            complexity=0,
        )

    def _format_analysis(self, analysis: CodeAnalysis) -> str:
        """格式化分析结果"""
        lines = [
            f"📊 代码分析: {analysis.file_path}",
            "",
            "📝 基本信息:",
            f"  • 语言: {analysis.language}",
            f"  • 行数: {analysis.lines}",
            f"  • 复杂度: {analysis.complexity}",
            "",
        ]

        if analysis.classes:
            lines.append(f"📦 类定义 ({len(analysis.classes)}):")
            for cls in analysis.classes:
                decorators = f" [{', '.join(cls.decorators)}]" if cls.decorators else ""
                lines.append(f"  • {cls.name} (行 {cls.line}){decorators}")
                if cls.docstring:
                    lines.append(f"    └─ {cls.docstring}")
            lines.append("")

        if analysis.functions:
            lines.append(f"🔧 函数定义 ({len(analysis.functions)}):")
            for func in analysis.functions:
                sig = func.signature or ""
                decorators = f" [{', '.join(func.decorators)}]" if func.decorators else ""
                lines.append(f"  • {func.name}{sig} (行 {func.line}){decorators}")
                if func.docstring:
                    lines.append(f"    └─ {func.docstring}")
            lines.append("")

        if analysis.imports:
            lines.append(f"📥 导入 ({len(analysis.imports)}):")
            for imp in analysis.imports[:10]:
                lines.append(f"  • {imp}")
            if len(analysis.imports) > 10:
                lines.append(f"  ... 还有 {len(analysis.imports) - 10} 个")
            lines.append("")

        if analysis.dependencies:
            lines.append(f"📦 依赖 ({len(analysis.dependencies)}):")
            lines.append(f"  {', '.join(analysis.dependencies[:15])}")
            if len(analysis.dependencies) > 15:
                lines.append(f"  ... 还有 {len(analysis.dependencies) - 15} 个")

        return "\n".join(lines)
