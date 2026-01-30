"""语义搜索模块测试"""

import importlib.util
import os

import pytest

from xiaotie.search.embeddings import DummyEmbeddings, EmbeddingProvider

# 检查 chromadb 是否可用
HAS_CHROMADB = importlib.util.find_spec("chromadb") is not None


class TestDummyEmbeddings:
    """测试 DummyEmbeddings"""

    @pytest.fixture
    def embeddings(self):
        return DummyEmbeddings(dimension=384)

    @pytest.mark.asyncio
    async def test_embed_text(self, embeddings):
        """测试单个文本嵌入"""
        result = await embeddings.embed_text("hello world")
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)
        # 值应该在 [-1, 1] 范围内
        assert all(-1.0 <= x <= 1.0 for x in result)

    @pytest.mark.asyncio
    async def test_embed_text_deterministic(self, embeddings):
        """测试嵌入是确定性的"""
        result1 = await embeddings.embed_text("test")
        result2 = await embeddings.embed_text("test")
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_embed_texts(self, embeddings):
        """测试批量文本嵌入"""
        texts = ["hello", "world", "test"]
        results = await embeddings.embed_texts(texts)
        assert len(results) == 3
        assert all(len(r) == 384 for r in results)

    @pytest.mark.asyncio
    async def test_embed_texts_empty(self, embeddings):
        """测试空列表"""
        results = await embeddings.embed_texts([])
        assert results == []

    def test_dimension(self, embeddings):
        """测试维度属性"""
        assert embeddings.dimension == 384


class TestEmbeddingProviderInterface:
    """测试 EmbeddingProvider 接口"""

    def test_is_abstract(self):
        """测试基类是抽象的"""
        with pytest.raises(TypeError):
            EmbeddingProvider()


@pytest.mark.skipif(not HAS_CHROMADB, reason="chromadb not installed")
class TestCodeVectorStore:
    """测试 CodeVectorStore"""

    @pytest.fixture
    def embeddings(self):
        return DummyEmbeddings(dimension=384)

    @pytest.fixture
    def vector_store(self, embeddings, tmp_path):
        from xiaotie.search.vector_store import CodeVectorStore

        return CodeVectorStore(
            embedding_provider=embeddings,
            persist_directory=str(tmp_path / "vectordb"),
            collection_name="test_collection",
        )

    @pytest.fixture
    def sample_chunks(self):
        from xiaotie.search.vector_store import CodeChunk

        return [
            CodeChunk(
                id="chunk1",
                file_path="/test/file1.py",
                content="def hello(): return 'hello'",
                start_line=1,
                end_line=1,
                chunk_type="function",
            ),
            CodeChunk(
                id="chunk2",
                file_path="/test/file1.py",
                content="def world(): return 'world'",
                start_line=3,
                end_line=3,
                chunk_type="function",
            ),
            CodeChunk(
                id="chunk3",
                file_path="/test/file2.py",
                content="class Calculator: pass",
                start_line=1,
                end_line=1,
                chunk_type="class",
            ),
        ]

    @pytest.mark.asyncio
    async def test_add_chunks(self, vector_store, sample_chunks):
        """测试添加代码块"""
        await vector_store.add_chunks(sample_chunks)
        assert vector_store.count() == 3

    @pytest.mark.asyncio
    async def test_add_empty_chunks(self, vector_store):
        """测试添加空列表"""
        await vector_store.add_chunks([])
        assert vector_store.count() == 0

    @pytest.mark.asyncio
    async def test_search(self, vector_store, sample_chunks):
        """测试搜索"""
        await vector_store.add_chunks(sample_chunks)
        results = await vector_store.search("hello function", n_results=2)
        assert len(results) <= 2
        assert all("id" in r for r in results)
        assert all("content" in r for r in results)
        assert all("similarity" in r for r in results)

    @pytest.mark.asyncio
    async def test_delete_by_file(self, vector_store, sample_chunks):
        """测试按文件删除"""
        await vector_store.add_chunks(sample_chunks)
        assert vector_store.count() == 3

        await vector_store.delete_by_file("/test/file1.py")
        assert vector_store.count() == 1

    @pytest.mark.asyncio
    async def test_update_file(self, vector_store, sample_chunks):
        """测试更新文件"""
        from xiaotie.search.vector_store import CodeChunk

        await vector_store.add_chunks(sample_chunks)
        assert vector_store.count() == 3

        # 更新 file1.py
        new_chunks = [
            CodeChunk(
                id="chunk_new",
                file_path="/test/file1.py",
                content="def new_func(): pass",
                start_line=1,
                end_line=1,
                chunk_type="function",
            ),
        ]
        await vector_store.update_file("/test/file1.py", new_chunks)
        # file1.py 原来有 2 个块，现在只有 1 个
        assert vector_store.count() == 2

    def test_clear(self, vector_store, sample_chunks):
        """测试清空"""
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            vector_store.add_chunks(sample_chunks)
        )
        assert vector_store.count() == 3

        vector_store.clear()
        assert vector_store.count() == 0


