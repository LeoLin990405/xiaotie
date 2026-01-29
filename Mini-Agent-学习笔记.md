# Mini-Agent 学习笔记

基于用户选择的三个学习领域：**Agent执行循环**、**工具系统设计**、**LLM客户端封装**

---

## 1. Agent 执行循环 (Agent Execution Loop)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/agent.py`

### 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent.run() 主循环                        │
├─────────────────────────────────────────────────────────────┤
│  while step < max_steps:                                    │
│    ├── 1. 检查取消事件 (_check_cancelled)                    │
│    ├── 2. Token 检查与消息摘要 (_summarize_messages)         │
│    ├── 3. 调用 LLM 生成响应 (llm.generate)                   │
│    ├── 4. 解析响应 (content, thinking, tool_calls)          │
│    ├── 5. 如果无 tool_calls → 任务完成，返回                 │
│    └── 6. 执行工具调用 → 添加结果到消息历史 → 继续循环        │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计模式

#### 1.1 消息历史管理
```python
# agent.py:76
self.messages: list[Message] = [Message(role="system", content=system_prompt)]
```
- 使用 `Message` 对象列表维护完整对话历史
- 支持 system/user/assistant/tool 四种角色
- Message 定义见 `schema/schema.py:29-37`

#### 1.2 取消机制 (Graceful Cancellation)
```python
# agent.py:63
self.cancel_event: Optional[asyncio.Event] = None

# agent.py:90-98
def _check_cancelled(self) -> bool:
    if self.cancel_event is not None and self.cancel_event.is_set():
        return True
    return False
```
- 在每个步骤开始 (agent.py:345) 和工具执行后 (agent.py:504) 检查
- 取消时清理未完成的消息 (`_cleanup_incomplete_messages`, agent.py:100-121)
- 清理逻辑：找到最后一个 assistant 消息，删除它及其后的所有 tool 结果

#### 1.3 Token 管理与自动摘要
```python
# agent.py:180-260
async def _summarize_messages(self):
    estimated_tokens = self._estimate_tokens()
    # 双重检查：本地估算 OR API 返回的 token 数
    if estimated_tokens > self.token_limit or self.api_total_tokens > self.token_limit:
        # 触发摘要
```
- 使用 tiktoken (`cl100k_base` 编码器) 精确计算 token 数 (agent.py:123-158)
- 摘要策略：保留所有 user 消息，摘要每轮 agent 执行过程
- 结构：`system -> user1 -> summary1 -> user2 -> summary2 -> ...`

#### 1.4 工具执行循环
```python
# agent.py:431-501
for tool_call in response.tool_calls:
    tool_call_id = tool_call.id
    function_name = tool_call.function.name
    arguments = tool_call.function.arguments

    tool = self.tools[function_name]
    result = await tool.execute(**arguments)

    tool_msg = Message(
        role="tool",
        content=result.content if result.success else f"Error: {result.error}",
        tool_call_id=tool_call_id,
        name=function_name,
    )
    self.messages.append(tool_msg)
```

---

## 2. 工具系统设计 (Tool System Design)

### 核心文件
- `~/Desktop/github/Mini-Agent/mini_agent/tools/base.py` - 基类定义
- `~/Desktop/github/Mini-Agent/mini_agent/tools/file_tools.py` - 具体实现

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Tool (抽象基类)                         │
├─────────────────────────────────────────────────────────────┤
│  @property name: str          # 工具名称                     │
│  @property description: str   # 工具描述                     │
│  @property parameters: dict   # JSON Schema 参数定义         │
│  async execute(**kwargs)      # 异步执行方法                 │
│  to_schema() -> dict          # 转换为 Anthropic 格式        │
│  to_openai_schema() -> dict   # 转换为 OpenAI 格式           │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐       ┌──────────┐       ┌──────────┐
    │ ReadTool │       │ WriteTool│       │ EditTool │
    └──────────┘       └──────────┘       └──────────┘
```

### 关键设计模式

#### 2.1 统一结果类型
```python
# base.py:8-13
class ToolResult(BaseModel):
    success: bool
    content: str = ""
    error: str | None = None
```
- 所有工具返回统一的 `ToolResult`
- 明确区分成功/失败状态
- Agent 根据 `success` 字段决定如何构造 tool message

#### 2.2 多协议 Schema 转换
```python
# base.py:38-55
def to_schema(self) -> dict[str, Any]:
    """Anthropic 格式"""
    return {
        "name": self.name,
        "description": self.description,
        "input_schema": self.parameters,  # Anthropic 用 input_schema
    }

def to_openai_schema(self) -> dict[str, Any]:
    """OpenAI 格式"""
    return {
        "type": "function",
        "function": {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,  # OpenAI 用 parameters
        },
    }
