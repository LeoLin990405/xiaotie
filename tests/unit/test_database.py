"""
数据库工具测试
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from xiaotie.database import (
    DatabaseTool,
    DatabaseConfig,
    DatabaseDriver,
    QueryType,
    QueryResult,
    SQLValidator,
    SQLiteConnection,
    QueryBuilder,
    query,
    DatabaseError,
    ConnectionError,
    QueryError,
    SecurityError,
)


class TestDatabaseConfig:
    """测试数据库配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = DatabaseConfig()
        assert config.driver == "sqlite"
        assert config.database == ":memory:"
        assert config.read_only is True
        assert config.max_rows == 1000

    def test_custom_config(self):
        """测试自定义配置"""
        config = DatabaseConfig(
            driver="postgresql",
            host="db.example.com",
            port=5433,
            database="mydb",
            username="user",
            password="pass",
            read_only=False,
        )
        assert config.driver == "postgresql"
        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.read_only is False

    def test_connection_string_sqlite(self):
        """测试 SQLite 连接字符串"""
        config = DatabaseConfig(driver="sqlite", database="test.db")
        assert config.connection_string == "test.db"

    def test_connection_string_postgresql(self):
        """测试 PostgreSQL 连接字符串"""
        config = DatabaseConfig(
            driver="postgresql",
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password="pass",
        )
        assert "postgresql://" in config.connection_string
        assert "user:pass@" in config.connection_string


class TestQueryResult:
    """测试查询结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = QueryResult(
            success=True,
            rows=[{"id": 1, "name": "test"}],
            columns=["id", "name"],
            row_count=1,
        )
        assert result.success is True
        assert len(result.rows) == 1

    def test_error_result(self):
        """测试错误结果"""
        result = QueryResult(
            success=False,
            error_message="Table not found",
        )
        assert result.success is False
        assert result.error_message == "Table not found"

    def test_to_dict(self):
        """测试转换为字典"""
        result = QueryResult(
            success=True,
            rows=[{"id": 1}],
            row_count=1,
            query_type=QueryType.SELECT,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["query_type"] == "select"


class TestSQLValidator:
    """测试 SQL 验证器"""

    def test_valid_select(self):
        """测试有效的 SELECT"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("SELECT * FROM users")
        assert valid is True
        assert error is None

    def test_valid_select_with_where(self):
        """测试带 WHERE 的 SELECT"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("SELECT * FROM users WHERE id = 1")
        assert valid is True

    def test_invalid_drop(self):
        """测试 DROP 语句"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("DROP TABLE users")
        assert valid is False
        assert "Dangerous keyword" in error

    def test_invalid_truncate(self):
        """测试 TRUNCATE 语句"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("TRUNCATE TABLE users")
        assert valid is False

    def test_readonly_insert(self):
        """测试只读模式下的 INSERT"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("INSERT INTO users VALUES (1, 'test')")
        assert valid is False
        assert "read-only" in error

    def test_writable_insert(self):
        """测试可写模式下的 INSERT"""
        validator = SQLValidator(read_only=False)
        valid, error = validator.validate("INSERT INTO users VALUES (1, 'test')")
        assert valid is True

    def test_sql_comment_injection(self):
        """测试 SQL 注释注入"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("SELECT * FROM users -- WHERE admin=1")
        assert valid is False
        assert "comments" in error

    def test_multiple_statements(self):
        """测试多语句"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("SELECT 1; SELECT 2")
        assert valid is False
        assert "Multiple statements" in error

    def test_empty_sql(self):
        """测试空 SQL"""
        validator = SQLValidator(read_only=True)
        valid, error = validator.validate("")
        assert valid is False

    def test_get_query_type(self):
        """测试获取查询类型"""
        validator = SQLValidator()
        assert validator.get_query_type("SELECT * FROM t") == QueryType.SELECT
        assert validator.get_query_type("INSERT INTO t VALUES (1)") == QueryType.INSERT
        assert validator.get_query_type("UPDATE t SET x=1") == QueryType.UPDATE
        assert validator.get_query_type("DELETE FROM t") == QueryType.DELETE
        assert validator.get_query_type("CREATE TABLE t (id INT)") == QueryType.DDL


