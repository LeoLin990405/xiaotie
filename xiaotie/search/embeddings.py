"""嵌入生成器

提供多种嵌入生成方式：
- OpenAI Embeddings
- 本地模型 (可选)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import openai


class EmbeddingProvider(ABC):
    """嵌入生成器基类"""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """生成单个文本的嵌入"""
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本嵌入"""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """嵌入维度"""
        pass


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI 嵌入生成器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "text-embedding-3-small",
    ):
        self.model = model
        self._dimension = 1536  # text-embedding-3-small 默认维度

        # 配置客户端
        if api_key:
            self.client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=api_base,
            )
        else:
            self.client = openai.AsyncOpenAI()

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        """生成单个文本的嵌入"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本嵌入"""
        if not texts:
            return []

        # OpenAI 支持批量嵌入
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        # 按索引排序返回
        embeddings = [None] * len(texts)
        for item in response.data:
            embeddings[item.index] = item.embedding

        return embeddings


class DummyEmbeddings(EmbeddingProvider):
    """测试用的假嵌入生成器"""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        """生成基于文本哈希的伪嵌入"""
        import hashlib

        # 使用文本哈希生成确定性的伪嵌入
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # 扩展到所需维度
        embedding = []
        for i in range(self._dimension):
            byte_idx = i % len(hash_bytes)
            # 归一化到 [-1, 1]
            value = (hash_bytes[byte_idx] / 127.5) - 1.0
            embedding.append(value)
        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成伪嵌入"""
        return [await self.embed_text(text) for text in texts]
