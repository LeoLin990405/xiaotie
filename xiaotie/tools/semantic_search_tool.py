"""语义搜索工具

提供基于向量的代码语义搜索能力。
"""

from __future__ import annotations

# 检查 chromadb 是否可用
import importlib.util
import os
from typing import Any, Optional

from ..schema import ToolResult
from .base import Tool

HAS_CHROMADB = importlib.util.find_spec("chromadb") is not None


class SemanticSearchTool(Tool):
    """语义搜索工具

    使用向量嵌入进行代码语义搜索。
    """

    def __init__(
        self,
        workspace_dir: str = ".",
        persist_directory: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.persist_directory = persist_directory
        self.api_key = api_key
        self.api_base = api_base
        self._search_engine = None
        self._indexed = False

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return """语义搜索代码库。使用向量嵌入查找与查询语义相关的代码片段。

适用场景：
- 查找实现特定功能的代码
- 搜索相似的代码模式
- 理解代码库结构

注意：首次使用需要索引代码库，可能需要一些时间。"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询，描述你要查找的代码功能或模式",
                },
                "n_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                    "default": 5,
                },
                "file_filter": {
                    "type": "string",
                    "description": "文件路径过滤（可选），只搜索包含此字符串的文件",
                },
                "reindex": {
                    "type": "boolean",
                    "description": "是否重新索引代码库，默认 False",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        n_results: int = 5,
        file_filter: Optional[str] = None,
        reindex: bool = False,
    ) -> ToolResult:
        """执行语义搜索"""
        if not HAS_CHROMADB:
            return ToolResult(
                success=False,
                content="语义搜索需要 chromadb。请安装: pip install xiaotie[search]",
            )

        try:
            # 延迟初始化搜索引擎
            if self._search_engine is None:
                await self._init_search_engine()

            # 如果需要重新索引或尚未索引
            if reindex or not self._indexed:
                indexed_count = await self._search_engine.index_directory()
                self._indexed = True
                if indexed_count == 0:
                    return ToolResult(
                        success=True,
                        content="代码库中没有找到可索引的代码文件。",
                    )

            # 执行搜索
            results = await self._search_engine.search(
                query=query,
                n_results=n_results,
                file_filter=file_filter,
            )

            if not results:
                return ToolResult(
                    success=True,
                    content=f"没有找到与 '{query}' 相关的代码。",
                )

            # 格式化结果
            output_lines = [f"找到 {len(results)} 个相关代码片段:\n"]

            for i, result in enumerate(results, 1):
                rel_path = os.path.relpath(result.file_path, self.workspace_dir)
                output_lines.append(f"## {i}. {rel_path}")
                output_lines.append(f"行 {result.start_line}-{result.end_line}")
                output_lines.append(f"相似度: {result.similarity:.2%}")
                output_lines.append(f"类型: {result.chunk_type}")
                output_lines.append("```")
                # 限制内容长度
                content = result.content
                if len(content) > 500:
                    content = content[:500] + "\n... (截断)"
                output_lines.append(content)
                output_lines.append("```\n")

            return ToolResult(
                success=True,
                content="\n".join(output_lines),
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content=f"语义搜索失败: {str(e)}",
            )

    async def _init_search_engine(self) -> None:
        """初始化搜索引擎"""
        from ..search import SemanticSearch
        from ..search.embeddings import DummyEmbeddings, OpenAIEmbeddings

        # 选择嵌入提供者
        if self.api_key:
            embedding_provider = OpenAIEmbeddings(
                api_key=self.api_key,
                api_base=self.api_base,
            )
        else:
            # 如果没有 API key，使用 DummyEmbeddings（基于哈希）
            embedding_provider = DummyEmbeddings()

        self._search_engine = SemanticSearch(
            embedding_provider=embedding_provider,
            workspace_dir=self.workspace_dir,
            persist_directory=self.persist_directory,
        )

    def get_index_count(self) -> int:
        """获取已索引的代码块数量"""
        if self._search_engine is None:
            return 0
        return self._search_engine.count()

    def clear_index(self) -> None:
        """清空索引"""
        if self._search_engine is not None:
            self._search_engine.clear()
            self._indexed = False
