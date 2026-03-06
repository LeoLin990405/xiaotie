# API Reference

小铁 v2.0 核心模块 API 参考。

---

## AgentRuntime

`xiaotie.agent.runtime.AgentRuntime`

状态机驱动的 Agent 运行时，组合 ToolExecutor 和 ResponseHandler。

```python
class AgentRuntime:
    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[Tool],
        config: Optional[AgentConfig] = None,
        workspace_dir: str = ".",
        session_id: Optional[str] = None,
    ): ...
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `await run(prompt: str) -> str` | 运行完整 Agent 循环，返回最终响应 |
| `await step(prompt: str = None) -> (RuntimeState, str)` | 单步执行，用于外部控制 |
| `reset()` | 重置运行时状态和消息历史 |
| `get_stats() -> dict` | 获取运行时统计 (steps, tool_calls, tokens 等) |
| `set_context_engine(engine)` | 集成 ContextEngine |
| `set_repomap_engine(engine)` | 集成 RepoMapEngine |

### RuntimeState 枚举

```python
class RuntimeState(Enum):
    IDLE = "idle"
    THINKING = "thinking"      # 等待 LLM 响应
    ACTING = "acting"          # 执行工具调用
    OBSERVING = "observing"    # 处理工具结果
    REFLECTING = "reflecting"  # 检查是否继续
```

### 用法示例

```python
from xiaotie.agent.runtime import AgentRuntime
from xiaotie.llm import LLMClient
from xiaotie.tools import ReadTool, BashTool

runtime = AgentRuntime(
    llm_client=LLMClient(api_key="...", model="claude-sonnet-4-20250514", provider="anthropic"),
    system_prompt="你是小铁",
    tools=[ReadTool(workspace_dir="."), BashTool()],
)
result = await runtime.run("列出当前目录文件")
```

---

## ToolExecutor

`xiaotie.agent.executor.ToolExecutor`

工具执行器，负责查找、权限检查、执行和结果处理。

```python
class ToolExecutor:
    def __init__(
        self,
        tools: dict[str, Tool],
        permission_manager: PermissionManager,
        telemetry: AgentTelemetry,
        session_id: str,
        quiet: bool = False,
    ): ...
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `await execute(tool_calls, parallel=True) -> list[ToolResult]` | 执行一批工具调用 |

### ToolResult

```python
@dataclass
class ToolResult:
    tool_call_id: str
    function_name: str
    content: str
    success: bool = True
    elapsed: float = 0.0
```

---

## ResponseHandler

`xiaotie.agent.response.ResponseHandler`

LLM 响应处理器，统一流式/非流式处理，管理 Token 预算。

```python
class ResponseHandler:
    def __init__(
        self,
        llm: LLMClient,
        telemetry: AgentTelemetry,
        session_id: str,
        token_limit: int = 100000,
        summary_threshold: float = 0.8,
        summary_keep_recent: int = 5,
        enable_thinking: bool = True,
        quiet: bool = False,
    ): ...
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `await generate(messages, tool_schemas, stream=True) -> LLMResponse` | 生成 LLM 响应 |
| `await maybe_summarize(messages) -> list[Message]` | Token 超阈值时自动摘要历史 |
| `estimate_tokens(messages) -> int` | 增量估算消息 Token 数 |

### 回调

```python
handler.on_thinking = lambda text: print(f"[思考] {text}")
handler.on_content = lambda text: print(text, end="")
```

---

## ContextEngine

`xiaotie.context_engine.ContextEngine`

Token 预算上下文组装器，将多源上下文按优先级分配到 Token 预算内。

```python
class ContextEngine:
    def __init__(
        self,
        token_budget: int = 100_000,
        ratios: Optional[dict[str, float]] = None,  # 默认: system 10%, conversation 50%, ...
    ): ...
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `await compose_context(query, conversation, repo_map, memory_chunks, ...) -> ContextBundle` | 组装上下文 |
| `await compact(conversation, target_tokens) -> list[Message]` | 压缩对话历史 |
| `set_budget(max_tokens)` | 设置 Token 预算 |

### ContextBundle

```python
@dataclass
class ContextBundle:
    blocks: list[ContextBlock]
    token_usage: TokenBudget

    def to_messages(self, system_prompt: str) -> list[Message]:
        """转换为 LLM 消息列表，非会话块合并到 system prompt"""
```

### 优先级

```python
class BlockPriority(IntEnum):
    SYSTEM = 100              # 最高，始终保留
    CONVERSATION_RECENT = 80  # 最近对话
    REPO_MAP = 60             # 代码映射
    MEMORY = 50               # 记忆
    CONVERSATION_OLD = 40     # 旧对话
    SKILLS = 30               # 技能元数据
```

### 用法示例

