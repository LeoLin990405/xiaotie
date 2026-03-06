"""Tests for the tree-sitter based RepoMapEngine (v2).

Tests cover:
- TreeSitterParser: symbol extraction per language
- TagCache: persistence and invalidation
- DependencyGraph: graph construction from tags
- PageRankScorer: ranking with personalization
- RepoMapEngine: end-to-end map generation + token budgeting
- Smoke test: run on the xiaotie codebase itself
"""

import os
import tempfile
import shutil
from pathlib import Path

import pytest

from xiaotie.repomap_v2 import (
    Tag,
    TreeSitterParser,
    TagCache,
    DependencyGraph,
    PageRankScorer,
    RepoMapEngine,
    _is_valid_identifier,
    _language_for_file,
    _serialize_tags,
    _deserialize_tags,
    HAS_TREE_SITTER,
    HAS_NETWORKX,
)


# --- Fixtures ---


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with sample source files."""
    # Python file
    py_file = tmp_path / "main.py"
    py_file.write_text(
        'import os\n'
        'from utils import helper\n'
        '\n'
        'class Application:\n'
        '    """Main app."""\n'
        '    def __init__(self):\n'
        '        self.name = "app"\n'
        '\n'
        '    def run(self):\n'
        '        result = helper()\n'
        '        return result\n'
        '\n'
        'def main():\n'
        '    app = Application()\n'
        '    app.run()\n'
    )

    py_util = tmp_path / "utils.py"
    py_util.write_text(
        'import json\n'
        '\n'
        'CONSTANT = 42\n'
        '\n'
        'def helper():\n'
        '    return CONSTANT\n'
        '\n'
        'def format_output(data):\n'
        '    return json.dumps(data)\n'
    )

    # JavaScript file
    js_file = tmp_path / "app.js"
    js_file.write_text(
        'import { render } from "./renderer";\n'
        '\n'
        'class Widget {\n'
        '  constructor(name) {\n'
        '    this.name = name;\n'
        '  }\n'
        '  display() { return this.name; }\n'
        '}\n'
        '\n'
        'function createApp() {\n'
        '  return new Widget("main");\n'
        '}\n'
        '\n'
        'export default createApp;\n'
    )

    # TypeScript file
    ts_file = tmp_path / "types.ts"
    ts_file.write_text(
        'export interface Config {\n'
        '  name: string;\n'
        '  debug: boolean;\n'
        '}\n'
        '\n'
        'export type Handler = (event: Event) => void;\n'
        '\n'
        'export enum Status {\n'
        '  Active = "active",\n'
        '  Inactive = "inactive",\n'
        '}\n'
        '\n'
        'export class Manager {\n'
        '  private config: Config;\n'
        '  constructor(config: Config) { this.config = config; }\n'
        '  getStatus(): Status { return Status.Active; }\n'
        '}\n'
    )

    # Go file
    go_file = tmp_path / "server.go"
    go_file.write_text(
        'package main\n'
        '\n'
        'import "net/http"\n'
        '\n'
        'type Server struct {\n'
        '    Port int\n'
        '    Host string\n'
        '}\n'
        '\n'
        'func NewServer(port int) *Server {\n'
        '    return &Server{Port: port}\n'
        '}\n'
        '\n'
        'func (s *Server) Start() error {\n'
        '    return http.ListenAndServe(s.Host, nil)\n'
        '}\n'
    )

    # Rust file
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text(
        'use std::collections::HashMap;\n'
        '\n'
        'pub struct Config {\n'
        '    pub name: String,\n'
        '    pub values: HashMap<String, String>,\n'
        '}\n'
        '\n'
        'pub enum Level {\n'
        '    Info,\n'
        '    Warn,\n'
        '    Error,\n'
        '}\n'
        '\n'
        'pub fn create_config(name: &str) -> Config {\n'
        '    Config {\n'
        '        name: name.to_string(),\n'
        '        values: HashMap::new(),\n'
        '    }\n'
        '}\n'
        '\n'
        'pub trait Logger {\n'
        '    fn log(&self, level: Level, msg: &str);\n'
        '}\n'
    )

    # Java file
    java_file = tmp_path / "App.java"
    java_file.write_text(
        'package com.example;\n'
        '\n'
        'import java.util.List;\n'
        '\n'
        'public class App {\n'
        '    private String name;\n'
        '\n'
        '    public App(String name) {\n'
        '        this.name = name;\n'
        '    }\n'
        '\n'
        '    public void start() {\n'
        '        System.out.println("Starting " + name);\n'
        '    }\n'
        '}\n'
        '\n'
        'interface Service {\n'
        '    void execute();\n'
        '}\n'
    )

    # C file
    c_file = tmp_path / "main.c"
    c_file.write_text(
        '#include <stdio.h>\n'
        '#include "utils.h"\n'
        '\n'
        'struct Point {\n'
        '    int x;\n'
        '    int y;\n'
        '};\n'
        '\n'
        'int add(int a, int b) {\n'
        '    return a + b;\n'
        '}\n'
        '\n'
        'int main() {\n'
        '    struct Point p = {1, 2};\n'
        '    printf("%d\\n", add(p.x, p.y));\n'
        '    return 0;\n'
        '}\n'
    )

    # Create an ignored directory
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("junk")

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_bytes(b"cache")

    return tmp_path


@pytest.fixture
def parser():
    if not HAS_TREE_SITTER:
        pytest.skip("tree-sitter not installed")
    return TreeSitterParser()


@pytest.fixture
def engine(tmp_workspace):
    eng = RepoMapEngine(str(tmp_workspace))
    yield eng
    eng.close()


# --- TreeSitterParser Tests ---


class TestTreeSitterParser:
    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_python(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "main.py")
        tags = parser.parse_file(abs_path, "main.py", "python")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Application" in def_names
        assert "__init__" in def_names
        assert "run" in def_names
        assert "main" in def_names

        # Verify line numbers
        app_tag = next(t for t in defs if t.name == "Application")
        assert app_tag.line == 4
        assert app_tag.rel_fname == "main.py"

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_python_refs(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "main.py")
        tags = parser.parse_file(abs_path, "main.py", "python")

        refs = [t for t in tags if t.kind == "ref"]
        ref_names = {t.name for t in refs}

        # Should reference 'helper', 'Application', 'os', etc.
        assert "helper" in ref_names
        assert "Application" in ref_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_javascript(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "app.js")
        tags = parser.parse_file(abs_path, "app.js", "javascript")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Widget" in def_names
        assert "createApp" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_typescript(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "types.ts")
        tags = parser.parse_file(abs_path, "types.ts", "typescript")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Config" in def_names
        assert "Handler" in def_names
        assert "Status" in def_names
        assert "Manager" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_go(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "server.go")
        tags = parser.parse_file(abs_path, "server.go", "go")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Server" in def_names
        assert "NewServer" in def_names
        assert "Start" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_rust(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "lib.rs")
        tags = parser.parse_file(abs_path, "lib.rs", "rust")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Config" in def_names
        assert "Level" in def_names
        assert "create_config" in def_names
        assert "Logger" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_java(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "App.java")
        tags = parser.parse_file(abs_path, "App.java", "java")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "App" in def_names
        assert "start" in def_names
        assert "Service" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_c(self, parser, tmp_workspace):
        abs_path = str(tmp_workspace / "main.c")
        tags = parser.parse_file(abs_path, "main.c", "c")

        defs = [t for t in tags if t.kind == "def"]
        def_names = {t.name for t in defs}

        assert "Point" in def_names
        assert "add" in def_names
        assert "main" in def_names

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_nonexistent_file(self, parser):
        tags = parser.parse_file("/nonexistent/file.py", "file.py", "python")
        assert tags == []

    @pytest.mark.skipif(not HAS_TREE_SITTER, reason="tree-sitter not installed")
    def test_parse_empty_file(self, parser, tmp_path):
        empty = tmp_path / "empty.py"
        empty.write_text("")
        tags = parser.parse_file(str(empty), "empty.py", "python")
        assert tags == []


# --- TagCache Tests ---


class TestTagCache:
    def test_put_and_get(self, tmp_path):
        cache = TagCache(str(tmp_path / "cache"))
        tags = [
            Tag(rel_fname="foo.py", fname="/abs/foo.py", line=1, name="Foo", kind="def"),
            Tag(rel_fname="foo.py", fname="/abs/foo.py", line=5, name="bar", kind="ref"),
        ]
        cache.put("/abs/foo.py", 1000.0, tags)

        result = cache.get("/abs/foo.py", 1000.0)
        assert result is not None
        assert len(result) == 2
        assert result[0].name == "Foo"
        assert result[1].name == "bar"
        cache.close()

    def test_cache_miss_on_mtime_change(self, tmp_path):
        cache = TagCache(str(tmp_path / "cache"))
        tags = [Tag(rel_fname="a.py", fname="/a.py", line=1, name="X", kind="def")]
        cache.put("/a.py", 1000.0, tags)

        # Different mtime = cache miss
        result = cache.get("/a.py", 2000.0)
        assert result is None
        cache.close()

    def test_invalidate_specific(self, tmp_path):
        cache = TagCache(str(tmp_path / "cache"))
        cache.put("/a.py", 1.0, [Tag("a.py", "/a.py", 1, "A", "def")])
        cache.put("/b.py", 1.0, [Tag("b.py", "/b.py", 1, "B", "def")])

        cache.invalidate(["/a.py"])

        assert cache.get("/a.py", 1.0) is None
        assert cache.get("/b.py", 1.0) is not None
        cache.close()

    def test_invalidate_all(self, tmp_path):
        cache = TagCache(str(tmp_path / "cache"))
        cache.put("/a.py", 1.0, [Tag("a.py", "/a.py", 1, "A", "def")])
        cache.put("/b.py", 1.0, [Tag("b.py", "/b.py", 1, "B", "def")])

        cache.invalidate()

        assert cache.get("/a.py", 1.0) is None
        assert cache.get("/b.py", 1.0) is None
        cache.close()

    def test_persistence_across_instances(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        cache1 = TagCache(cache_dir)
        cache1.put("/a.py", 1.0, [Tag("a.py", "/a.py", 1, "A", "def")])
        cache1.close()

        cache2 = TagCache(cache_dir)
        result = cache2.get("/a.py", 1.0)
        assert result is not None
        assert result[0].name == "A"
        cache2.close()


# --- DependencyGraph Tests ---


class TestDependencyGraph:
    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_build_graph(self):
        builder = DependencyGraph()
        all_tags = {
            "main.py": [
                Tag("main.py", "/main.py", 1, "main", "def"),
                Tag("main.py", "/main.py", 2, "helper", "ref"),  # refs utils.helper
                Tag("main.py", "/main.py", 3, "Application", "def"),
            ],
            "utils.py": [
                Tag("utils.py", "/utils.py", 1, "helper", "def"),
                Tag("utils.py", "/utils.py", 2, "format_output", "def"),
            ],
        }

        graph = builder.build(all_tags)

        assert "main.py" in graph.nodes()
        assert "utils.py" in graph.nodes()

        # main.py references 'helper' which is defined in utils.py
        assert graph.has_edge("main.py", "utils.py")

        # utils.py doesn't reference anything in main.py
        assert not graph.has_edge("utils.py", "main.py")

    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_build_graph_no_self_edges(self):
        builder = DependencyGraph()
        all_tags = {
            "a.py": [
                Tag("a.py", "/a.py", 1, "Foo", "def"),
                Tag("a.py", "/a.py", 5, "Foo", "ref"),  # self-reference
            ],
        }
        graph = builder.build(all_tags)
        assert not graph.has_edge("a.py", "a.py")

    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_build_graph_empty(self):
        builder = DependencyGraph()
        graph = builder.build({})
        assert len(graph.nodes()) == 0


# --- PageRankScorer Tests ---


class TestPageRankScorer:
    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_rank_basic(self):
        import networkx as nx

        graph = nx.MultiDiGraph()
        graph.add_edge("a.py", "core.py", ident="Base")
        graph.add_edge("b.py", "core.py", ident="Base")
        graph.add_edge("c.py", "core.py", ident="helper")

        scorer = PageRankScorer()
        scores = scorer.rank(graph, chat_files=[])

        # core.py should have highest score (most referenced)
        assert scores["core.py"] > scores["a.py"]
        assert scores["core.py"] > scores["b.py"]

    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_rank_with_personalization(self):
        import networkx as nx

        graph = nx.MultiDiGraph()
        graph.add_edge("a.py", "core.py", ident="Base")
        graph.add_edge("b.py", "other.py", ident="Util")
        graph.add_edge("a.py", "other.py", ident="Util")

        scorer = PageRankScorer()

        # When chat_file is a.py, nodes connected to a.py should rank higher
        scores = scorer.rank(graph, chat_files=["a.py"])

        # core.py and other.py are both referenced by a.py, so they should
        # be boosted. b.py is also connected to other.py but not directly
        # to chat file a.py
        assert scores["core.py"] > 0
        assert scores["other.py"] > 0

    @pytest.mark.skipif(not HAS_NETWORKX, reason="networkx not installed")
    def test_rank_empty_graph(self):
        import networkx as nx

        graph = nx.MultiDiGraph()
        scorer = PageRankScorer()
        scores = scorer.rank(graph, chat_files=[])
        assert scores == {}


# --- RepoMapEngine Integration Tests ---


class TestRepoMapEngine:
    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_get_ranked_map(self, engine, tmp_workspace):
        repo_map = engine.get_ranked_map(
            chat_files=[str(tmp_workspace / "main.py")],
            max_tokens=2048,
        )

        assert len(repo_map) > 0
        # Should contain definitions from other files
        assert "helper" in repo_map or "Widget" in repo_map or "Server" in repo_map

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_token_budget_respected(self, engine):
        # With a tiny budget, output should be short
        repo_map = engine.get_ranked_map(max_tokens=50)
        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(repo_map) // 4
        # Allow some slack but should be roughly within budget
        assert estimated_tokens < 100  # generous upper bound for 50 token budget

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_get_definitions(self, engine):
        defs = engine.get_definitions("main.py")
        def_names = {t.name for t in defs}
        assert "Application" in def_names
        assert "main" in def_names

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_get_stats(self, engine):
        engine.get_ranked_map(max_tokens=2048)
        stats = engine.get_stats()

        assert stats["files_parsed"] >= 5  # py, js, ts, go, rs, java, c
        assert stats["total_definitions"] > 10
        assert stats["total_references"] > 0
        assert "python" in stats["languages"]
        assert "javascript" in stats["languages"]

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_ignores_node_modules(self, engine, tmp_workspace):
        engine.get_ranked_map(max_tokens=2048)
        parsed_files = set(engine._file_tags.keys())
        assert not any("node_modules" in f for f in parsed_files)
        assert not any("__pycache__" in f for f in parsed_files)

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_cache_reuse(self, engine, tmp_workspace):
        # First call parses everything
        map1 = engine.get_ranked_map(max_tokens=2048)

        # Second call should use cache
        map2 = engine.get_ranked_map(max_tokens=2048)

        assert map1 == map2

    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    def test_invalidate_and_reparse(self, engine, tmp_workspace):
        engine.get_ranked_map(max_tokens=2048)

        # Modify a file
        main_py = tmp_workspace / "main.py"
        main_py.write_text(
            'def new_function():\n'
            '    return "new"\n'
        )

        # Invalidate and re-scan
        engine.invalidate_cache([str(main_py)])
        engine.get_ranked_map(max_tokens=2048)

        defs = engine.get_definitions("main.py")
        def_names = {t.name for t in defs}
        assert "new_function" in def_names
        assert "Application" not in def_names  # old class gone


# --- Smoke Test on Xiaotie Codebase ---


class TestSmokeXiaotieCosdebase:
    @pytest.mark.skipif(
        not (HAS_TREE_SITTER and HAS_NETWORKX),
        reason="tree-sitter or networkx not installed",
    )
    @pytest.mark.smoke
    def test_xiaotie_repo_map(self):
        """Run the engine on the xiaotie codebase itself."""
        xiaotie_dir = Path(__file__).parent.parent.parent / "xiaotie"
        if not xiaotie_dir.exists():
            pytest.skip("xiaotie source directory not found")

        engine = RepoMapEngine(
            str(xiaotie_dir.parent),
            cache_dir=str(Path(tempfile.mkdtemp()) / "cache"),
        )

        try:
            repo_map = engine.get_ranked_map(
                chat_files=["xiaotie/repomap_v2.py"],
                max_tokens=2048,
            )

            assert len(repo_map) > 0

            stats = engine.get_stats()
            assert stats["files_parsed"] > 20  # xiaotie has 40+ python files
            assert stats["total_definitions"] > 50
            assert "python" in stats["languages"]

            # Verify key symbols appear
            all_defs = []
            for tags in engine._file_tags.values():
                all_defs.extend(t.name for t in tags if t.kind == "def")

            # Core classes should be found
            assert "Agent" in all_defs
            assert "Tool" in all_defs
            assert "RepoMapEngine" in all_defs

        finally:
            engine.close()


# --- Utility Function Tests ---


class TestUtilities:
    def test_is_valid_identifier(self):
        assert _is_valid_identifier("MyClass") is True
        assert _is_valid_identifier("helper_func") is True
        assert _is_valid_identifier("_private") is True

        # Keywords should be invalid
        assert _is_valid_identifier("self") is False
        assert _is_valid_identifier("return") is False
        assert _is_valid_identifier("class") is False
        assert _is_valid_identifier("const") is False
        assert _is_valid_identifier("fn") is False

        # Edge cases
        assert _is_valid_identifier("") is False
        assert _is_valid_identifier("None") is False

    def test_language_for_file(self):
        assert _language_for_file("foo.py") == "python"
        assert _language_for_file("bar.js") == "javascript"
        assert _language_for_file("baz.ts") == "typescript"
        assert _language_for_file("main.go") == "go"
        assert _language_for_file("lib.rs") == "rust"
        assert _language_for_file("App.java") == "java"
        assert _language_for_file("main.c") == "c"
        assert _language_for_file("main.cpp") == "cpp"
        assert _language_for_file("header.h") == "c"
        assert _language_for_file("header.hpp") == "cpp"
        assert _language_for_file("unknown.xyz") is None

    def test_serialize_deserialize_tags(self):
        tags = [
            Tag("a.py", "/abs/a.py", 10, "Foo", "def"),
            Tag("b.py", "/abs/b.py", 20, "bar", "ref"),
        ]
        data = _serialize_tags(tags)
        result = _deserialize_tags(data)

        assert len(result) == 2
        assert result[0].name == "Foo"
        assert result[0].kind == "def"
        assert result[0].line == 10
        assert result[1].name == "bar"
        assert result[1].kind == "ref"
