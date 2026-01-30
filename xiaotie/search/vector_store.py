"""向量存储

使用 ChromaDB 存储和检索代码嵌入。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import chromadb
    from chromadb.config import Settings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

from .embeddings import EmbeddingProvider


@dataclass
class CodeChunk:
    """代码块"""

    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str = "code"  # code, function, class, comment
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CodeVectorStore:
    """代码向量存储"""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        persist_directory: Optional[str] = None,
        collection_name: str = "code_chunks",
    ):
        if not HAS_CHROMADB:
            raise ImportError(
                "chromadb is required for vector search. "
                "Install with: pip install chromadb"
            )

        self.embedding_provider = embedding_provider
        self.collection_name = collection_name

        # 设置持久化目录
        if persist_directory:
            self.persist_directory = persist_directory
        else:
            # 默认使用 ~/.xiaotie/vectordb/
            home = os.path.expanduser("~")
            self.persist_directory = os.path.join(home, ".xiaotie", "vectordb")

        # 确保目录存在
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # 使用余弦相似度
        )

    async def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """添加代码块到向量存储"""
        if not chunks:
            return

        # 生成嵌入
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_provider.embed_texts(texts)

        # 准备数据
        ids = [chunk.id for chunk in chunks]
        documents = texts
        metadatas = [
            {
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                **chunk.metadata,
            }
            for chunk in chunks
        ]

        # 添加到集合
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def search(
        self,
        query: str,
        n_results: int = 10,
        file_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """搜索相似代码块"""
        # 生成查询嵌入
        query_embedding = await self.embedding_provider.embed_text(query)

        # 构建过滤条件
        where = {}
        if file_filter:
            where["file_path"] = {"$contains": file_filter}
        if chunk_type_filter:
            where["chunk_type"] = chunk_type_filter

        # 执行查询
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        # 格式化结果
        formatted_results = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                formatted_results.append(
                    {
                        "id": id_,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "similarity": 1 - results["distances"][0][i],  # 余弦距离转相似度
                    }
                )

        return formatted_results

    async def delete_by_file(self, file_path: str) -> None:
        """删除指定文件的所有代码块"""
        # 查找该文件的所有 ID
        results = self.collection.get(
            where={"file_path": file_path},
            include=[],
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])

    async def update_file(self, file_path: str, chunks: list[CodeChunk]) -> None:
        """更新文件的代码块（先删除再添加）"""
        await self.delete_by_file(file_path)
        await self.add_chunks(chunks)

    def count(self) -> int:
        """获取存储的代码块数量"""
        return self.collection.count()

    def clear(self) -> None:
        """清空所有数据"""
        # 删除并重新创建集合
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