```

#### 2.3 工作目录注入
```python
# file_tools.py:66-72, 108-114
class ReadTool(Tool):
    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir).absolute()

    async def execute(self, path: str, ...):
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_dir / file_path  # 相对路径解析
```
- 工具实例化时注入工作目录
- 支持相对路径自动解析为绝对路径

#### 2.4 Token 截断保护
```python
# file_tools.py:11-60
def truncate_text_by_tokens(text: str, max_tokens: int) -> str:
    """智能截断：保留头尾，截断中间"""
    encoding = tiktoken.get_encoding("cl100k_base")
    token_count = len(encoding.encode(text))

    if token_count <= max_tokens:
        return text

    # 计算 token/字符 比例
    ratio = token_count / len(text)
    chars_per_half = int((max_tokens / 2) / ratio * 0.95)  # 5% 安全边际

    # 保留前半部分（找最近换行符）
    head_part = text[:chars_per_half]
    last_newline_head = head_part.rfind("\n")
    if last_newline_head > 0:
        head_part = head_part[:last_newline_head]

    # 保留后半部分（找最近换行符）
    tail_part = text[-chars_per_half:]
    first_newline_tail = tail_part.find("\n")
    if first_newline_tail > 0:
        tail_part = tail_part[first_newline_tail + 1:]

    truncation_note = f"\n\n... [Content truncated: {token_count} tokens -> ~{max_tokens} tokens limit] ...\n\n"
    return head_part + truncation_note + tail_part
```

---

## 3. LLM 客户端封装 (LLM Client Wrapper)

### 核心文件
- `~/Desktop/github/Mini-Agent/mini_agent/llm/base.py` - 抽象基类
- `~/Desktop/github/Mini-Agent/mini_agent/llm/llm_wrapper.py` - 统一包装器
- `~/Desktop/github/Mini-Agent/mini_agent/llm/anthropic_client.py` - Anthropic 实现
- `~/Desktop/github/Mini-Agent/mini_agent/retry.py` - 重试机制

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    LLMClient (统一入口)                      │
├─────────────────────────────────────────────────────────────┤
│  - 根据 provider 参数自动选择底层客户端                       │
│  - 处理 MiniMax API 的特殊 URL 后缀                          │
│  - 统一的 generate() 接口                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLMClientBase (抽象基类)                    │
├─────────────────────────────────────────────────────────────┤
│  @abstractmethod generate()           # 生成响应             │
│  @abstractmethod _prepare_request()   # 准备请求             │
│  @abstractmethod _convert_messages()  # 消息格式转换         │
└─────────────────────────────────────────────────────────────┘
          │                                       │
          ▼                                       ▼
┌──────────────────────┐              ┌──────────────────────┐
│   AnthropicClient    │              │    OpenAIClient      │
├──────────────────────┤              ├──────────────────────┤
│ - Anthropic SDK      │              │ - OpenAI SDK         │
│ - thinking 支持      │              │ - 标准 function call │
│ - tool_use 格式      │              │ - tool_calls 格式    │
└──────────────────────┘              └──────────────────────┘
```

### 关键设计模式

#### 3.1 策略模式 (Strategy Pattern)
```python
# llm_wrapper.py:82-99
class LLMClient:
    def __init__(self, provider: LLMProvider = LLMProvider.ANTHROPIC, ...):
        self._client: LLMClientBase
        if provider == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(...)
        elif provider == LLMProvider.OPENAI:
            self._client = OpenAIClient(...)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def generate(self, messages, tools) -> LLMResponse:
        return await self._client.generate(messages, tools)
```

#### 3.2 统一响应模型
```python
# schema/schema.py:48-55
class LLMResponse(BaseModel):
    content: str
    thinking: str | None = None      # 扩展思考 (Anthropic 特有)
    tool_calls: list[ToolCall] | None = None
    finish_reason: str
    usage: TokenUsage | None = None

# schema/schema.py:40-45
class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
```

#### 3.3 重试机制 (Decorator Pattern)
```python
# retry.py:23-61
class RetryConfig:
    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0  # 指数退避
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,)

    def calculate_delay(self, attempt: int) -> float:
        """指数退避计算"""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)

# retry.py:73-138
def async_retry(config: RetryConfig, on_retry: Callable = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    if attempt >= config.max_retries:
                        raise RetryExhaustedError(e, attempt + 1)
                    delay = config.calculate_delay(attempt)
                    if on_retry:
                        on_retry(e, attempt + 1)
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
```

#### 3.4 消息格式转换 (Anthropic)
```python
# anthropic_client.py:114-178
def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
    """将内部 Message 格式转换为 Anthropic API 格式"""
    system_message = None
    api_messages = []

    for msg in messages:
        if msg.role == "system":
            system_message = msg.content  # Anthropic: system 单独提取
            continue

        if msg.role == "assistant" and (msg.thinking or msg.tool_calls):
            # 构建 content blocks
            content_blocks = []
            if msg.thinking:
                content_blocks.append({"type": "thinking", "thinking": msg.thinking})
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": tc.function.arguments,
                    })
            api_messages.append({"role": "assistant", "content": content_blocks})

        elif msg.role == "tool":
            # Anthropic: tool 结果用 user role + tool_result content block
            api_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                }]
            })
```

#### 3.5 MiniMax API 特殊处理
```python
# llm_wrapper.py:64-78
MINIMAX_DOMAINS = ("api.minimax.io", "api.minimaxi.com")

is_minimax = any(domain in api_base for domain in self.MINIMAX_DOMAINS)

if is_minimax:
    # 根据 provider 自动添加正确的 URL 后缀
    api_base = api_base.replace("/anthropic", "").replace("/v1", "")
    if provider == LLMProvider.ANTHROPIC:
        full_api_base = f"{api_base}/anthropic"
    elif provider == LLMProvider.OPENAI:
        full_api_base = f"{api_base}/v1"
else:
    # 第三方 API 直接使用
    full_api_base = api_base
```