@pytest.mark.skipif(not HAS_CHROMADB, reason="chromadb not installed")
class TestSemanticSearch:
    """测试 SemanticSearch"""

    @pytest.fixture
    def embeddings(self):
        return DummyEmbeddings(dimension=384)

    @pytest.fixture
    def search_engine(self, embeddings, tmp_path):
        from xiaotie.search.semantic_search import SemanticSearch

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return SemanticSearch(
            embedding_provider=embeddings,
            workspace_dir=str(workspace),
            persist_directory=str(tmp_path / "vectordb"),
        )

    @pytest.fixture
    def sample_workspace(self, tmp_path):
        """创建示例工作区"""
        workspace = tmp_path / "workspace"
        workspace.mkdir(exist_ok=True)

        # 创建 Python 文件
        py_file = workspace / "main.py"
        py_file.write_text("""
def hello(name):
    return f"Hello, {name}!"

def goodbye(name):
    return f"Goodbye, {name}!"

class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return hello(self.name)
""")

        # 创建另一个文件
        utils_file = workspace / "utils.py"
        utils_file.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")

        return str(workspace)

    @pytest.mark.asyncio
    async def test_index_file(self, search_engine, sample_workspace):
        """测试索引单个文件"""
        file_path = os.path.join(sample_workspace, "main.py")
        count = await search_engine.index_file(file_path)
        assert count > 0

    @pytest.mark.asyncio
    async def test_index_nonexistent_file(self, search_engine):
        """测试索引不存在的文件"""
        count = await search_engine.index_file("/nonexistent/file.py")
        assert count == 0

    @pytest.mark.asyncio
    async def test_index_non_code_file(self, search_engine, tmp_path):
        """测试索引非代码文件"""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("This is a readme file")
        count = await search_engine.index_file(str(txt_file))
        assert count == 0

    @pytest.mark.asyncio
    async def test_index_directory(self, embeddings, sample_workspace, tmp_path):
        """测试索引目录"""
        from xiaotie.search.semantic_search import SemanticSearch

        search_engine = SemanticSearch(
            embedding_provider=embeddings,
            workspace_dir=sample_workspace,
            persist_directory=str(tmp_path / "vectordb"),
        )
        count = await search_engine.index_directory()
        assert count == 2  # main.py 和 utils.py

    @pytest.mark.asyncio
    async def test_search(self, embeddings, sample_workspace, tmp_path):
        """测试搜索"""
        from xiaotie.search.semantic_search import SemanticSearch

        search_engine = SemanticSearch(
            embedding_provider=embeddings,
            workspace_dir=sample_workspace,
            persist_directory=str(tmp_path / "vectordb"),
        )
        await search_engine.index_directory()

        results = await search_engine.search("hello function", n_results=5)
        assert isinstance(results, list)
        for r in results:
            assert hasattr(r, "file_path")
            assert hasattr(r, "content")
            assert hasattr(r, "similarity")

    def test_count(self, search_engine):
        """测试计数"""
        assert search_engine.count() == 0

    def test_clear(self, search_engine):
        """测试清空"""
        search_engine.clear()
        assert search_engine.count() == 0


class TestSearchResult:
    """测试 SearchResult"""

    def test_to_dict(self):
        from xiaotie.search.semantic_search import SearchResult

        result = SearchResult(
            file_path="/test/file.py",
            content="def test(): pass",
            start_line=1,
            end_line=1,
            similarity=0.95,
            chunk_type="function",
        )
        d = result.to_dict()
        assert d["file_path"] == "/test/file.py"
        assert d["content"] == "def test(): pass"
        assert d["start_line"] == 1
        assert d["end_line"] == 1
        assert d["similarity"] == 0.95
        assert d["chunk_type"] == "function"


class TestCodeChunk:
    """测试 CodeChunk"""

    def test_default_metadata(self):
        from xiaotie.search.vector_store import CodeChunk

        chunk = CodeChunk(
            id="test",
            file_path="/test.py",
            content="code",
            start_line=1,
            end_line=1,
        )
        assert chunk.metadata == {}

    def test_custom_metadata(self):
        from xiaotie.search.vector_store import CodeChunk

        chunk = CodeChunk(
            id="test",
            file_path="/test.py",
            content="code",
            start_line=1,
            end_line=1,
            metadata={"key": "value"},
        )
        assert chunk.metadata == {"key": "value"}
