"""Tree-sitter based Repository Map Engine (v2)

Inspired by Aider's RepoMap architecture:
1. Parse source files with tree-sitter -> extract Tags (definitions + references)
2. Build a NetworkX DiGraph (files as nodes, cross-file refs as edges)
3. Rank with PageRank (personalized to current chat files)
4. Format top-ranked definitions within a token budget

Supported languages: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++

Falls back to regex extraction (v1 RepoMap) if tree-sitter is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# --- Optional dependency imports ---

try:
    import tree_sitter_languages

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


# --- Data Structures ---


@dataclass(frozen=True)
class Tag:
    """Code identifier extracted from source."""

    rel_fname: str
    fname: str
    line: int
    name: str
    kind: str  # "def" or "ref"


@dataclass
class FileEntry:
    """Metadata about a scanned file."""

    rel_path: str
    abs_path: str
    mtime: float
    size: int


# --- Constants ---

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
}

DEFAULT_IGNORE = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "out",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    "coverage",
    ".nyc_output",
    ".ruff_cache",
    "htmlcov",
    ".mypy_cache",
    ".tox",
    "egg-info",
}

DEFAULT_IGNORE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".dylib",
    ".o",
    ".a",
    ".min.js",
    ".min.css",
    ".map",
    ".lock",
    ".whl",
    ".egg",
}


# --- Tree-Sitter Parser ---


# Node type queries per language for definitions
# Maps language -> list of (node_type, name_child_field_or_index)
DEFINITION_QUERIES = {
    "python": [
        ("class_definition", "name"),
        ("function_definition", "name"),
    ],
    "javascript": [
        ("class_declaration", "name"),
        ("function_declaration", "name"),
        ("method_definition", "name"),
        # const foo = ...
        ("variable_declarator", "name"),
    ],
    "typescript": [
        ("class_declaration", "name"),
        ("function_declaration", "name"),
        ("method_definition", "name"),
        ("interface_declaration", "name"),
        ("type_alias_declaration", "name"),
        ("variable_declarator", "name"),
        ("enum_declaration", "name"),
    ],
    "go": [
        ("type_declaration", None),  # handled specially
        ("function_declaration", "name"),
        ("method_declaration", "name"),
    ],
    "rust": [
        ("struct_item", "name"),
        ("enum_item", "name"),
        ("function_item", "name"),
        ("impl_item", None),  # handled specially
        ("trait_item", "name"),
        ("type_item", "name"),
    ],
    "java": [
        ("class_declaration", "name"),
        ("interface_declaration", "name"),
        ("method_declaration", "name"),
        ("enum_declaration", "name"),
    ],
    "c": [
        ("function_definition", "declarator"),
        ("struct_specifier", "name"),
        ("enum_specifier", "name"),
        ("type_definition", "declarator"),
    ],
    "cpp": [
        ("function_definition", "declarator"),
        ("class_specifier", "name"),
        ("struct_specifier", "name"),
        ("enum_specifier", "name"),
        ("namespace_definition", "name"),
    ],
}

# Import node types per language
IMPORT_QUERIES = {
    "python": ["import_statement", "import_from_statement"],
    "javascript": ["import_statement", "call_expression"],  # require()
    "typescript": ["import_statement", "call_expression"],
    "go": ["import_declaration"],
    "rust": ["use_declaration"],
    "java": ["import_declaration"],
    "c": ["preproc_include"],
    "cpp": ["preproc_include", "using_declaration"],
}


class TreeSitterParser:
    """Parses source files using tree-sitter to extract Tags."""

    def __init__(self):
        if not HAS_TREE_SITTER:
            raise ImportError(
                "tree-sitter-languages is required. Install with: pip install 'xiaotie[repomap]'"
            )
        self._parsers: Dict[str, object] = {}

    def _get_parser(self, language: str):
        if language not in self._parsers:
            try:
                self._parsers[language] = tree_sitter_languages.get_parser(language)
            except Exception as e:
                logger.warning(f"Failed to get parser for {language}: {e}")
                return None
        return self._parsers[language]

    def _extract_name_from_node(
        self, node, name_field: Optional[str], language: str
    ) -> Optional[str]:
        """Extract the identifier name from a definition node."""
        if name_field is None:
            # Special handling
            if language == "go" and node.type == "type_declaration":
                # type_declaration -> type_spec -> name
                for child in node.children:
                    if child.type == "type_spec":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            return name_node.text.decode("utf-8", errors="replace")
            elif language == "rust" and node.type == "impl_item":
                type_node = child_by_field_safe(node, "type")
                if type_node:
                    return f"impl {type_node.text.decode('utf-8', errors='replace')}"
            return None

        name_node = child_by_field_safe(node, name_field)
        if name_node is None:
            return None

        # For C/C++ function_definition, declarator can be nested
        # (e.g., pointer_declarator -> function_declarator -> identifier)
        text = name_node.text.decode("utf-8", errors="replace")

        # Extract just the identifier from complex declarators
        if name_node.type in ("function_declarator", "pointer_declarator"):
            ident = _find_first_identifier(name_node)
            if ident:
                text = ident

        return text

    def parse_file(self, abs_path: str, rel_path: str, language: str) -> List[Tag]:
        """Parse a single file and return its Tags (definitions and references)."""
        parser = self._get_parser(language)
        if parser is None:
            return []

        try:
            content = Path(abs_path).read_bytes()
        except (OSError, PermissionError):
            return []

        try:
            tree = parser.parse(content)
        except Exception as e:
            logger.debug(f"tree-sitter parse error for {rel_path}: {e}")
            return []

        tags: List[Tag] = []
        def_queries = DEFINITION_QUERIES.get(language, [])

        # Walk tree for definitions
        self._walk_for_definitions(tree.root_node, rel_path, abs_path, language, def_queries, tags)

        # Walk tree for identifier references
        self._walk_for_references(tree.root_node, rel_path, abs_path, language, tags)

        return tags

    def _walk_for_definitions(
        self,
        node,
        rel_path: str,
        abs_path: str,
        language: str,
        def_queries: list,
        tags: List[Tag],
    ):
        """Walk AST to find definition nodes."""
        for node_type, name_field in def_queries:
            if node.type == node_type:
                name = self._extract_name_from_node(node, name_field, language)
                if name and _is_valid_identifier(name):
                    tags.append(
                        Tag(
                            rel_fname=rel_path,
                            fname=abs_path,
                            line=node.start_point[0] + 1,
                            name=name,
                            kind="def",
                        )
                    )

        for child in node.children:
            self._walk_for_definitions(child, rel_path, abs_path, language, def_queries, tags)

    def _walk_for_references(
        self,
        node,
        rel_path: str,
        abs_path: str,
        language: str,
        tags: List[Tag],
    ):
        """Walk AST to find identifier references (not definitions)."""
        if node.type == "identifier" and node.parent is not None:
            parent_type = node.parent.type
            # Skip if this identifier IS the name of a definition
            def_node_types = {q[0] for q in DEFINITION_QUERIES.get(language, [])}
            if parent_type not in def_node_types:
                name = node.text.decode("utf-8", errors="replace")
                if _is_valid_identifier(name) and len(name) > 1:
                    tags.append(
                        Tag(
                            rel_fname=rel_path,
                            fname=abs_path,
                            line=node.start_point[0] + 1,
                            name=name,
                            kind="ref",
                        )
                    )
                return  # Don't recurse into identifier children

        for child in node.children:
            self._walk_for_references(child, rel_path, abs_path, language, tags)


# --- Tag Cache ---


class TagCache:
    """Persistent disk cache for file tags, keyed by file path + mtime.

    Uses SQLite for atomic reads/writes and crash safety.
    Falls back to in-memory dict if SQLite fails.
    """

    def __init__(self, cache_dir: str):
        self._cache_dir = Path(cache_dir)
        self._db_path = self._cache_dir / "tags_cache.db"
        self._memory_cache: Dict[str, Tuple[float, List[Tag]]] = {}
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self._db_path), timeout=5.0)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS tags (path TEXT PRIMARY KEY, mtime REAL, data TEXT)"
            )
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.commit()
        except Exception as e:
            logger.warning(f"TagCache: SQLite init failed, using in-memory: {e}")
            self._db = None

    def get(self, abs_path: str, mtime: float) -> Optional[List[Tag]]:
        """Get cached tags if file hasn't changed."""
        # Check memory cache first
        if abs_path in self._memory_cache:
            cached_mtime, tags = self._memory_cache[abs_path]
            if cached_mtime == mtime:
                return tags

        # Check disk cache
        if self._db is not None:
            try:
                row = self._db.execute(
                    "SELECT mtime, data FROM tags WHERE path = ?", (abs_path,)
                ).fetchone()
                if row and row[0] == mtime:
                    tags = _deserialize_tags(row[1])
                    self._memory_cache[abs_path] = (mtime, tags)
                    return tags
            except Exception:
                pass

        return None

    def put(self, abs_path: str, mtime: float, tags: List[Tag]):
        """Cache tags for a file."""
        self._memory_cache[abs_path] = (mtime, tags)
        if self._db is not None:
            try:
                data = _serialize_tags(tags)
                self._db.execute(
                    "INSERT OR REPLACE INTO tags (path, mtime, data) VALUES (?, ?, ?)",
                    (abs_path, mtime, data),
                )
                self._db.commit()
            except Exception as e:
                logger.debug(f"TagCache: write failed: {e}")

    def invalidate(self, paths: Optional[List[str]] = None):
        """Invalidate cache entries."""
        if paths is None:
            self._memory_cache.clear()
            if self._db is not None:
                try:
                    self._db.execute("DELETE FROM tags")
                    self._db.commit()
                except Exception:
                    pass
        else:
            for p in paths:
                self._memory_cache.pop(p, None)
                if self._db is not None:
                    try:
                        self._db.execute("DELETE FROM tags WHERE path = ?", (p,))
                    except Exception:
                        pass
            if self._db is not None:
                try:
                    self._db.commit()
                except Exception:
                    pass

    def close(self):
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass


# --- Dependency Graph ---


class DependencyGraph:
    """Builds a NetworkX MultiDiGraph from Tags.

    Nodes are files. Edges connect files that share identifiers:
    if file A defines 'Foo' and file B references 'Foo', add edge B->A.
    """

    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError("networkx is required. Install with: pip install 'xiaotie[repomap]'")

    def build(self, all_tags: Dict[str, List[Tag]]) -> "nx.MultiDiGraph":
        """Build dependency graph from file -> tags mapping.

        Args:
            all_tags: mapping of rel_path -> list of Tags for that file

        Returns:
            MultiDiGraph where nodes are rel_paths, edges represent references
        """
        graph = nx.MultiDiGraph()

        # Index: identifier_name -> set of files that define it
        definitions: Dict[str, Set[str]] = {}
        for rel_path, tags in all_tags.items():
            graph.add_node(rel_path)
            for tag in tags:
                if tag.kind == "def":
                    definitions.setdefault(tag.name, set()).add(rel_path)

        # Add edges: for each reference, link to the file(s) that define it
        for rel_path, tags in all_tags.items():
            for tag in tags:
                if tag.kind == "ref" and tag.name in definitions:
                    for def_file in definitions[tag.name]:
                        if def_file != rel_path:
                            graph.add_edge(rel_path, def_file, ident=tag.name)

        return graph