---

## 设计亮点总结

| 领域 | 设计模式 | 优点 |
|------|----------|------|
| Agent 循环 | 状态机 + 事件驱动 | 可中断、可恢复、可追踪 |
| 工具系统 | 模板方法 + 策略模式 | 易扩展、多协议支持 |
| LLM 客户端 | 策略模式 + 装饰器 | 多 Provider 统一接口、自动重试 |

## 可借鉴的实践

1. **Token 管理**: 使用 tiktoken 精确计算 + 自动摘要 (agent.py:123-260)
2. **优雅取消**: asyncio.Event + 消息清理 (agent.py:90-121)
3. **统一结果类型**: ToolResult 封装成功/失败 (base.py:8-13)
4. **多协议适配**: to_schema() / to_openai_schema() (base.py:38-55)
5. **指数退避重试**: RetryConfig + async_retry 装饰器 (retry.py:23-138)
6. **智能截断**: 保留头尾、截断中间、按换行符对齐 (file_tools.py:11-60)

---

## 数据模型速查

```python
# Message (schema/schema.py:29-37)
Message(
    role: str,                    # "system" | "user" | "assistant" | "tool"
    content: str | list[dict],    # 文本或 content blocks
    thinking: str | None,         # 扩展思考
    tool_calls: list[ToolCall],   # 工具调用列表
    tool_call_id: str | None,     # tool role 专用
    name: str | None,             # tool role 专用
)

# ToolCall (schema/schema.py:21-26)
ToolCall(
    id: str,
    type: str,                    # "function"
    function: FunctionCall(
        name: str,
        arguments: dict[str, Any]
    )
)

# ToolResult (base.py:8-13)
ToolResult(
    success: bool,
    content: str,
    error: str | None
)

# LLMResponse (schema/schema.py:48-55)
LLMResponse(
    content: str,
    thinking: str | None,
    tool_calls: list[ToolCall] | None,
    finish_reason: str,
    usage: TokenUsage | None
)
```

---

## 4. CLI 入口与交互循环 (CLI Entry Point)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/cli.py`

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 启动流程                            │
├─────────────────────────────────────────────────────────────┤
│  1. 加载配置 (Config.load())                                 │
│  2. 初始化基础工具 (initialize_base_tools)                   │
│  3. 添加工作区工具 (add_workspace_tools)                     │
│  4. 创建 LLM 客户端                                          │
│  5. 创建 Agent 实例                                          │
│  6. 进入交互循环 (interactive_loop)                          │
└─────────────────────────────────────────────────────────────┘
```

### 关键函数

#### 4.1 工具初始化
```python
# cli.py - initialize_base_tools()
async def initialize_base_tools(config: Config) -> tuple[list[Tool], SkillLoader | None]:
    """初始化不依赖工作目录的基础工具"""
    tools = []
    skill_loader = None

    # 1. Bash 工具 (跨平台)
    if config.tools.enable_bash:
        tools.extend([BashTool(), BashOutputTool(), BashKillTool()])

    # 2. Skill 工具 (渐进式披露)
    if config.tools.enable_skills:
        skill_tools, skill_loader = create_skill_tools(skills_dir)
        tools.extend(skill_tools)

    # 3. MCP 工具 (外部服务)
    if config.tools.enable_mcp:
        mcp_tools = await load_mcp_tools_async(mcp_config_path)
        tools.extend(mcp_tools)

    return tools, skill_loader

# cli.py - add_workspace_tools()
def add_workspace_tools(tools: list[Tool], config: Config, workspace: Path):
    """添加依赖工作目录的工具"""
    if config.tools.enable_file_tools:
        tools.extend([
            ReadTool(workspace_dir=str(workspace)),
            WriteTool(workspace_dir=str(workspace)),
            EditTool(workspace_dir=str(workspace)),
        ])

    if config.tools.enable_note:
        memory_file = workspace / ".agent_memory.json"
        tools.extend([
            SessionNoteTool(memory_file=str(memory_file)),
            RecallNoteTool(memory_file=str(memory_file)),
        ])
```

#### 4.2 交互循环
```python
# cli.py - interactive_loop() 核心逻辑
async def interactive_loop(agent: Agent, ...):
    while True:
        # 1. 获取用户输入
        user_input = await get_user_input()

        # 2. 处理特殊命令
        if user_input.startswith("/"):
            await handle_command(user_input)
            continue

        # 3. 添加用户消息
        agent.messages.append(Message(role="user", content=user_input))

        # 4. 运行 Agent (带取消支持)
        cancel_event = asyncio.Event()
        agent.cancel_event = cancel_event

        try:
            result = await agent.run()
            print(result)
        except KeyboardInterrupt:
            cancel_event.set()  # 触发优雅取消
```

---

## 5. 配置管理系统 (Configuration System)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/config.py`

### 配置层次结构

