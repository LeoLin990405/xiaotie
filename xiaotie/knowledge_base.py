"""
知识库集成模块

支持多种知识源的统一接口：
- 本地文件 (Markdown, TXT, PDF)
- Notion
- Confluence
- 向量数据库
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import hashlib
import json
import re


class SourceType(Enum):
    """知识源类型"""
    LOCAL = "local"
    NOTION = "notion"
    CONFLUENCE = "confluence"
    VECTOR_DB = "vector_db"
    WEB = "web"


@dataclass
class Document:
    """文档"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    source_type: SourceType = SourceType.LOCAL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(self.content.encode()).hexdigest()[:12]


@dataclass
class SearchResult:
    """搜索结果"""
    document: Document
    score: float
    highlights: List[str] = field(default_factory=list)


@dataclass
class SourceConfig:
    """知识源配置"""
    type: SourceType
    path: Optional[str] = None  # 本地路径
    url: Optional[str] = None   # 远程 URL
    token: Optional[str] = None # API Token
    options: Dict[str, Any] = field(default_factory=dict)


class KnowledgeSource(ABC):
    """知识源抽象基类"""

    def __init__(self, config: SourceConfig):
        self.config = config
        self._documents: Dict[str, Document] = {}

    @abstractmethod
    async def load(self) -> List[Document]:
        """加载文档"""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """搜索文档"""
        pass

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self._documents.get(doc_id)

    def list_documents(self) -> List[Document]:
        """列出所有文档"""
        return list(self._documents.values())