# --- PageRank Scorer ---


class PageRankScorer:
    """Ranks files by importance using personalized PageRank."""

    def rank(
        self,
        graph: "nx.MultiDiGraph",
        chat_files: List[str],
        alpha: float = 0.85,
    ) -> Dict[str, float]:
        """Compute personalized PageRank scores.

        Args:
            graph: dependency graph from DependencyGraph.build()
            chat_files: files currently in focus (get boosted personalization)
            alpha: damping factor (0.85 = standard)

        Returns:
            Mapping of rel_path -> PageRank score
        """
        if len(graph) == 0:
            return {}

        # Personalization: boost files that reference chat_files
        personalization = {}
        chat_set = set(chat_files)
        for node in graph.nodes():
            if node in chat_set:
                personalization[node] = 0.0  # Don't rank chat files themselves
            else:
                # Boost nodes that are neighbors of chat files
                connected = False
                for cf in chat_set:
                    if graph.has_node(cf) and (
                        graph.has_edge(node, cf) or graph.has_edge(cf, node)
                    ):
                        connected = True
                        break
                personalization[node] = 10.0 if connected else 1.0

        # Normalize personalization
        total = sum(personalization.values())
        if total > 0:
            personalization = {k: v / total for k, v in personalization.items()}
        else:
            personalization = None

        try:
            scores = nx.pagerank(
                graph,
                alpha=alpha,
                personalization=personalization,
                max_iter=200,
            )
        except nx.PowerIterationFailedConvergence:
            logger.warning("PageRank failed to converge, using uniform scores")
            scores = {node: 1.0 / len(graph) for node in graph.nodes()}

        return scores


