"""
数据库工具模块

提供安全的数据库查询和操作能力，支持多种数据库：
- SQLite
- PostgreSQL
- MySQL

使用示例:
    from xiaotie.database import DatabaseTool, DatabaseConfig

    # SQLite
    db = DatabaseTool(DatabaseConfig(
        driver="sqlite",
        database="data.db",
    ))

    # PostgreSQL
    db = DatabaseTool(DatabaseConfig(
        driver="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="user",
        password="pass",
    ))

    # 查询
    result = db.query("SELECT * FROM users WHERE id = ?", [1])
    print(result.rows)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union
import sqlite3
import re
import time
from pathlib import Path
from contextlib import contextmanager


class DatabaseDriver(Enum):
    """数据库驱动类型"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class QueryType(Enum):
    """查询类型"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DDL = "ddl"
    OTHER = "other"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    driver: str = "sqlite"
    host: str = "localhost"
    port: int = 5432
    database: str = ":memory:"
    username: Optional[str] = None
    password: Optional[str] = None
    read_only: bool = True  # 默认只读模式
    max_rows: int = 1000  # 最大返回行数
    timeout: float = 30.0  # 查询超时
    pool_size: int = 5  # 连接池大小
    ssl_enabled: bool = False
    ssl_ca: Optional[str] = None

    @property
    def connection_string(self) -> str:
        """生成连接字符串"""
        driver = DatabaseDriver(self.driver)
        if driver == DatabaseDriver.SQLITE:
            return self.database
        elif driver == DatabaseDriver.POSTGRESQL:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"
        elif driver == DatabaseDriver.MYSQL:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"mysql://{auth}{self.host}:{self.port}/{self.database}"
        return ""


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    rows: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    affected_rows: int = 0
    execution_time: float = 0.0
    query_type: QueryType = QueryType.SELECT
    error_message: Optional[str] = None
    truncated: bool = False  # 结果是否被截断

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "rows": self.rows,
            "columns": self.columns,
            "row_count": self.row_count,
            "affected_rows": self.affected_rows,
            "execution_time": self.execution_time,
            "query_type": self.query_type.value,
            "error_message": self.error_message,
            "truncated": self.truncated,
        }


class DatabaseError(Exception):
    """数据库错误基类"""
    pass


class ConnectionError(DatabaseError):
    """连接错误"""
    pass


class QueryError(DatabaseError):
    """查询错误"""
    pass


class SecurityError(DatabaseError):
    """安全错误"""
    pass


class SQLValidator:
    """SQL 验证器"""

    # 始终危险的关键字（即使在可写模式下也禁止）
    ALWAYS_DANGEROUS = [
        "DROP", "TRUNCATE", "GRANT", "REVOKE",
        "EXEC", "EXECUTE", "XP_", "SP_", "SHUTDOWN", "KILL",
    ]

    # 只读模式下额外禁止的关键字
    WRITE_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"]

    # 允许的只读关键字
    READONLY_KEYWORDS = ["SELECT", "WITH", "EXPLAIN", "DESCRIBE", "SHOW", "PRAGMA"]

    def __init__(self, read_only: bool = True):
        self.read_only = read_only

    def validate(self, sql: str) -> Tuple[bool, Optional[str]]:
        """验证 SQL 语句"""
        sql_upper = sql.upper().strip()

        # 检查是否为空
        if not sql_upper:
            return False, "Empty SQL statement"

        # 检查多语句（先检查，避免被其他检查干扰）
        if ";" in sql[:-1]:  # 允许末尾的分号
            return False, "Multiple statements not allowed"

        # 检查注释注入
        if "--" in sql or "/*" in sql:
            return False, "SQL comments not allowed"

        # 检查始终危险的关键字
        for keyword in self.ALWAYS_DANGEROUS:
            if re.search(rf'\b{keyword}\b', sql_upper):
                return False, f"Dangerous keyword detected: {keyword}"

        # 只读模式检查
        if self.read_only:
            # 检查是否以只读关键字开头
            is_readonly = False
            for keyword in self.READONLY_KEYWORDS:
                if sql_upper.startswith(keyword):
                    is_readonly = True
                    break

            if not is_readonly:
                return False, "Only SELECT queries allowed in read-only mode"

        return True, None

    def get_query_type(self, sql: str) -> QueryType:
        """获取查询类型"""
        sql_upper = sql.upper().strip()

        if sql_upper.startswith("SELECT") or sql_upper.startswith("WITH"):
            return QueryType.SELECT
        elif sql_upper.startswith("INSERT"):
            return QueryType.INSERT
        elif sql_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        elif sql_upper.startswith("DELETE"):
            return QueryType.DELETE
        elif any(sql_upper.startswith(k) for k in ["CREATE", "ALTER", "DROP"]):
            return QueryType.DDL
        else:
            return QueryType.OTHER


class SQLiteConnection:
    """SQLite 连接"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self):
        """建立连接"""
        try:
            self._connection = sqlite3.connect(
                self.config.database,
                timeout=self.config.timeout,
            )
            self._connection.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect: {e}")

    def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    def execute(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        """执行查询"""
        if not self._connection:
            raise ConnectionError("Not connected")

        start_time = time.time()
        params = params or []

        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)

            # 获取查询类型
            validator = SQLValidator()
            query_type = validator.get_query_type(sql)

            # 如果有结果集（SELECT, PRAGMA, SHOW 等），获取结果
            if cursor.description:
                # 获取列名
                columns = [desc[0] for desc in cursor.description]

                # 获取结果
                rows = []
                truncated = False
                for i, row in enumerate(cursor):
                    if i >= self.config.max_rows:
                        truncated = True
                        break
                    rows.append(dict(row))

                return QueryResult(
                    success=True,
                    rows=rows,
                    columns=columns,
                    row_count=len(rows),
                    execution_time=time.time() - start_time,
                    query_type=query_type,
                    truncated=truncated,
                )
            else:
                # 非 SELECT 查询
                self._connection.commit()
                return QueryResult(
                    success=True,
                    affected_rows=cursor.rowcount,
                    execution_time=time.time() - start_time,
                    query_type=query_type,
                )

        except sqlite3.Error as e:
            return QueryResult(
                success=False,
                execution_time=time.time() - start_time,
                error_message=str(e),
            )


