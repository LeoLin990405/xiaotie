"""语义搜索

提供代码库的语义搜索能力。
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from .embeddings import EmbeddingProvider
from .vector_store import CodeChunk, CodeVectorStore


@dataclass
class SearchResult:
    """搜索结果"""

    file_path: str
    content: str
    start_line: int
    end_line: int
    similarity: float
    chunk_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "similarity": self.similarity,
            "chunk_type": self.chunk_type,
        }


class SemanticSearch:
    """语义搜索引擎"""

    # 支持的代码文件扩展名
    CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".cs",
        ".vue",
        ".svelte",
    }

    # 忽略的目录
    IGNORE_DIRS = {
        ".git",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        ".idea",
        ".vscode",
    }

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        workspace_dir: str = ".",
        persist_directory: Optional[str] = None,
        chunk_size: int = 500,  # 每个代码块的最大行数
        chunk_overlap: int = 50,  # 代码块重叠行数
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化向量存储
        self.vector_store = CodeVectorStore(
            embedding_provider=embedding_provider,
            persist_directory=persist_directory,
        )

    async def index_file(self, file_path: str) -> int:
        """索引单个文件，返回索引的代码块数量"""
        abs_path = os.path.abspath(file_path)

        # 检查文件是否存在
        if not os.path.isfile(abs_path):
            return 0

        # 检查是否是代码文件
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in self.CODE_EXTENSIONS:
            return 0

        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return 0

        # 分割成代码块
        chunks = self._split_into_chunks(abs_path, content)

        if chunks:
            await self.vector_store.update_file(abs_path, chunks)

        return len(chunks)

    async def index_directory(
        self,
        directory: Optional[str] = None,
        extensions: Optional[set[str]] = None,
    ) -> int:
        """索引目录，返回索引的文件数量"""
        target_dir = directory or self.workspace_dir
        extensions = extensions or self.CODE_EXTENSIONS

        indexed_files = 0

        for root, dirs, files in os.walk(target_dir):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    chunks_count = await self.index_file(file_path)
                    if chunks_count > 0:
                        indexed_files += 1

        return indexed_files

    async def search(
        self,
        query: str,
        n_results: int = 10,
        file_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """语义搜索"""
        results = await self.vector_store.search(
            query=query,
            n_results=n_results,
            file_filter=file_filter,
        )

        return [
            SearchResult(
                file_path=r["metadata"]["file_path"],
                content=r["content"],
                start_line=r["metadata"]["start_line"],
                end_line=r["metadata"]["end_line"],
                similarity=r["similarity"],
                chunk_type=r["metadata"]["chunk_type"],
            )
            for r in results
        ]

    def _split_into_chunks(self, file_path: str, content: str) -> list[CodeChunk]:
        """将文件内容分割成代码块"""
        lines = content.split("\n")
        chunks = []

        # 首先尝试按函数/类分割
        semantic_chunks = self._extract_semantic_chunks(file_path, content, lines)
        if semantic_chunks:
            chunks.extend(semantic_chunks)

        # 如果没有语义块，或者有剩余内容，按固定大小分割
        if not chunks:
            chunks = self._split_by_size(file_path, lines)

        return chunks

    def _extract_semantic_chunks(
        self, file_path: str, content: str, lines: list[str]
    ) -> list[CodeChunk]:
        """提取语义代码块（函数、类等）"""
        chunks = []
        ext = os.path.splitext(file_path)[1].lower()

        # Python 函数和类
        if ext == ".py":
            # 匹配函数定义
            func_pattern = r"^(async\s+)?def\s+(\w+)\s*\("
            class_pattern = r"^class\s+(\w+)"

            current_block = None
            current_start = 0

            for i, line in enumerate(lines):
                stripped = line.lstrip()

                # 检查函数定义
                func_match = re.match(func_pattern, stripped)
                class_match = re.match(class_pattern, stripped)

                if func_match or class_match:
                    # 保存之前的块
                    if current_block and i - current_start > 2:
                        chunk_content = "\n".join(lines[current_start:i])
                        if chunk_content.strip():
                            chunks.append(
                                CodeChunk(
                                    id=self._generate_chunk_id(file_path, current_start),
                                    file_path=file_path,
                                    content=chunk_content,
                                    start_line=current_start + 1,
                                    end_line=i,
                                    chunk_type=current_block,
                                )
                            )

                    # 开始新块
                    current_start = i
                    current_block = "function" if func_match else "class"

        return chunks

    def _split_by_size(self, file_path: str, lines: list[str]) -> list[CodeChunk]:
        """按固定大小分割代码"""
        chunks = []
        total_lines = len(lines)

        if total_lines == 0:
            return chunks

        start = 0
        while start < total_lines:
            end = min(start + self.chunk_size, total_lines)
            chunk_content = "\n".join(lines[start:end])

            if chunk_content.strip():
                chunks.append(
                    CodeChunk(
                        id=self._generate_chunk_id(file_path, start),
                        file_path=file_path,
                        content=chunk_content,
                        start_line=start + 1,
                        end_line=end,
                        chunk_type="code",
                    )
                )

            # 下一个块，考虑重叠
            start = end - self.chunk_overlap if end < total_lines else total_lines

        return chunks

    def _generate_chunk_id(self, file_path: str, start_line: int) -> str:
        """生成代码块 ID"""
        content = f"{file_path}:{start_line}"
        return hashlib.md5(content.encode()).hexdigest()

    def count(self) -> int:
        """获取索引的代码块数量"""
        return self.vector_store.count()

    def clear(self) -> None:
        """清空索引"""
        self.vector_store.clear()