```python
# config.py - 配置类层次
Config
├── llm: LLMConfig
│   ├── api_key: str
│   ├── api_base: str = "https://api.minimax.io"
│   ├── model: str = "MiniMax-M2.1"
│   ├── provider: str = "anthropic"
│   └── retry: RetryConfig
│       ├── enabled: bool = True
│       ├── max_retries: int = 3
│       ├── initial_delay: float = 1.0
│       ├── max_delay: float = 60.0
│       └── exponential_base: float = 2.0
├── agent: AgentConfig
│   ├── max_steps: int = 50
│   ├── workspace_dir: str = "./workspace"
│   └── system_prompt_path: str = "system_prompt.md"
└── tools: ToolsConfig
    ├── enable_file_tools: bool = True
    ├── enable_bash: bool = True
    ├── enable_note: bool = True
    ├── enable_skills: bool = True
    ├── skills_dir: str = "./skills"
    ├── enable_mcp: bool = True
    ├── mcp_config_path: str = "mcp.json"
    └── mcp: MCPConfig
        ├── connect_timeout: float = 10.0
        ├── execute_timeout: float = 60.0
        └── sse_read_timeout: float = 120.0
```

### 配置文件搜索优先级
```python
# config.py:176-206 - find_config_file()
def find_config_file(cls, filename: str) -> Path | None:
    """配置文件搜索优先级"""
    # 优先级 1: 开发模式 - 当前目录的 mini_agent/config/
    dev_config = Path.cwd() / "mini_agent" / "config" / filename
    if dev_config.exists():
        return dev_config

    # 优先级 2: 用户配置目录 ~/.mini-agent/config/
    user_config = Path.home() / ".mini-agent" / "config" / filename
    if user_config.exists():
        return user_config

    # 优先级 3: 包安装目录的 config/
    package_config = cls.get_package_dir() / "config" / filename
    if package_config.exists():
        return package_config

    return None
```

---

## 6. 日志系统 (Logging System)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/logger.py`

### 日志结构
```python
# logger.py - AgentLogger
class AgentLogger:
    def __init__(self):
        self.log_dir = Path.home() / ".mini-agent" / "log"
        self.log_file = None
        self.log_index = 0

    def start_new_run(self):
        """创建新日志文件: agent_run_YYYYMMDD_HHMMSS.log"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"agent_run_{timestamp}.log"

    def log_request(self, messages: list[Message], tools: list[Any]):
        """记录 LLM 请求 (消息 + 工具名称)"""

    def log_response(self, content, thinking, tool_calls, finish_reason):
        """记录 LLM 响应"""

    def log_tool_result(self, tool_name, arguments, success, content, error):
        """记录工具执行结果"""
```

### 日志格式
```
================================================================================
Agent Run Log - 2024-01-15 10:30:45
================================================================================

--------------------------------------------------------------------------------
[1] REQUEST
Timestamp: 2024-01-15 10:30:45.123
--------------------------------------------------------------------------------
LLM Request:

{
  "messages": [...],
  "tools": ["read_file", "write_file", "bash"]
}

--------------------------------------------------------------------------------
[2] RESPONSE
Timestamp: 2024-01-15 10:30:47.456
--------------------------------------------------------------------------------
LLM Response:

{
  "content": "...",
  "thinking": "...",
  "tool_calls": [...]
}
```

---

## 7. Bash 工具与后台进程管理 (Bash Tool System)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/tools/bash_tool.py`

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Bash 工具系统                             │
├─────────────────────────────────────────────────────────────┤
│  BashTool          - 执行命令 (前台/后台)                    │
│  BashOutputTool    - 获取后台进程输出                        │
│  BashKillTool      - 终止后台进程                            │
├─────────────────────────────────────────────────────────────┤
│  BackgroundShell        - 后台进程数据容器                   │
│  BackgroundShellManager - 后台进程管理器 (单例)              │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计

#### 7.1 跨平台支持
```python
# bash_tool.py:225-228
class BashTool(Tool):
    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.shell_name = "PowerShell" if self.is_windows else "bash"

    async def execute(self, command: str, timeout: int = 120, run_in_background: bool = False):
        if self.is_windows:
            shell_cmd = ["powershell.exe", "-NoProfile", "-Command", command]
            process = await asyncio.create_subprocess_exec(*shell_cmd, ...)
        else:
            shell_cmd = command
            process = await asyncio.create_subprocess_shell(shell_cmd, ...)
```

#### 7.2 后台进程管理
```python
# bash_tool.py:52-106 - BackgroundShell
class BackgroundShell:
    """后台进程数据容器"""
    def __init__(self, bash_id: str, command: str, process, start_time: float):
        self.bash_id = bash_id
        self.command = command
        self.process = process
        self.start_time = start_time
        self.output_lines: list[str] = []  # 输出缓冲
        self.last_read_index = 0           # 增量读取指针
        self.status = "running"            # running/completed/failed/terminated
        self.exit_code: int | None = None

    def get_new_output(self, filter_pattern: str | None = None) -> list[str]:
        """获取自上次读取后的新输出 (支持正则过滤)"""
        new_lines = self.output_lines[self.last_read_index:]
        self.last_read_index = len(self.output_lines)
        if filter_pattern:
            pattern = re.compile(filter_pattern)
            new_lines = [line for line in new_lines if pattern.search(line)]
        return new_lines

# bash_tool.py:108-214 - BackgroundShellManager
class BackgroundShellManager:
    """后台进程管理器 (类级别单例)"""
    _shells: dict[str, BackgroundShell] = {}
    _monitor_tasks: dict[str, asyncio.Task] = {}

    @classmethod
    async def start_monitor(cls, bash_id: str):
        """启动输出监控协程"""
        async def monitor():
            while process.returncode is None:
                line = await process.stdout.readline()
                shell.add_output(line.decode())
            shell.update_status(is_alive=False, exit_code=process.returncode)
        task = asyncio.create_task(monitor())
        cls._monitor_tasks[bash_id] = task

    @classmethod
    async def terminate(cls, bash_id: str) -> BackgroundShell:
        """终止进程并清理资源"""
        shell = cls.get(bash_id)
        await shell.terminate()  # SIGTERM -> SIGKILL
        cls._cancel_monitor(bash_id)
        cls._remove(bash_id)
        return shell
```

