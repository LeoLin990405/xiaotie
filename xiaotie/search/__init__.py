"""语义搜索模块

提供基于向量的代码语义搜索能力，使用 ChromaDB 作为向量存储。
"""

from .embeddings import EmbeddingProvider, OpenAIEmbeddings
from .semantic_search import SearchResult, SemanticSearch
from .vector_store import CodeVectorStore

__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbeddings",
    "CodeVectorStore",
    "SemanticSearch",
    "SearchResult",
]