class TestSQLiteConnection:
    """测试 SQLite 连接"""

    def test_connect_memory(self):
        """测试内存数据库连接"""
        config = DatabaseConfig(driver="sqlite", database=":memory:")
        conn = SQLiteConnection(config)
        conn.connect()
        assert conn.is_connected is True
        conn.close()
        assert conn.is_connected is False

    def test_connect_file(self, tmp_path):
        """测试文件数据库连接"""
        db_file = tmp_path / "test.db"
        config = DatabaseConfig(driver="sqlite", database=str(db_file))
        conn = SQLiteConnection(config)
        conn.connect()
        assert conn.is_connected is True
        conn.close()

    def test_execute_select(self):
        """测试执行 SELECT"""
        config = DatabaseConfig(driver="sqlite", database=":memory:")
        conn = SQLiteConnection(config)
        conn.connect()

        # 创建表
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice')")
        conn.execute("INSERT INTO test VALUES (2, 'Bob')")

        # 查询
        result = conn.execute("SELECT * FROM test ORDER BY id")
        assert result.success is True
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "Alice"

        conn.close()

    def test_execute_with_params(self):
        """测试带参数的执行"""
        config = DatabaseConfig(driver="sqlite", database=":memory:")
        conn = SQLiteConnection(config)
        conn.connect()

        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (?, ?)", [1, "Alice"])

        result = conn.execute("SELECT * FROM test WHERE id = ?", [1])
        assert result.success is True
        assert result.rows[0]["name"] == "Alice"

        conn.close()

    def test_max_rows_limit(self):
        """测试最大行数限制"""
        config = DatabaseConfig(driver="sqlite", database=":memory:", max_rows=5)
        conn = SQLiteConnection(config)
        conn.connect()

        conn.execute("CREATE TABLE test (id INTEGER)")
        for i in range(10):
            conn.execute("INSERT INTO test VALUES (?)", [i])

        result = conn.execute("SELECT * FROM test")
        assert result.success is True
        assert len(result.rows) == 5
        assert result.truncated is True

        conn.close()