```python
from xiaotie.context_engine import ContextEngine

engine = ContextEngine(token_budget=100_000)
bundle = await engine.compose_context(
    query="implement auth",
    conversation=messages,
    repo_map="src/auth.py: class AuthService ...",
    system_prompt="你是小铁",
)
final_messages = bundle.to_messages(system_prompt="你是小铁")
```

---

## RepoMapEngine

`xiaotie.repomap_v2.RepoMapEngine`

tree-sitter AST + PageRank 代码导航引擎。

```python
class RepoMapEngine:
    def __init__(
        self,
        workspace_dir: str,
        cache_dir: Optional[str] = None,
        ignore_patterns: Optional[set[str]] = None,
        max_file_size: int = 100_000,
    ): ...
```

### 支持语言

Python, JavaScript, TypeScript, Go, Rust, Java, C, C++

### 主要方法

| 方法 | 说明 |
|------|------|
| `get_ranked_map(chat_files, other_files, max_tokens) -> str` | 生成 PageRank 排序的代码映射 |
| `get_tags(fname) -> list[Tag]` | 提取文件的所有标签 |
| `get_definitions(rel_path) -> list[Tag]` | 获取文件的定义标签 |
| `get_stats() -> dict` | 扫描统计 (文件数/定义数/引用数/语言) |
| `invalidate_cache(fnames)` | 失效标签缓存 |
| `close()` | 释放资源 |

### Tag

```python
@dataclass(frozen=True)
class Tag:
    rel_fname: str  # 相对路径
    fname: str      # 绝对路径
    line: int       # 行号
    name: str       # 标识符名称
    kind: str       # "def" 或 "ref"
```

### 用法示例

```python
from xiaotie.repomap_v2 import RepoMapEngine

engine = RepoMapEngine("/path/to/project")
repo_map = engine.get_ranked_map(
    chat_files=["src/main.py"],
    max_tokens=2048,
)
print(repo_map)
# 输出:
# src/auth.py:
#   AuthService (L15)
#   login (L42)
# src/models.py:
#   User (L8)
```

---

## SandboxManager

`xiaotie.sandbox_v2.SandboxManager`

OS 级沙箱管理器，自动选择最佳后端。

```python
@dataclass
class SandboxManager:
    workspace: str
    enabled: bool = True
    preferred_backend: str | None = None  # "seatbelt", "bubblewrap", "fallback"
```

### Capability 标志

```python
class Capability(Flag):
    NONE = 0
    READ_FS = auto()       # 读取工作区文件
    WRITE_FS = auto()      # 写入工作区文件
    NETWORK = auto()       # 网络访问
    SUBPROCESS = auto()    # 子进程
    DANGEROUS = auto()     # 系统级操作
    READ_WRITE = READ_FS | WRITE_FS
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `await execute(command, capabilities, timeout, env, extra_read_paths) -> SandboxResult` | 沙箱内执行命令 |
| `await execute_shell(shell_command, ...) -> SandboxResult` | 执行 shell 命令字符串 |
| `get_capabilities_for_tool(tool_name) -> Capability` | 查询工具默认权限 |

### SandboxResult

```python
@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    backend: str      # "seatbelt" / "bubblewrap" / "fallback"
    sandboxed: bool   # 是否真正应用了 OS 沙箱
```

### 用法示例

```python
from xiaotie.sandbox_v2 import SandboxManager, Capability

manager = SandboxManager(workspace="/path/to/project")
result = await manager.execute(
    command=["python", "script.py"],
    capabilities=Capability.READ_FS | Capability.SUBPROCESS,
    timeout=30.0,
)
print(result.stdout)
```

---

## SecretManager

`xiaotie.secrets.SecretManager`

分层密钥管理器，解析优先级: keyring -> 环境变量 -> 配置明文。

```python
class SecretManager:
    SERVICE_NAME = "xiaotie"
```

### 主要方法

| 方法 | 说明 |
|------|------|
| `get(key) -> Optional[str]` | 按优先级获取密钥 |
| `set(key, value, backend="keyring") -> bool` | 存储密钥 |
| `delete(key) -> bool` | 删除密钥 |
| `list_keys() -> list[dict]` | 列出已知密钥及来源 |
| `resolve_config(config: dict) -> dict` | 解析配置中的 `${secret:...}` 和 `${env:...}` |
| `migrate_config(config_path) -> list[str]` | 迁移明文密钥到 keyring |

### 全局实例

```python
from xiaotie.secrets import get_secret_manager

sm = get_secret_manager()
sm.set("api_key", "sk-xxx")
value = sm.get("api_key")
```

### 配置占位符语法

```yaml
# ${secret:key_name} - 从 keyring/环境变量解析
api_key: ${secret:api_key}

# ${env:VAR_NAME} - 仅从环境变量解析
home: ${env:HOME}
```