#### 7.3 扩展结果类型
```python
# bash_tool.py:18-49
class BashOutputResult(ToolResult):
    """Bash 执行结果 (继承 ToolResult)"""
    stdout: str
    stderr: str
    exit_code: int
    bash_id: str | None = None  # 后台进程 ID

    @model_validator(mode="after")
    def format_content(self) -> "BashOutputResult":
        """自动格式化 content 字段"""
        output = self.stdout
        if self.stderr:
            output += f"\n[stderr]:\n{self.stderr}"
        if self.bash_id:
            output += f"\n[bash_id]:\n{self.bash_id}"
        self.content = output or "(no output)"
        return self
```

---

## 8. MCP 工具加载器 (MCP Tool Loader)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/tools/mcp_loader.py`

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP 工具系统                              │
├─────────────────────────────────────────────────────────────┤
│  MCPTool              - MCP 工具包装器                       │
│  MCPServerConnection  - 单个 MCP 服务器连接                  │
│  MCPTimeoutConfig     - 超时配置                             │
├─────────────────────────────────────────────────────────────┤
│  支持连接类型:                                               │
│  - stdio: 本地进程 (command + args)                         │
│  - sse: Server-Sent Events                                  │
│  - http/streamable_http: HTTP 流式传输                      │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计

#### 8.1 MCP 工具包装
```python
# mcp_loader.py:60-119
class MCPTool(Tool):
    """MCP 工具包装器 (带超时保护)"""
    def __init__(self, name, description, parameters, session: ClientSession, execute_timeout):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._session = session
        self._execute_timeout = execute_timeout

    async def execute(self, **kwargs) -> ToolResult:
        try:
            async with asyncio.timeout(self._execute_timeout):
                result = await self._session.call_tool(self._name, arguments=kwargs)

            # 解析 MCP 结果 (content items 列表)
            content_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
            return ToolResult(success=not result.isError, content="\n".join(content_parts))

        except TimeoutError:
            return ToolResult(success=False, error=f"MCP tool timed out after {timeout}s")
```

#### 8.2 多协议连接
```python
# mcp_loader.py:122-268
class MCPServerConnection:
    """MCP 服务器连接管理"""
    def __init__(self, name, connection_type, command, args, env, url, headers, ...):
        self.connection_type = connection_type  # stdio/sse/http/streamable_http
        # STDIO 参数
        self.command = command
        self.args = args
        self.env = env
        # URL 参数
        self.url = url
        self.headers = headers

    async def connect(self) -> bool:
        async with asyncio.timeout(connect_timeout):
            if self.connection_type == "stdio":
                read_stream, write_stream = await self._connect_stdio()
            elif self.connection_type == "sse":
                read_stream, write_stream = await self._connect_sse()
            else:
                read_stream, write_stream = await self._connect_streamable_http()

            session = await ClientSession(read_stream, write_stream)
            await session.initialize()
            tools_list = await session.list_tools()

            # 包装每个工具
            for tool in tools_list.tools:
                self.tools.append(MCPTool(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.inputSchema,
                    session=session,
                    execute_timeout=self._get_execute_timeout(),
                ))
```

#### 8.3 配置文件格式
```json
// mcp.json 示例
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/dir"],
      "disabled": false
    },
    "remote-api": {
      "url": "https://api.example.com/mcp",
      "type": "streamable_http",
      "headers": {"Authorization": "Bearer xxx"},
      "execute_timeout": 120.0
    }
  }
}
```

---

## 9. Skill 系统 (Progressive Disclosure)

### 核心文件
- `~/Desktop/github/Mini-Agent/mini_agent/tools/skill_loader.py` - Skill 加载器
- `~/Desktop/github/Mini-Agent/mini_agent/tools/skill_tool.py` - Skill 工具

### 渐进式披露架构

```
┌─────────────────────────────────────────────────────────────┐
│              Progressive Disclosure 三层架构                 │
├─────────────────────────────────────────────────────────────┤
│  Level 1: 元数据 (System Prompt)                            │
│    - 只包含 skill 名称和描述                                 │
│    - Agent 知道有哪些 skill 可用                             │
├─────────────────────────────────────────────────────────────┤
│  Level 2: 按需加载 (get_skill 工具)                         │
│    - Agent 调用 get_skill("skill-name")                     │
│    - 返回完整的 skill 内容                                   │
├─────────────────────────────────────────────────────────────┤
│  Level 3: 嵌套资源 (路径处理)                               │
│    - skill 内容中的相对路径自动转换为绝对路径                │
│    - Agent 可以读取 skill 引用的文件                         │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计

#### 9.1 SKILL.md 格式
```yaml
---
name: pdf-skill
description: Create and manipulate PDF documents
license: MIT
allowed-tools:
  - bash
  - read_file
  - write_file