class TestDatabaseTool:
    """测试数据库工具"""

    @pytest.fixture
    def db(self):
        """创建测试数据库"""
        config = DatabaseConfig(
            driver="sqlite",
            database=":memory:",
            read_only=False,
        )
        db = DatabaseTool(config)
        db.connect()

        # 创建测试表
        db.query("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        db.query("INSERT INTO users VALUES (1, 'Alice', 30)")
        db.query("INSERT INTO users VALUES (2, 'Bob', 25)")
        db.query("INSERT INTO users VALUES (3, 'Charlie', 35)")

        yield db
        db.close()

    def test_create_tool(self):
        """测试创建工具"""
        db = DatabaseTool()
        assert db.config is not None
        assert db.config.driver == "sqlite"

    def test_connect_close(self):
        """测试连接和关闭"""
        db = DatabaseTool()
        db.connect()
        assert db.is_connected is True
        db.close()
        assert db.is_connected is False

    def test_session_context(self):
        """测试上下文管理器"""
        db = DatabaseTool()
        with db.session():
            assert db.is_connected is True
        assert db.is_connected is False

    def test_query_select(self, db):
        """测试 SELECT 查询"""
        result = db.query("SELECT * FROM users ORDER BY id")
        assert result.success is True
        assert len(result.rows) == 3
        assert result.rows[0]["name"] == "Alice"

    def test_query_with_params(self, db):
        """测试带参数的查询"""
        result = db.query("SELECT * FROM users WHERE age > ?", [28])
        assert result.success is True
        assert len(result.rows) == 2

    def test_query_readonly_violation(self):
        """测试只读模式违规"""
        config = DatabaseConfig(driver="sqlite", database=":memory:", read_only=True)
        db = DatabaseTool(config)
        db.connect()

        result = db.query("INSERT INTO test VALUES (1)")
        assert result.success is False
        assert "read-only" in result.error_message

        db.close()

    def test_query_dangerous_sql(self, db):
        """测试危险 SQL"""
        result = db.query("DROP TABLE users")
        assert result.success is False
        assert "Dangerous" in result.error_message

    def test_get_tables(self, db):
        """测试获取表列表"""
        result = db.get_tables()
        assert result.success is True
        table_names = [row["name"] for row in result.rows]
        assert "users" in table_names

    def test_get_columns(self, db):
        """测试获取列信息"""
        result = db.get_columns("users")
        assert result.success is True
        assert len(result.rows) == 3  # id, name, age

    def test_get_columns_invalid_table(self, db):
        """测试无效表名"""
        result = db.get_columns("users; DROP TABLE users")
        assert result.success is False
        assert "Invalid table name" in result.error_message

    def test_count(self, db):
        """测试统计行数"""
        count = db.count("users")
        assert count == 3

    def test_count_with_where(self, db):
        """测试带条件的统计"""
        count = db.count("users", "age > 28")
        assert count == 2


class TestQueryBuilder:
    """测试查询构建器"""

    def test_simple_select(self):
        """测试简单 SELECT"""
        sql, params = QueryBuilder("users").build()
        assert sql == "SELECT * FROM users"
        assert params == []

    def test_select_columns(self):
        """测试选择列"""
        sql, params = QueryBuilder("users").select("id", "name").build()
        assert sql == "SELECT id, name FROM users"

    def test_where(self):
        """测试 WHERE"""
        sql, params = QueryBuilder("users").where("id = ?", 1).build()
        assert "WHERE id = ?" in sql
        assert params == [1]

    def test_multiple_where(self):
        """测试多个 WHERE"""
        sql, params = (
            QueryBuilder("users")
            .where("age > ?", 20)
            .where("name LIKE ?", "A%")
            .build()
        )
        assert "WHERE age > ? AND name LIKE ?" in sql
        assert params == [20, "A%"]

    def test_order_by(self):
        """测试 ORDER BY"""
        sql, params = QueryBuilder("users").order_by("name").build()
        assert "ORDER BY name ASC" in sql

    def test_order_by_desc(self):
        """测试 ORDER BY DESC"""
        sql, params = QueryBuilder("users").order_by("age", desc=True).build()
        assert "ORDER BY age DESC" in sql

    def test_limit(self):
        """测试 LIMIT"""
        sql, params = QueryBuilder("users").limit(10).build()
        assert "LIMIT 10" in sql

    def test_offset(self):
        """测试 OFFSET"""
        sql, params = QueryBuilder("users").limit(10).offset(20).build()
        assert "LIMIT 10" in sql
        assert "OFFSET 20" in sql

    def test_full_query(self):
        """测试完整查询"""
        sql, params = (
            QueryBuilder("users")
            .select("id", "name", "age")
            .where("age > ?", 18)
            .where("name IS NOT NULL")
            .order_by("age", desc=True)
            .limit(10)
            .offset(0)
            .build()
        )
        assert "SELECT id, name, age FROM users" in sql
        assert "WHERE age > ? AND name IS NOT NULL" in sql
        assert "ORDER BY age DESC" in sql
        assert "LIMIT 10" in sql
        assert params == [18]

    def test_execute(self):
        """测试执行"""
        config = DatabaseConfig(driver="sqlite", database=":memory:", read_only=False)
        db = DatabaseTool(config)
        db.connect()

        db.query("CREATE TABLE users (id INTEGER, name TEXT)")
        db.query("INSERT INTO users VALUES (1, 'Alice')")
        db.query("INSERT INTO users VALUES (2, 'Bob')")

        result = QueryBuilder("users").where("id = ?", 1).execute(db)
        assert result.success is True
        assert result.rows[0]["name"] == "Alice"

        db.close()


class TestQueryShortcut:
    """测试查询快捷方式"""

    def test_query_function(self):
        """测试 query 函数"""
        builder = query("users")
        assert isinstance(builder, QueryBuilder)

    def test_query_chain(self):
        """测试链式调用"""
        sql, params = (
            query("users")
            .select("name")
            .where("id = ?", 1)
            .build()
        )
        assert "SELECT name FROM users" in sql
        assert "WHERE id = ?" in sql


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        config = DatabaseConfig(
            driver="sqlite",
            database=":memory:",
            read_only=False,
            max_rows=100,
        )

        with DatabaseTool(config).session() as db:
            # 创建表
            db.query("""
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    price REAL,
                    stock INTEGER
                )
            """)

            # 插入数据
            products = [
                (1, "Apple", 1.5, 100),
                (2, "Banana", 0.5, 200),
                (3, "Orange", 2.0, 50),
            ]
            for p in products:
                db.query("INSERT INTO products VALUES (?, ?, ?, ?)", list(p))

            # 查询
            result = db.query("SELECT * FROM products WHERE price < ?", [2.0])
            assert result.success is True
            assert len(result.rows) == 2

            # 使用构建器
            result = (
                query("products")
                .select("name", "price")
                .where("stock > ?", 60)
                .order_by("price")
                .execute(db)
            )
            assert result.success is True
            assert len(result.rows) == 2

    def test_error_recovery(self):
        """测试错误恢复"""
        db = DatabaseTool()
        db.connect()

        # 查询不存在的表
        result = db.query("SELECT * FROM nonexistent")
        assert result.success is False
        assert result.error_message is not None

        # 仍然可以执行其他查询
        result = db.query("SELECT 1 as num")
        assert result.success is True

        db.close()