# --- RepoMap Engine ---


class RepoMapEngine:
    """Composes a token-budgeted repository map from ranked symbols.

    Usage:
        engine = RepoMapEngine("/path/to/project")
        repo_map = engine.get_ranked_map(
            chat_files=["src/main.py"],
            other_files=["src/utils.py", "src/models.py"],
            max_tokens=2048,
        )
    """

    def __init__(
        self,
        workspace_dir: str,
        cache_dir: Optional[str] = None,
        ignore_patterns: Optional[Set[str]] = None,
        max_file_size: int = 100_000,
    ):
        self.workspace = Path(workspace_dir).resolve()
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE
        self.max_file_size = max_file_size

        cache_path = cache_dir or str(self.workspace / ".xiaotie" / "cache")
        self._cache = TagCache(cache_path)
        self._parser = TreeSitterParser() if HAS_TREE_SITTER else None
        self._graph_builder = DependencyGraph() if HAS_NETWORKX else None
        self._scorer = PageRankScorer() if HAS_NETWORKX else None

        # Collected tags per file
        self._file_tags: Dict[str, List[Tag]] = {}

    def get_ranked_map(
        self,
        chat_files: Optional[List[str]] = None,
        other_files: Optional[List[str]] = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a ranked repo map within a token budget.

        Args:
            chat_files: files actively being discussed (get boosted)
            other_files: all other repo files (None = auto-scan)
            max_tokens: maximum tokens for the output

        Returns:
            Formatted repo map text
        """
        chat_files = chat_files or []
        chat_rel = [self._to_rel(f) for f in chat_files]

        # Auto-scan if no other_files provided
        if other_files is None:
            all_files = self._scan_files()
            other_rel = [f.rel_path for f in all_files if f.rel_path not in set(chat_rel)]
        else:
            other_rel = [self._to_rel(f) for f in other_files]

        all_rel = list(set(chat_rel + other_rel))

        # Parse all files and collect tags
        self._file_tags.clear()
        for rel_path in all_rel:
            abs_path = str(self.workspace / rel_path)
            tags = self._get_tags(abs_path, rel_path)
            if tags:
                self._file_tags[rel_path] = tags

        # Build graph and rank
        if self._graph_builder and self._scorer and len(self._file_tags) > 1:
            graph = self._graph_builder.build(self._file_tags)
            scores = self._scorer.rank(graph, chat_rel)
        else:
            # Fallback: score by definition count
            scores = {}
            for rel_path, tags in self._file_tags.items():
                def_count = sum(1 for t in tags if t.kind == "def")
                scores[rel_path] = def_count

        # Sort files by score (descending), exclude chat files
        ranked_files = sorted(
            [(rel, score) for rel, score in scores.items() if rel not in set(chat_rel)],
            key=lambda x: -x[1],
        )

        # Format output within token budget
        return self._format_map(ranked_files, max_tokens)

    def get_tags(self, fname: str) -> List[Tag]:
        """Extract tags from a file (public API)."""
        abs_path = str(Path(fname).resolve())
        rel_path = self._to_rel(fname)
        return self._get_tags(abs_path, rel_path)

    def invalidate_cache(self, fnames: Optional[List[str]] = None) -> None:
        """Invalidate tag cache."""
        if fnames:
            abs_paths = [str(Path(f).resolve()) for f in fnames]
            self._cache.invalidate(abs_paths)
        else:
            self._cache.invalidate()

    def get_definitions(self, rel_path: str) -> List[Tag]:
        """Get only definition tags for a file."""
        abs_path = str(self.workspace / rel_path)
        tags = self._get_tags(abs_path, rel_path)
        return [t for t in tags if t.kind == "def"]

    def get_stats(self) -> Dict:
        """Get statistics about the last scan."""
        total_defs = sum(
            sum(1 for t in tags if t.kind == "def") for tags in self._file_tags.values()
        )
        total_refs = sum(
            sum(1 for t in tags if t.kind == "ref") for tags in self._file_tags.values()
        )
        languages = set()
        for rel_path in self._file_tags:
            lang = _language_for_file(rel_path)
            if lang:
                languages.add(lang)
        return {
            "files_parsed": len(self._file_tags),
            "total_definitions": total_defs,
            "total_references": total_refs,
            "languages": sorted(languages),
        }

    # --- Internal methods ---

    def _to_rel(self, path: str) -> str:
        """Convert a path to relative (from workspace)."""
        p = Path(path)
        if p.is_absolute():
            try:
                return str(p.resolve().relative_to(self.workspace))
            except ValueError:
                return str(p)
        return str(p)

    def _get_tags(self, abs_path: str, rel_path: str) -> List[Tag]:
        """Get tags for a file, using cache when possible."""
        try:
            stat = os.stat(abs_path)
        except (OSError, PermissionError):
            return []

        if stat.st_size > self.max_file_size:
            return []

        mtime = stat.st_mtime

        # Check cache
        cached = self._cache.get(abs_path, mtime)
        if cached is not None:
            return cached

        # Parse with tree-sitter
        language = _language_for_file(rel_path)
        tags: List[Tag] = []

        if language and self._parser:
            tags = self._parser.parse_file(abs_path, rel_path, language)
        elif language == "python":
            # Regex fallback for Python (v1 compatibility)
            tags = self._regex_parse_python(abs_path, rel_path)

        self._cache.put(abs_path, mtime, tags)
        return tags

    def _regex_parse_python(self, abs_path: str, rel_path: str) -> List[Tag]:
        """Fallback regex parser for Python when tree-sitter is unavailable."""
        try:
            content = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []

        tags = []
        for match in re.finditer(r"^(?:async\s+)?(?:class|def)\s+(\w+)", content, re.MULTILINE):
            line = content[: match.start()].count("\n") + 1
            tags.append(
                Tag(
                    rel_fname=rel_path,
                    fname=abs_path,
                    line=line,
                    name=match.group(1),
                    kind="def",
                )
            )

        return tags

    def _scan_files(self) -> List[FileEntry]:
        """Scan workspace for supported source files."""
        files = []
        for root, dirs, filenames in os.walk(self.workspace):
            # Filter directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_patterns and not d.startswith(".")]

            for filename in filenames:
                # Skip ignored extensions
                ext = Path(filename).suffix.lower()
                if ext in DEFAULT_IGNORE_EXTENSIONS:
                    continue

                # Only supported languages
                if ext not in EXTENSION_TO_LANGUAGE:
                    continue

                file_path = Path(root) / filename
                try:
                    stat = file_path.stat()
                    if stat.st_size > self.max_file_size:
                        continue

                    rel_path = str(file_path.relative_to(self.workspace))
                    files.append(
                        FileEntry(
                            rel_path=rel_path,
                            abs_path=str(file_path),
                            mtime=stat.st_mtime,
                            size=stat.st_size,
                        )
                    )
                except (OSError, PermissionError):
                    continue

        return files

    def _format_map(
        self,
        ranked_files: List[Tuple[str, float]],
        max_tokens: int,
    ) -> str:
        """Format the repo map output within a token budget."""
        lines: List[str] = []
        token_count = 0

        for rel_path, score in ranked_files:
            tags = self._file_tags.get(rel_path, [])
            defs = [t for t in tags if t.kind == "def"]
            if not defs:
                continue

            # Build file section
            file_lines = [f"{rel_path}:"]
            for tag in sorted(defs, key=lambda t: t.line):
                file_lines.append(f"  {tag.name} (L{tag.line})")

            # Estimate tokens (~4 chars per token)
            section_tokens = sum(len(line) for line in file_lines) // 4 + len(file_lines)

            if token_count + section_tokens > max_tokens:
                if lines:
                    lines.append("  ...")
                break

            lines.extend(file_lines)
            token_count += section_tokens

        return "\n".join(lines)

    def close(self):
        """Clean up resources."""
        self._cache.close()


# --- Helper functions ---


def child_by_field_safe(node, field_name: str):
    """Safely get a child node by field name."""
    try:
        return node.child_by_field_name(field_name)
    except Exception:
        return None


def _find_first_identifier(node) -> Optional[str]:
    """Recursively find the first identifier text in a node tree."""
    if node.type == "identifier":
        return node.text.decode("utf-8", errors="replace")
    for child in node.children:
        result = _find_first_identifier(child)
        if result:
            return result
    return None


def _is_valid_identifier(name: str) -> bool:
    """Check if a name is a meaningful identifier (not a keyword/builtin)."""
    if not name or len(name) < 1:
        return False
    # Skip single-character names and Python builtins/keywords
    if name in {
        "self",
        "cls",
        "None",
        "True",
        "False",
        "pass",
        "return",
        "yield",
        "import",
        "from",
        "as",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "raise",
        "break",
        "continue",
        "def",
        "class",
        "and",
        "or",
        "not",
        "is",
        "in",
        "lambda",
        "global",
        "nonlocal",
        "del",
        "assert",
        "async",
        "await",
        # JS/TS keywords
        "var",
        "let",
        "const",
        "function",
        "this",
        "new",
        "typeof",
        "instanceof",
        "void",
        "delete",
        "null",
        "undefined",
        "true",
        "false",
        # Go keywords
        "func",
        "type",
        "struct",
        "interface",
        "package",
        "nil",
        "err",
        # Rust keywords
        "fn",
        "pub",
        "mod",
        "use",
        "impl",
        "trait",
        "enum",
        "mut",
        "ref",
        "let",
        "match",
    }:
        return False
    return True


def _language_for_file(path: str) -> Optional[str]:
    """Determine the tree-sitter language for a file path."""
    ext = Path(path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def _serialize_tags(tags: List[Tag]) -> str:
    """Serialize tags to JSON for cache storage."""
    return json.dumps(
        [
            {
                "r": t.rel_fname,
                "f": t.fname,
                "l": t.line,
                "n": t.name,
                "k": t.kind,
            }
            for t in tags
        ]
    )


def _deserialize_tags(data: str) -> List[Tag]:
    """Deserialize tags from JSON cache."""
    items = json.loads(data)
    return [
        Tag(
            rel_fname=item["r"],
            fname=item["f"],
            line=item["l"],
            name=item["n"],
            kind=item["k"],
        )
        for item in items
    ]