metadata:
  author: example
---
# PDF Skill Instructions

Use this skill to create PDF documents...

Read [`reference.md`](reference.md) for API details.
Run `python scripts/generate.py` to create PDF.
```

#### 9.2 路径处理
```python
# skill_loader.py:119-192
def _process_skill_paths(self, content: str, skill_dir: Path) -> str:
    """将相对路径转换为绝对路径"""

    # Pattern 1: 目录路径 (scripts/, references/, assets/)
    # "python scripts/gen.py" -> "python /abs/path/scripts/gen.py"
    pattern_dirs = r"(python\s+|`)((?:scripts|references|assets)/[^\s`\)]+)"

    # Pattern 2: 文档引用
    # "see reference.md" -> "see `/abs/path/reference.md` (use read_file)"
    pattern_docs = r"(see|read|refer to)\s+([a-zA-Z0-9_-]+\.(?:md|txt|json))"

    # Pattern 3: Markdown 链接
    # "[Guide](./ref/guide.md)" -> "[Guide](`/abs/path/ref/guide.md`) (use read_file)"
    pattern_markdown = r"\[([^\]]+)\]\(((?:\./)?[^)]+\.(?:md|txt|json))\)"
```

#### 9.3 元数据注入
```python
# skill_loader.py:237-256
def get_skills_metadata_prompt(self) -> str:
    """生成 Level 1 元数据 prompt"""
    prompt_parts = ["## Available Skills\n"]
    prompt_parts.append("Load a skill's full content using get_skill when needed.\n")

    for skill in self.loaded_skills.values():
        prompt_parts.append(f"- `{skill.name}`: {skill.description}")

    return "\n".join(prompt_parts)

# 注入到 system prompt
system_prompt = f"{base_prompt}\n\n{skill_loader.get_skills_metadata_prompt()}"
```

---

## 10. OpenAI 客户端实现 (OpenAI Client)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/llm/openai_client.py`

### 与 Anthropic 客户端的差异

| 特性 | Anthropic | OpenAI |
|------|-----------|--------|
| System 消息 | 单独参数 | messages 数组中 |
| Tool 结果 | user + tool_result | tool role |
| 思考内容 | thinking block | reasoning_details |
| 参数格式 | dict | JSON string |

### 关键实现

#### 10.1 消息格式转换
```python
# openai_client.py:114-180
def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
    api_messages = []

    for msg in messages:
        if msg.role == "system":
            # OpenAI: system 在 messages 数组中
            api_messages.append({"role": "system", "content": msg.content})

        elif msg.role == "assistant":
            assistant_msg = {"role": "assistant", "content": msg.content}

            if msg.tool_calls:
                tool_calls_list = []
                for tc in msg.tool_calls:
                    tool_calls_list.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.dumps(tc.function.arguments),  # JSON string!
                        },
                    })
                assistant_msg["tool_calls"] = tool_calls_list

            # 关键: 保留 reasoning_details 以支持 Interleaved Thinking
            if msg.thinking:
                assistant_msg["reasoning_details"] = [{"text": msg.thinking}]

            api_messages.append(assistant_msg)

        elif msg.role == "tool":
            # OpenAI: 使用 tool role
            api_messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })

    return None, api_messages
```

#### 10.2 响应解析
```python
# openai_client.py:203-259
def _parse_response(self, response) -> LLMResponse:
    message = response.choices[0].message

    # 提取思考内容
    thinking_content = ""
    if hasattr(message, "reasoning_details") and message.reasoning_details:
        for detail in message.reasoning_details:
            if hasattr(detail, "text"):
                thinking_content += detail.text

    # 解析工具调用 (arguments 是 JSON string)
    tool_calls = []
    if message.tool_calls:
        for tc in message.tool_calls:
            arguments = json.loads(tc.function.arguments)  # 解析 JSON
            tool_calls.append(ToolCall(
                id=tc.id,
                type="function",
                function=FunctionCall(name=tc.function.name, arguments=arguments),
            ))

    return LLMResponse(
        content=message.content or "",
        thinking=thinking_content if thinking_content else None,
        tool_calls=tool_calls if tool_calls else None,
        usage=TokenUsage(...) if response.usage else None,
    )
```

---

## 11. Note 工具 (Session Memory)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/tools/note_tool.py`

### 设计目的
- 让 Agent 在会话中记录重要信息
- 跨工具调用链保持上下文
- 持久化存储用户偏好和决策

### 实现
```python
# note_tool.py:17-125
class SessionNoteTool(Tool):
    """记录笔记"""
    name = "record_note"

    def __init__(self, memory_file: str = "./workspace/.agent_memory.json"):
        self.memory_file = Path(memory_file)

    async def execute(self, content: str, category: str = "general") -> ToolResult:
        notes = self._load_from_file()
        notes.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "content": content,
        })
        self._save_to_file(notes)
        return ToolResult(success=True, content=f"Recorded: {content}")

class RecallNoteTool(Tool):
    """回忆笔记"""
    name = "recall_notes"

    async def execute(self, category: str = None) -> ToolResult:
        notes = json.loads(self.memory_file.read_text())
        if category:
            notes = [n for n in notes if n.get("category") == category]
        # 格式化输出
        formatted = [f"{i}. [{n['category']}] {n['content']}" for i, n in enumerate(notes, 1)]
        return ToolResult(success=True, content="\n".join(formatted))
```

