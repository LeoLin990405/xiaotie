"""
知识库模块测试
"""

import sys
import asyncio
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_tests():
    """运行所有测试"""
    passed = 0
    failed = 0

    def test(name, condition):
        nonlocal passed, failed
        if condition:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            failed += 1

    async def async_test(name, coro):
        nonlocal passed, failed
        try:
            result = await coro
            if result:
                print(f"  ✓ {name}")
                passed += 1
            else:
                print(f"  ✗ {name}")
                failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    # 导入模块
    from xiaotie.knowledge_base import (
        Document, SearchResult, SourceConfig, SourceType,
        LocalSource, NotionSource, ConfluenceSource, VectorDBSource,
        KnowledgeBase, DocumentChunker, MarkdownParser,
    )

    print("\n=== Document 测试 ===")

    # 测试 Document 创建
    doc = Document(id="test1", content="Hello World")
    test("document_create", doc.id == "test1" and doc.content == "Hello World")

    # 测试自动生成 ID
    doc2 = Document(id="", content="Auto ID")
    test("document_auto_id", len(doc2.id) == 12)

    # 测试 metadata
    doc3 = Document(id="test3", content="With metadata", metadata={"key": "value"})
    test("document_metadata", doc3.metadata.get("key") == "value")

    print("\n=== SearchResult 测试 ===")

    result = SearchResult(document=doc, score=0.95, highlights=["Hello"])
    test("search_result_create", result.score == 0.95)
    test("search_result_highlights", len(result.highlights) == 1)

    print("\n=== SourceConfig 测试 ===")

    config = SourceConfig(type=SourceType.LOCAL, path="/tmp/docs")
    test("source_config_local", config.type == SourceType.LOCAL)

    config2 = SourceConfig(type=SourceType.NOTION, token="secret")
    test("source_config_notion", config2.token == "secret")

    print("\n=== LocalSource 测试 ===")

    async def test_local_source():
        # 创建临时目录和文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test\n\nThis is a test document.")

            test_file2 = Path(tmpdir) / "test2.txt"
            test_file2.write_text("Another document with different content.")

            # 创建子目录
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            sub_file = subdir / "nested.md"
            sub_file.write_text("Nested document content.")

            config = SourceConfig(type=SourceType.LOCAL, path=tmpdir)
            source = LocalSource(config)

            # 测试加载
            docs = await source.load()
            return len(docs) == 3

    asyncio.run(async_test("local_source_load", test_local_source()))

    async def test_local_source_search():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Python is a programming language.")

            test_file2 = Path(tmpdir) / "test2.md"
            test_file2.write_text("JavaScript is also a programming language.")

            config = SourceConfig(type=SourceType.LOCAL, path=tmpdir)
            source = LocalSource(config)
            await source.load()

            results = await source.search("Python")
            return len(results) == 1 and results[0].score > 0

    asyncio.run(async_test("local_source_search", test_local_source_search()))

    async def test_local_source_search_multiple():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Python programming language.")

            test_file2 = Path(tmpdir) / "test2.md"
            test_file2.write_text("Python is great for programming.")

            config = SourceConfig(type=SourceType.LOCAL, path=tmpdir)
            source = LocalSource(config)
            await source.load()

            results = await source.search("programming")
            return len(results) == 2

    asyncio.run(async_test("local_source_search_multiple", test_local_source_search_multiple()))

    async def test_local_source_single_file():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "single.md"
            test_file.write_text("Single file content.")

            config = SourceConfig(type=SourceType.LOCAL, path=str(test_file))
            source = LocalSource(config)

            docs = await source.load()
            return len(docs) == 1

    asyncio.run(async_test("local_source_single_file", test_local_source_single_file()))

    async def test_local_source_nonexistent():
        config = SourceConfig(type=SourceType.LOCAL, path="/nonexistent/path")
        source = LocalSource(config)

        docs = await source.load()
        return len(docs) == 0

    asyncio.run(async_test("local_source_nonexistent", test_local_source_nonexistent()))

    print("\n=== VectorDBSource 测试 ===")

    async def test_vector_db_add():
        config = SourceConfig(type=SourceType.VECTOR_DB)
        source = VectorDBSource(config)

        doc = Document(id="vec1", content="Vector document")
        await source.add_document(doc, embedding=[0.1, 0.2, 0.3])

        return source.get_document("vec1") is not None

    asyncio.run(async_test("vector_db_add", test_vector_db_add()))

    async def test_vector_db_search_with_embedding():
        config = SourceConfig(type=SourceType.VECTOR_DB)
        source = VectorDBSource(config)

        # 简单的嵌入函数
        def simple_embed(text):
            return [len(text) / 100, 0.5, 0.5]

        source.set_embedding_function(simple_embed)

        doc1 = Document(id="v1", content="Short")
        doc2 = Document(id="v2", content="This is a longer document")

        await source.add_document(doc1)
        await source.add_document(doc2)

        results = await source.search("Medium length query")
        return len(results) == 2

    asyncio.run(async_test("vector_db_search_with_embedding", test_vector_db_search_with_embedding()))

    async def test_vector_db_text_fallback():
        config = SourceConfig(type=SourceType.VECTOR_DB)
        source = VectorDBSource(config)

        doc = Document(id="v1", content="Fallback search test")
        await source.add_document(doc)

        results = await source.search("Fallback")
        return len(results) == 1

    asyncio.run(async_test("vector_db_text_fallback", test_vector_db_text_fallback()))

    # 测试余弦相似度
    similarity = VectorDBSource._cosine_similarity([1, 0, 0], [1, 0, 0])
    test("cosine_similarity_identical", abs(similarity - 1.0) < 0.001)

    similarity2 = VectorDBSource._cosine_similarity([1, 0, 0], [0, 1, 0])
    test("cosine_similarity_orthogonal", abs(similarity2) < 0.001)

    similarity3 = VectorDBSource._cosine_similarity([1, 2, 3], [1, 2, 3])
    test("cosine_similarity_same", abs(similarity3 - 1.0) < 0.001)

    similarity4 = VectorDBSource._cosine_similarity([1, 0], [1, 0, 0])
    test("cosine_similarity_different_length", similarity4 == 0.0)

    print("\n=== KnowledgeBase 测试 ===")

    async def test_kb_create():
        kb = KnowledgeBase()
        return kb.document_count == 0

    asyncio.run(async_test("kb_create", test_kb_create()))

    async def test_kb_add_source_dict():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Test content")

            kb = KnowledgeBase(sources=[
                {"type": "local", "path": tmpdir}
            ])

            await kb.load()
            return kb.document_count == 1

    asyncio.run(async_test("kb_add_source_dict", test_kb_add_source_dict()))

    async def test_kb_add_source_config():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Test content")

            config = SourceConfig(type=SourceType.LOCAL, path=tmpdir)
            kb = KnowledgeBase()
            kb.add_source(config, name="local_docs")

            await kb.load()
            return "local_docs" in kb.list_sources()

    asyncio.run(async_test("kb_add_source_config", test_kb_add_source_config()))

    async def test_kb_search():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Python programming guide")

            kb = KnowledgeBase(sources=[
                {"type": "local", "path": tmpdir}
            ])

            results = await kb.search("Python")
            return len(results) == 1

    asyncio.run(async_test("kb_search", test_kb_search()))

    async def test_kb_search_multiple_sources():
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                Path(tmpdir1, "doc1.md").write_text("Python basics")
                Path(tmpdir2, "doc2.md").write_text("Python advanced")

                kb = KnowledgeBase(sources=[
                    {"type": "local", "path": tmpdir1, "name": "basics"},
                    {"type": "local", "path": tmpdir2, "name": "advanced"},
                ])

                results = await kb.search("Python")
                return len(results) == 2

    asyncio.run(async_test("kb_search_multiple_sources", test_kb_search_multiple_sources()))

    async def test_kb_search_specific_source():
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                Path(tmpdir1, "doc1.md").write_text("Python basics")
                Path(tmpdir2, "doc2.md").write_text("Python advanced")

                kb = KnowledgeBase()
                kb.add_source({"type": "local", "path": tmpdir1}, name="basics")
                kb.add_source({"type": "local", "path": tmpdir2}, name="advanced")

                results = await kb.search("Python", sources=["basics"])
                return len(results) == 1

    asyncio.run(async_test("kb_search_specific_source", test_kb_search_specific_source()))

    async def test_kb_get_document():
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("Test content")

            kb = KnowledgeBase(sources=[
                {"type": "local", "path": tmpdir}
            ])
            await kb.load()

            docs = kb.list_documents()
            if docs:
                doc = kb.get_document(docs[0].id)
                return doc is not None
            return False

    asyncio.run(async_test("kb_get_document", test_kb_get_document()))

    async def test_kb_list_documents():
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "doc1.md").write_text("Doc 1")
            Path(tmpdir, "doc2.md").write_text("Doc 2")

            kb = KnowledgeBase(sources=[
                {"type": "local", "path": tmpdir}
            ])
            await kb.load()

            return len(kb.list_documents()) == 2

    asyncio.run(async_test("kb_list_documents", test_kb_list_documents()))

    async def test_kb_list_documents_by_source():
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                Path(tmpdir1, "doc1.md").write_text("Doc 1")
                Path(tmpdir2, "doc2.md").write_text("Doc 2")
                Path(tmpdir2, "doc3.md").write_text("Doc 3")

                kb = KnowledgeBase()
                kb.add_source({"type": "local", "path": tmpdir1}, name="source1")
                kb.add_source({"type": "local", "path": tmpdir2}, name="source2")
                await kb.load()

                return len(kb.list_documents("source2")) == 2

    asyncio.run(async_test("kb_list_documents_by_source", test_kb_list_documents_by_source()))

    print("\n=== DocumentChunker 测试 ===")

    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

    # 测试短文档
    short_doc = Document(id="short", content="Short content")
    chunks = chunker.chunk(short_doc)
    test("chunker_short_doc", len(chunks) == 1)

    # 测试长文档
    long_content = "\n\n".join([f"Paragraph {i} with some content." for i in range(20)])
    long_doc = Document(id="long", content=long_content)
    chunks = chunker.chunk(long_doc)
    test("chunker_long_doc", len(chunks) > 1)

    # 测试分块 ID
    test("chunker_chunk_id", chunks[0].id.startswith("long_chunk_"))

    # 测试分块 metadata
    test("chunker_chunk_metadata", chunks[0].metadata.get("parent_id") == "long")

    # 测试超长段落
    very_long_para = "A" * 500
    very_long_doc = Document(id="verylong", content=very_long_para)
    chunks = chunker.chunk(very_long_doc)
    test("chunker_very_long_para", len(chunks) > 1)

    print("\n=== MarkdownParser 测试 ===")

    md_content = """# Title

Introduction paragraph.

## Section 1

Content of section 1.

### Subsection 1.1

More content.

## Section 2

Final content.
"""

    sections = MarkdownParser.extract_sections(md_content)
    test("md_extract_sections", len(sections) == 4)
    test("md_section_level", sections[0]["level"] == 1)
    test("md_section_title", sections[0]["title"] == "Title")

    # 测试代码块提取
    code_md = """
Some text.

```python
def hello():
    print("Hello")
```

More text.

```javascript
console.log("Hi");
```
"""

    code_blocks = MarkdownParser.extract_code_blocks(code_md)
    test("md_extract_code_blocks", len(code_blocks) == 2)
    test("md_code_language", code_blocks[0]["language"] == "python")

    # 测试链接提取
    link_md = """
Check out [Google](https://google.com) and [GitHub](https://github.com).
"""

    links = MarkdownParser.extract_links(link_md)
    test("md_extract_links", len(links) == 2)
    test("md_link_text", links[0]["text"] == "Google")
    test("md_link_url", links[0]["url"] == "https://google.com")

    print("\n=== NotionSource 测试 ===")

    async def test_notion_no_token():
        config = SourceConfig(type=SourceType.NOTION)
        source = NotionSource(config)
        docs = await source.load()
        return len(docs) == 0

    asyncio.run(async_test("notion_no_token", test_notion_no_token()))

    print("\n=== ConfluenceSource 测试 ===")

    async def test_confluence_no_config():
        config = SourceConfig(type=SourceType.CONFLUENCE)
        source = ConfluenceSource(config)
        docs = await source.load()
        return len(docs) == 0

    asyncio.run(async_test("confluence_no_config", test_confluence_no_config()))

    print("\n=== 集成测试 ===")

    async def test_integration_full_workflow():
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建多个文档
            Path(tmpdir, "guide.md").write_text("""# Python Guide

## Introduction

Python is a programming language.

## Installation

Use pip to install packages.
""")
            Path(tmpdir, "api.md").write_text("""# API Reference

## Functions

### hello()

Prints hello world.
""")

            # 创建知识库
            kb = KnowledgeBase(sources=[
                {"type": "local", "path": tmpdir}
            ])

            # 搜索
            results = await kb.search("Python")
            if len(results) != 1:
                return False

            # 获取文档
            doc = results[0].document

            # 分块
            chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
            chunks = chunker.chunk(doc)

            # 解析 Markdown
            sections = MarkdownParser.extract_sections(doc.content)

            return len(chunks) > 0 and len(sections) > 0

    asyncio.run(async_test("integration_full_workflow", test_integration_full_workflow()))

    async def test_integration_vector_search():
        config = SourceConfig(type=SourceType.VECTOR_DB)
        source = VectorDBSource(config)

        # 简单的词袋嵌入
        def bag_of_words_embed(text):
            words = set(text.lower().split())
            vocab = ["python", "java", "programming", "code", "function"]
            return [1.0 if w in words else 0.0 for w in vocab]

        source.set_embedding_function(bag_of_words_embed)

        await source.add_document(Document(id="d1", content="Python programming code"))
        await source.add_document(Document(id="d2", content="Java programming code"))
        await source.add_document(Document(id="d3", content="Python function example"))

        results = await source.search("Python code")

        # Python 相关文档应该排在前面
        return len(results) == 3 and results[0].document.id in ["d1", "d3"]

    asyncio.run(async_test("integration_vector_search", test_integration_vector_search()))

    # 打印总结
    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