class DatabaseTool:
    """数据库工具"""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._validator = SQLValidator(read_only=self.config.read_only)
        self._connection = self._create_connection()
        self._connected = False

    def _create_connection(self):
        """创建连接"""
        driver = DatabaseDriver(self.config.driver)
        if driver == DatabaseDriver.SQLITE:
            return SQLiteConnection(self.config)
        else:
            raise NotImplementedError(f"Driver {driver.value} not implemented yet")

    def connect(self) -> "DatabaseTool":
        """建立连接"""
        self._connection.connect()
        self._connected = True
        return self

    def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._connection.is_connected

    @contextmanager
    def session(self):
        """上下文管理器"""
        self.connect()
        try:
            yield self
        finally:
            self.close()

    def query(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        """执行查询"""
        # 验证 SQL
        valid, error = self._validator.validate(sql)
        if not valid:
            return QueryResult(
                success=False,
                error_message=error,
            )

        # 确保已连接
        if not self.is_connected:
            self.connect()

        # 执行查询
        return self._connection.execute(sql, params)

    def execute(self, sql: str, params: Optional[List[Any]] = None) -> QueryResult:
        """执行语句（别名）"""
        return self.query(sql, params)

    def get_tables(self) -> QueryResult:
        """获取所有表"""
        driver = DatabaseDriver(self.config.driver)
        if driver == DatabaseDriver.SQLITE:
            return self.query(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        elif driver == DatabaseDriver.POSTGRESQL:
            return self.query(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        elif driver == DatabaseDriver.MYSQL:
            return self.query("SHOW TABLES")
        return QueryResult(success=False, error_message="Unknown driver")

    def get_columns(self, table: str) -> QueryResult:
        """获取表的列信息"""
        # 验证表名（防止注入）
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            return QueryResult(
                success=False,
                error_message="Invalid table name",
            )

        driver = DatabaseDriver(self.config.driver)
        if driver == DatabaseDriver.SQLITE:
            return self.query(f"PRAGMA table_info({table})")
        elif driver == DatabaseDriver.POSTGRESQL:
            return self.query(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = ?",
                [table]
            )
        return QueryResult(success=False, error_message="Unknown driver")

    def count(self, table: str, where: Optional[str] = None) -> int:
        """统计行数"""
        # 验证表名
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            return 0

        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            # 简单验证 where 子句
            valid, _ = self._validator.validate(f"SELECT * FROM t WHERE {where}")
            if valid:
                sql += f" WHERE {where}"

        result = self.query(sql)
        if result.success and result.rows:
            return result.rows[0].get("cnt", 0)
        return 0


class QueryBuilder:
    """查询构建器"""

    def __init__(self, table: str):
        self._table = table
        self._columns: List[str] = ["*"]
        self._where: List[str] = []
        self._params: List[Any] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def select(self, *columns: str) -> "QueryBuilder":
        """选择列"""
        self._columns = list(columns) if columns else ["*"]
        return self

    def where(self, condition: str, *params: Any) -> "QueryBuilder":
        """添加条件"""
        self._where.append(condition)
        self._params.extend(params)
        return self

    def order_by(self, column: str, desc: bool = False) -> "QueryBuilder":
        """排序"""
        direction = "DESC" if desc else "ASC"
        self._order_by = f"{column} {direction}"
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """限制数量"""
        self._limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """偏移量"""
        self._offset = offset
        return self

    def build(self) -> Tuple[str, List[Any]]:
        """构建 SQL"""
        columns = ", ".join(self._columns)
        sql = f"SELECT {columns} FROM {self._table}"

        if self._where:
            sql += " WHERE " + " AND ".join(self._where)

        if self._order_by:
            sql += f" ORDER BY {self._order_by}"

        if self._limit is not None:
            sql += f" LIMIT {self._limit}"

        if self._offset is not None:
            sql += f" OFFSET {self._offset}"

        return sql, self._params

    def execute(self, db: DatabaseTool) -> QueryResult:
        """执行查询"""
        sql, params = self.build()
        return db.query(sql, params)


def query(table: str) -> QueryBuilder:
    """创建查询构建器的快捷方式"""
    return QueryBuilder(table)