---

## 12. ACP 服务器 (Agent Client Protocol)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/acp/__init__.py`

### ACP 协议概述
ACP (Agent Client Protocol) 是一种标准化的 Agent 通信协议，类似于 LSP (Language Server Protocol)。

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    ACP 服务器架构                            │
├─────────────────────────────────────────────────────────────┤
│  Client (IDE/CLI)                                           │
│       │                                                     │
│       │ stdio (stdin/stdout)                                │
│       ▼                                                     │
│  AgentSideConnection                                        │
│       │                                                     │
│       ▼                                                     │
│  MiniMaxACPAgent                                            │
│       ├── initialize()    - 初始化连接                      │
│       ├── newSession()    - 创建会话                        │
│       ├── prompt()        - 处理用户输入                    │
│       └── cancel()        - 取消执行                        │
└─────────────────────────────────────────────────────────────┘
```

### 关键实现

#### 12.1 会话管理
```python
# acp/__init__.py:64-104
@dataclass
class SessionState:
    agent: Agent
    cancelled: bool = False

class MiniMaxACPAgent:
    def __init__(self, conn, config, llm, base_tools, system_prompt):
        self._sessions: dict[str, SessionState] = {}

    async def newSession(self, params: NewSessionRequest) -> NewSessionResponse:
        session_id = f"sess-{len(self._sessions)}-{uuid4().hex[:8]}"
        workspace = Path(params.cwd or self._config.agent.workspace_dir)

        # 为每个会话创建独立的 Agent
        tools = list(self._base_tools)
        add_workspace_tools(tools, self._config, workspace)
        agent = Agent(llm_client=self._llm, tools=tools, ...)

        self._sessions[session_id] = SessionState(agent=agent)
        return NewSessionResponse(sessionId=session_id)
```

#### 12.2 执行循环与实时更新
```python
# acp/__init__.py:127-165
async def _run_turn(self, state: SessionState, session_id: str) -> str:
    agent = state.agent

    for _ in range(agent.max_steps):
        if state.cancelled:
            return "cancelled"

        response = await agent.llm.generate(messages=agent.messages, tools=tool_schemas)

        # 实时发送思考内容
        if response.thinking:
            await self._send(session_id, update_agent_thought(text_block(response.thinking)))

        # 实时发送回复内容
        if response.content:
            await self._send(session_id, update_agent_message(text_block(response.content)))

        if not response.tool_calls:
            return "end_turn"

        # 执行工具并实时更新
        for call in response.tool_calls:
            await self._send(session_id, start_tool_call(call.id, f"🔧 {name}()"))
            result = await tool.execute(**args)
            await self._send(session_id, update_tool_call(call.id, status="completed", ...))

    return "max_turn_requests"
```

---

## 13. 终端工具 (Terminal Utilities)

### 核心文件
`~/Desktop/github/Mini-Agent/mini_agent/utils/terminal_utils.py`

### 功能
处理终端显示宽度计算，正确处理：
- ANSI 转义码 (颜色等)
- Emoji 字符 (2 列宽)
- 东亚字符 (2 列宽)
- 组合字符 (0 列宽)

```python
# terminal_utils.py:18-68
def calculate_display_width(text: str) -> int:
    """计算文本在终端中的显示宽度"""
    # 移除 ANSI 转义码
    clean_text = ANSI_ESCAPE_RE.sub("", text)

    width = 0
    for char in clean_text:
        if unicodedata.combining(char):
            continue  # 组合字符不占宽度

        code_point = ord(char)
        if EMOJI_START <= code_point <= EMOJI_END:
            width += 2  # Emoji 占 2 列
            continue

        eaw = unicodedata.east_asian_width(char)
        if eaw in ("W", "F"):
            width += 2  # 东亚宽字符占 2 列
        else:
            width += 1

    return width

def truncate_with_ellipsis(text: str, max_width: int) -> str:
    """截断文本并添加省略号"""

def pad_to_width(text: str, target_width: int, align: str = "left") -> str:
    """填充文本到指定宽度"""