class LocalSource(KnowledgeSource):
    """本地文件知识源"""

    SUPPORTED_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml'}

    async def load(self) -> List[Document]:
        """加载本地文件"""
        if not self.config.path:
            return []

        path = Path(self.config.path)
        if not path.exists():
            return []

        documents = []

        if path.is_file():
            doc = await self._load_file(path)
            if doc:
                documents.append(doc)
        elif path.is_dir():
            for file_path in path.rglob('*'):
                if file_path.is_file() and file_path.suffix in self.SUPPORTED_EXTENSIONS:
                    doc = await self._load_file(file_path)
                    if doc:
                        documents.append(doc)

        for doc in documents:
            self._documents[doc.id] = doc

        return documents

    async def _load_file(self, file_path: Path) -> Optional[Document]:
        """加载单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8')
            return Document(
                id=hashlib.md5(str(file_path).encode()).hexdigest()[:12],
                content=content,
                metadata={
                    'filename': file_path.name,
                    'extension': file_path.suffix,
                    'size': file_path.stat().st_size,
                },
                source=str(file_path),
                source_type=SourceType.LOCAL,
            )
        except Exception:
            return None

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """简单文本搜索"""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for doc in self._documents.values():
            content_lower = doc.content.lower()

            # 计算匹配分数
            score = 0.0
            highlights = []

            # 完整匹配
            if query_lower in content_lower:
                score += 1.0
                # 提取高亮片段
                idx = content_lower.find(query_lower)
                start = max(0, idx - 50)
                end = min(len(doc.content), idx + len(query) + 50)
                highlights.append(doc.content[start:end])

            # 词匹配
            for word in query_words:
                if word in content_lower:
                    score += 0.2

            if score > 0:
                results.append(SearchResult(
                    document=doc,
                    score=score,
                    highlights=highlights[:3],
                ))

        # 按分数排序
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]


class NotionSource(KnowledgeSource):
    """Notion 知识源"""

    async def load(self) -> List[Document]:
        """加载 Notion 页面"""
        if not self.config.token:
            return []

        # 模拟 Notion API 调用
        # 实际实现需要使用 notion-client
        documents = []

        # 这里是模拟实现
        # 实际需要调用 Notion API

        for doc in documents:
            self._documents[doc.id] = doc

        return documents

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """搜索 Notion"""
        # 使用 Notion Search API
        results = []
        query_lower = query.lower()

        for doc in self._documents.values():
            if query_lower in doc.content.lower():
                results.append(SearchResult(
                    document=doc,
                    score=1.0,
                    highlights=[],
                ))

        return results[:limit]


class ConfluenceSource(KnowledgeSource):
    """Confluence 知识源"""

    async def load(self) -> List[Document]:
        """加载 Confluence 页面"""
        if not self.config.url or not self.config.token:
            return []

        # 模拟 Confluence API 调用
        documents = []

        for doc in documents:
            self._documents[doc.id] = doc

        return documents

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """搜索 Confluence"""
        results = []
        query_lower = query.lower()

        for doc in self._documents.values():
            if query_lower in doc.content.lower():
                results.append(SearchResult(
                    document=doc,
                    score=1.0,
                    highlights=[],
                ))

        return results[:limit]


class VectorDBSource(KnowledgeSource):
    """向量数据库知识源"""

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self._embeddings: Dict[str, List[float]] = {}
        self._embed_fn: Optional[Callable[[str], List[float]]] = None

    def set_embedding_function(self, fn: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self._embed_fn = fn

    async def load(self) -> List[Document]:
        """加载并生成嵌入"""
        return list(self._documents.values())

    async def add_document(self, doc: Document, embedding: Optional[List[float]] = None):
        """添加文档"""
        self._documents[doc.id] = doc

        if embedding:
            self._embeddings[doc.id] = embedding
        elif self._embed_fn:
            self._embeddings[doc.id] = self._embed_fn(doc.content)

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """向量相似度搜索"""
        if not self._embed_fn or not self._embeddings:
            # 降级到文本搜索
            return await self._text_search(query, limit)

        query_embedding = self._embed_fn(query)

        results = []
        for doc_id, doc_embedding in self._embeddings.items():
            score = self._cosine_similarity(query_embedding, doc_embedding)
            doc = self._documents.get(doc_id)
            if doc:
                results.append(SearchResult(
                    document=doc,
                    score=score,
                    highlights=[],
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def _text_search(self, query: str, limit: int) -> List[SearchResult]:
        """文本搜索降级"""
        results = []
        query_lower = query.lower()

        for doc in self._documents.values():
            if query_lower in doc.content.lower():
                results.append(SearchResult(
                    document=doc,
                    score=1.0,
                    highlights=[],
                ))

        return results[:limit]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class KnowledgeBase:
    """统一知识库"""

    def __init__(
        self,
        sources: Optional[List[Union[SourceConfig, Dict[str, Any]]]] = None,
    ):
        self._sources: Dict[str, KnowledgeSource] = {}
        self._loaded = False

        if sources:
            for source in sources:
                self.add_source(source)

    def add_source(
        self,
        source: Union[SourceConfig, Dict[str, Any], KnowledgeSource],
        name: Optional[str] = None,
    ):
        """添加知识源"""
        if isinstance(source, KnowledgeSource):
            source_obj = source
            source_name = name or f"source_{len(self._sources)}"
        elif isinstance(source, dict):
            config = SourceConfig(
                type=SourceType(source.get('type', 'local')),
                path=source.get('path'),
                url=source.get('url'),
                token=source.get('token'),
                options=source.get('options', {}),
            )
            source_obj = self._create_source(config)
            source_name = name or source.get('name', f"source_{len(self._sources)}")
        else:
            source_obj = self._create_source(source)
            source_name = name or f"source_{len(self._sources)}"

        self._sources[source_name] = source_obj

    def _create_source(self, config: SourceConfig) -> KnowledgeSource:
        """创建知识源"""
        source_map = {
            SourceType.LOCAL: LocalSource,
            SourceType.NOTION: NotionSource,
            SourceType.CONFLUENCE: ConfluenceSource,
            SourceType.VECTOR_DB: VectorDBSource,
        }

        source_class = source_map.get(config.type, LocalSource)
        return source_class(config)

    async def load(self):
        """加载所有知识源"""
        for source in self._sources.values():
            await source.load()
        self._loaded = True

    async def search(
        self,
        query: str,
        limit: int = 10,
        sources: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """搜索所有知识源"""
        if not self._loaded:
            await self.load()

        all_results = []

        target_sources = sources or list(self._sources.keys())

        for source_name in target_sources:
            source = self._sources.get(source_name)
            if source:
                results = await source.search(query, limit)
                all_results.extend(results)

        # 按分数排序并去重
        all_results.sort(key=lambda r: r.score, reverse=True)

        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result.document.id not in seen_ids:
                seen_ids.add(result.document.id)
                unique_results.append(result)

        return unique_results[:limit]

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        for source in self._sources.values():
            doc = source.get_document(doc_id)
            if doc:
                return doc
        return None

    def list_documents(self, source_name: Optional[str] = None) -> List[Document]:
        """列出文档"""
        if source_name:
            source = self._sources.get(source_name)
            return source.list_documents() if source else []

        all_docs = []
        for source in self._sources.values():
            all_docs.extend(source.list_documents())
        return all_docs

    def list_sources(self) -> List[str]:
        """列出知识源"""
        return list(self._sources.keys())

    @property
    def document_count(self) -> int:
        """文档总数"""
        return sum(len(s.list_documents()) for s in self._sources.values())


class DocumentChunker:
    """文档分块器"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n\n",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def chunk(self, document: Document) -> List[Document]:
        """分块文档"""
        content = document.content
        chunks = []

        # 按分隔符分割
        paragraphs = content.split(self.separator)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) + len(self.separator) <= self.chunk_size:
                if current_chunk:
                    current_chunk += self.separator
                current_chunk += para
            else:
                if current_chunk:
                    chunks.append(self._create_chunk(
                        document, current_chunk, chunk_index
                    ))
                    chunk_index += 1

                # 处理超长段落
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_text(para)
                    for sub_chunk in sub_chunks:
                        chunks.append(self._create_chunk(
                            document, sub_chunk, chunk_index
                        ))
                        chunk_index += 1
                    current_chunk = ""
                else:
                    # 保留重叠部分
                    overlap_text = current_chunk[-self.chunk_overlap:] if current_chunk else ""
                    current_chunk = overlap_text + self.separator + para if overlap_text else para

        if current_chunk:
            chunks.append(self._create_chunk(document, current_chunk, chunk_index))

        return chunks

    def _create_chunk(
        self,
        original: Document,
        content: str,
        index: int,
    ) -> Document:
        """创建分块文档"""
        return Document(
            id=f"{original.id}_chunk_{index}",
            content=content,
            metadata={
                **original.metadata,
                'chunk_index': index,
                'parent_id': original.id,
            },
            source=original.source,
            source_type=original.source_type,
        )

    def _split_long_text(self, text: str) -> List[str]:
        """分割超长文本"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # 尝试在句子边界分割
            if end < len(text):
                # 查找最近的句子结束
                for sep in ['. ', '。', '! ', '? ', '\n']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunks.append(text[start:end])
            start = end - self.chunk_overlap

        return chunks


class MarkdownParser:
    """Markdown 解析器"""

    @staticmethod
    def extract_sections(content: str) -> List[Dict[str, Any]]:
        """提取 Markdown 章节"""
        sections = []
        current_section = None
        current_content = []

        for line in content.split('\n'):
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if header_match:
                # 保存前一个章节
                if current_section:
                    current_section['content'] = '\n'.join(current_content)
                    sections.append(current_section)

                level = len(header_match.group(1))
                title = header_match.group(2)

                current_section = {
                    'level': level,
                    'title': title,
                    'content': '',
                }
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个章节
        if current_section:
            current_section['content'] = '\n'.join(current_content)
            sections.append(current_section)

        return sections

    @staticmethod
    def extract_code_blocks(content: str) -> List[Dict[str, str]]:
        """提取代码块"""
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)

        return [
            {'language': lang or 'text', 'code': code.strip()}
            for lang, code in matches
        ]

    @staticmethod
    def extract_links(content: str) -> List[Dict[str, str]]:
        """提取链接"""
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        matches = re.findall(pattern, content)

        return [
            {'text': text, 'url': url}
            for text, url in matches
        ]
