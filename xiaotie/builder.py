"""
Agent Builder - 声明式 Agent 构建器

提供流畅的 API 来构建自定义 Agent，降低开发门槛。

使用示例:
```python
from xiaotie import AgentBuilder

agent = (
    AgentBuilder("my-agent")
    .with_llm(provider="anthropic", model="claude-sonnet-4")
    .with_tools([ReadTool(), WriteTool()])
    .with_system_prompt("You are a helpful assistant.")
    .with_hooks(on_tool_call=lambda t: print(f"Calling {t}"))
    .build()
)

result = await agent.run("Hello!")
```
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

from .agent import Agent, AgentConfig
from .llm import LLMClient
from .tools import Tool


@dataclass
class AgentHooks:
    """Agent 生命周期钩子"""

    on_start: Optional[Callable[[], None]] = None
    on_step: Optional[Callable[[int], None]] = None
    on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None
    on_tool_result: Optional[Callable[[str, Any], None]] = None
    on_thinking: Optional[Callable[[str], None]] = None
    on_content: Optional[Callable[[str], None]] = None
    on_complete: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None


@dataclass
class AgentSpec:
    """Agent 规格定义 - 支持 YAML/JSON 配置"""

    name: str
    description: str = ""
    # LLM 配置
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    # Agent 配置
    system_prompt: str = "You are a helpful AI assistant."
    max_steps: int = 50
    token_limit: int = 100000
    stream: bool = True
    enable_thinking: bool = True
    parallel_tools: bool = True
    # 工具配置
    tools: List[str] = field(default_factory=list)
    # 工作目录
    workspace_dir: str = "."

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "AgentSpec":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSpec":
        """从字典加载配置"""
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "max_steps": self.max_steps,
            "token_limit": self.token_limit,
            "stream": self.stream,
            "enable_thinking": self.enable_thinking,
            "parallel_tools": self.parallel_tools,
            "tools": self.tools,
            "workspace_dir": self.workspace_dir,
        }

    def to_yaml(self, path: Union[str, Path]) -> None:
        """保存为 YAML 文件"""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)


class AgentBuilder:
    """
    Agent 构建器 - 流畅 API

    使用示例:
    ```python
    agent = (
        AgentBuilder("code-assistant")
        .with_llm(provider="anthropic", model="claude-sonnet-4")
        .with_tools([ReadTool(), WriteTool(), BashTool()])
        .with_system_prompt("You are a coding assistant.")
        .with_config(max_steps=100, parallel_tools=True)
        .with_hooks(on_tool_call=lambda t, a: print(f"Calling {t}"))
        .build()
    )
    ```
    """

    def __init__(self, name: str = "xiaotie-agent"):
        """初始化构建器"""
        self._name = name
        self._description = ""
        # LLM 配置
        self._provider = "anthropic"
        self._model = "claude-sonnet-4-20250514"
        self._api_key: Optional[str] = None
        self._api_base: Optional[str] = None
        # Agent 配置
        self._system_prompt = "You are a helpful AI assistant."
        self._max_steps = 50
        self._token_limit = 100000
        self._stream = True
        self._enable_thinking = True
        self._parallel_tools = True
        self._workspace_dir = "."
        # 工具
        self._tools: List[Tool] = []
        # 钩子
        self._hooks = AgentHooks()
        # 预构建的 LLM 客户端
        self._llm_client: Optional[LLMClient] = None

    def with_name(self, name: str) -> "AgentBuilder":
        """设置 Agent 名称"""
        self._name = name
        return self

    def with_description(self, description: str) -> "AgentBuilder":
        """设置 Agent 描述"""
        self._description = description
        return self

    def with_llm(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        client: Optional[LLMClient] = None,
    ) -> "AgentBuilder":
        """
        配置 LLM

        可以直接传入 LLMClient 实例，或者通过参数配置:
        - provider: anthropic, openai, minimax 等
        - model: 模型名称
        - api_key: API 密钥 (也可通过环境变量)
        - api_base: API 基础 URL
        """
        if client is not None:
            self._llm_client = client
        else:
            if provider:
                self._provider = provider
            if model:
                self._model = model
            if api_key:
                self._api_key = api_key
            if api_base:
                self._api_base = api_base
        return self

    def with_tools(self, tools: List[Tool]) -> "AgentBuilder":
        """添加工具列表"""
        self._tools.extend(tools)
        return self

    def with_tool(self, tool: Tool) -> "AgentBuilder":
        """添加单个工具"""
        self._tools.append(tool)
        return self

    def with_system_prompt(self, prompt: str) -> "AgentBuilder":
        """设置系统提示词"""
        self._system_prompt = prompt
        return self

    def with_system_prompt_file(self, path: Union[str, Path]) -> "AgentBuilder":
        """从文件加载系统提示词"""
        with open(path, "r", encoding="utf-8") as f:
            self._system_prompt = f.read()
        return self

    def with_config(
        self,
        max_steps: Optional[int] = None,
        token_limit: Optional[int] = None,
        stream: Optional[bool] = None,
        enable_thinking: Optional[bool] = None,
        parallel_tools: Optional[bool] = None,
        workspace_dir: Optional[str] = None,
    ) -> "AgentBuilder":
        """配置 Agent 参数"""
        if max_steps is not None:
            self._max_steps = max_steps
        if token_limit is not None:
            self._token_limit = token_limit
        if stream is not None:
            self._stream = stream
        if enable_thinking is not None:
            self._enable_thinking = enable_thinking
        if parallel_tools is not None:
            self._parallel_tools = parallel_tools
        if workspace_dir is not None:
            self._workspace_dir = workspace_dir
        return self

    def with_hooks(
        self,
        on_start: Optional[Callable[[], None]] = None,
        on_step: Optional[Callable[[int], None]] = None,
        on_tool_call: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, Any], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_content: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> "AgentBuilder":
        """配置生命周期钩子"""
        if on_start:
            self._hooks.on_start = on_start
        if on_step:
            self._hooks.on_step = on_step
        if on_tool_call:
            self._hooks.on_tool_call = on_tool_call
        if on_tool_result:
            self._hooks.on_tool_result = on_tool_result
        if on_thinking:
            self._hooks.on_thinking = on_thinking
        if on_content:
            self._hooks.on_content = on_content
        if on_complete:
            self._hooks.on_complete = on_complete
        if on_error:
            self._hooks.on_error = on_error
        return self

    def from_spec(self, spec: Union[AgentSpec, Dict[str, Any], str, Path]) -> "AgentBuilder":
        """从 AgentSpec 加载配置"""
        if isinstance(spec, (str, Path)):
            spec = AgentSpec.from_yaml(spec)
        elif isinstance(spec, dict):
            spec = AgentSpec.from_dict(spec)

        self._name = spec.name
        self._description = spec.description
        self._provider = spec.provider
        self._model = spec.model
        if spec.api_key:
            self._api_key = spec.api_key
        if spec.api_base:
            self._api_base = spec.api_base
        self._system_prompt = spec.system_prompt
        self._max_steps = spec.max_steps
        self._token_limit = spec.token_limit
        self._stream = spec.stream
        self._enable_thinking = spec.enable_thinking
        self._parallel_tools = spec.parallel_tools
        self._workspace_dir = spec.workspace_dir
        return self

    def to_spec(self) -> AgentSpec:
        """导出为 AgentSpec"""
        return AgentSpec(
            name=self._name,
            description=self._description,
            provider=self._provider,
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
            system_prompt=self._system_prompt,
            max_steps=self._max_steps,
            token_limit=self._token_limit,
            stream=self._stream,
            enable_thinking=self._enable_thinking,
            parallel_tools=self._parallel_tools,
            tools=[t.name for t in self._tools],
            workspace_dir=self._workspace_dir,
        )

    def _create_llm_client(self) -> LLMClient:
        """创建 LLM 客户端"""
        if self._llm_client is not None:
            return self._llm_client

        # 从环境变量获取 API Key
        api_key = self._api_key
        if not api_key:
            env_map = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "minimax": "MINIMAX_API_KEY",
                "zhipu": "ZHIPU_API_KEY",
            }
            env_var = env_map.get(self._provider, f"{self._provider.upper()}_API_KEY")
            api_key = os.environ.get(env_var)

        if not api_key:
            raise ValueError(
                f"API key not provided for {self._provider}. "
                f"Set it via with_llm(api_key=...) or environment variable."
            )

        # 默认 API Base
        api_base = self._api_base
        if not api_base:
            base_map = {
                "anthropic": "https://api.anthropic.com",
                "openai": "https://api.openai.com/v1",
                "minimax": "https://api.minimax.io",
                "zhipu": "https://open.bigmodel.cn/api/coding/paas/v4",
            }
            api_base = base_map.get(self._provider, "https://api.openai.com/v1")

        return LLMClient(
            api_key=api_key,
            api_base=api_base,
            model=self._model,
            provider=self._provider,
        )

    def build(self) -> Agent:
        """构建 Agent 实例"""
        llm_client = self._create_llm_client()

        agent = Agent(
            llm_client=llm_client,
            system_prompt=self._system_prompt,
            tools=self._tools,
            max_steps=self._max_steps,
            token_limit=self._token_limit,
            workspace_dir=self._workspace_dir,
            stream=self._stream,
            enable_thinking=self._enable_thinking,
            parallel_tools=self._parallel_tools,
        )

        # 设置钩子
        if self._hooks.on_thinking:
            agent.on_thinking = self._hooks.on_thinking
        if self._hooks.on_content:
            agent.on_content = self._hooks.on_content

        # 存储其他钩子供后续使用
        agent._builder_hooks = self._hooks

        return agent


def create_agent(
    name: str = "xiaotie-agent",
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    tools: Optional[List[Tool]] = None,
    system_prompt: str = "You are a helpful AI assistant.",
    **kwargs,
) -> Agent:
    """
    快速创建 Agent 的便捷函数

    Args:
        name: Agent 名称
        provider: LLM 提供商
        model: 模型名称
        tools: 工具列表
        system_prompt: 系统提示词
        **kwargs: 其他 AgentBuilder 配置

    Returns:
        配置好的 Agent 实例
    """
    builder = AgentBuilder(name).with_llm(provider=provider, model=model).with_system_prompt(system_prompt)

    if tools:
        builder.with_tools(tools)

    # 应用其他配置
    config_keys = ["max_steps", "token_limit", "stream", "enable_thinking", "parallel_tools", "workspace_dir"]
    config_kwargs = {k: v for k, v in kwargs.items() if k in config_keys}
    if config_kwargs:
        builder.with_config(**config_kwargs)

    return builder.build()