```

---

## 14. 项目完整架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Mini-Agent 完整架构                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   CLI       │     │   ACP       │     │   Config    │                   │
│  │  (cli.py)   │     │ (acp/)      │     │ (config.py) │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│         └───────────────────┼───────────────────┘                           │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Agent (agent.py)                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  主循环: while step < max_steps                              │    │   │
│  │  │    1. 检查取消 → 2. Token 管理 → 3. LLM 调用                 │    │   │
│  │  │    4. 解析响应 → 5. 执行工具 → 6. 更新消息历史               │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│         ┌───────────────────┼───────────────────┐                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │ LLM Client  │     │   Tools     │     │   Logger    │                   │
│  │ (llm/)      │     │  (tools/)   │     │ (logger.py) │                   │
│  └──────┬──────┘     └──────┬──────┘     └─────────────┘                   │
│         │                   │                                               │
│         ▼                   ▼                                               │
│  ┌─────────────┐     ┌─────────────────────────────────────────────────┐   │
│  │ LLMClient   │     │                    工具系统                      │   │
│  │ (Wrapper)   │     │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │      │      │     │  │ File     │ │ Bash     │ │ Note     │        │   │
│  │      ▼      │     │  │ Tools    │ │ Tools    │ │ Tools    │        │   │
│  │ ┌────────┐  │     │  └──────────┘ └──────────┘ └──────────┘        │   │
│  │ │Anthropic│ │     │  ┌──────────┐ ┌──────────┐                     │   │
│  │ │Client  │  │     │  │ MCP      │ │ Skill    │                     │   │
│  │ └────────┘  │     │  │ Loader   │ │ System   │                     │   │
│  │ ┌────────┐  │     │  └──────────┘ └──────────┘                     │   │
│  │ │OpenAI  │  │     └─────────────────────────────────────────────────┘   │
│  │ │Client  │  │                                                           │
│  │ └────────┘  │                                                           │
│  └─────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. 复现指南

### 15.1 核心依赖
```toml
# pyproject.toml 关键依赖
[dependencies]
anthropic = "^0.40.0"      # Anthropic SDK
openai = "^1.50.0"         # OpenAI SDK
pydantic = "^2.0"          # 数据模型
tiktoken = "^0.7.0"        # Token 计算
pyyaml = "^6.0"            # 配置解析
mcp = "^1.0.0"             # MCP 协议
acp = "^0.1.0"             # ACP 协议 (可选)
```

### 15.2 最小可运行版本
```python
# 1. 数据模型 (schema.py)
class Message(BaseModel):
    role: str
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

class ToolCall(BaseModel):
    id: str
    function: FunctionCall

class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] | None = None

# 2. 工具基类 (tools/base.py)
class ToolResult(BaseModel):
    success: bool
    content: str = ""
    error: str | None = None

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    @property
    @abstractmethod
    def parameters(self) -> dict: ...
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...

# 3. LLM 客户端 (llm/base.py)
class LLMClientBase(ABC):
    @abstractmethod
    async def generate(self, messages, tools) -> LLMResponse: ...

# 4. Agent 核心 (agent.py)
class Agent:
    def __init__(self, llm_client, system_prompt, tools, max_steps=50):
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}
        self.messages = [Message(role="system", content=system_prompt)]
        self.max_steps = max_steps

    async def run(self) -> str:
        for step in range(self.max_steps):
            response = await self.llm.generate(
                messages=self.messages,
                tools=[t.to_schema() for t in self.tools.values()]
            )

            self.messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls
            ))

            if not response.tool_calls:
                return response.content

            for tc in response.tool_calls:
                tool = self.tools[tc.function.name]
                result = await tool.execute(**tc.function.arguments)
                self.messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=tc.id
                ))

        return "Max steps reached"
```

### 15.3 扩展功能优先级

| 优先级 | 功能 | 文件 |
|--------|------|------|
| P0 | Agent 核心循环 | agent.py |
| P0 | LLM 客户端 | llm/*.py |
| P0 | 基础工具 (Read/Write/Bash) | tools/*.py |
| P1 | Token 管理 + 自动摘要 | agent.py |
| P1 | 重试机制 | retry.py |
| P1 | 配置系统 | config.py |
| P2 | MCP 工具加载 | tools/mcp_loader.py |
| P2 | Skill 系统 | tools/skill_*.py |
| P2 | 后台进程管理 | tools/bash_tool.py |
| P3 | ACP 服务器 | acp/__init__.py |
| P3 | 日志系统 | logger.py |

---

## 16. 设计亮点总结 (完整版)

| 模块 | 设计模式 | 核心价值 |
|------|----------|----------|
| Agent 循环 | 状态机 + 事件驱动 | 可中断、可恢复、可追踪 |
| 工具系统 | 模板方法 + 策略模式 | 易扩展、多协议支持 |
| LLM 客户端 | 策略模式 + 装饰器 | 多 Provider 统一接口 |
| 配置系统 | 分层配置 + 优先级搜索 | 开发/生产环境分离 |
| Bash 工具 | 管理器模式 + 异步监控 | 后台进程生命周期管理 |
| MCP 加载器 | 适配器模式 + 超时保护 | 外部服务安全集成 |
| Skill 系统 | 渐进式披露 | 按需加载、节省 Token |
| ACP 服务器 | 会话管理 + 实时更新 | IDE 集成、标准化协议 |

---

## 17. 文件索引

```
mini_agent/
├── agent.py              # Agent 核心循环
├── cli.py                # CLI 入口
├── config.py             # 配置管理
├── logger.py             # 日志系统
├── retry.py              # 重试机制
├── schema/
│   └── schema.py         # 数据模型
├── llm/
│   ├── base.py           # LLM 客户端基类
│   ├── llm_wrapper.py    # 统一包装器
│   ├── anthropic_client.py
│   └── openai_client.py
├── tools/
│   ├── base.py           # 工具基类
│   ├── file_tools.py     # 文件工具
│   ├── bash_tool.py      # Bash 工具
│   ├── note_tool.py      # 笔记工具
│   ├── mcp_loader.py     # MCP 加载器
│   ├── skill_loader.py   # Skill 加载器
│   └── skill_tool.py     # Skill 工具
├── utils/
│   └── terminal_utils.py # 终端工具
├── acp/
│   └── __init__.py       # ACP 服务器
└── config/
    ├── config.yaml       # 主配置
    ├── mcp.json          # MCP 配置
    └── system_prompt.md  # 系统提示词
```
