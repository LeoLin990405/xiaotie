"""配置管理"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class RetryConfig:
    """重试配置"""

    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


@dataclass
class LLMConfig:
    """LLM 配置"""

    api_key: str
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    provider: str = "anthropic"
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass
class AgentConfig:
    """Agent 配置"""

    max_steps: int = 50
    workspace_dir: str = "./workspace"
    system_prompt_path: str = "system_prompt.md"


@dataclass
class ToolsConfig:
    """工具配置"""

    enable_file_tools: bool = True
    enable_bash: bool = True


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""

    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    enabled: bool = True


@dataclass
class MCPConfig:
    """MCP 配置"""

    enabled: bool = False
    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)


@dataclass
class Config:
    """主配置"""

    llm: LLMConfig
    agent: AgentConfig = field(default_factory=AgentConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Config":
        """加载配置"""
        if config_path is None:
            config_path = cls._find_config_file()

        if config_path is None or not Path(config_path).exists():
            raise FileNotFoundError("配置文件未找到，请创建 config/config.yaml")

        return cls.from_yaml(config_path)

    @classmethod
    def _find_config_file(cls) -> Path | None:
        """查找配置文件"""
        # 优先级: 当前目录 > 用户目录 > 包目录
        search_paths = [
            Path.cwd() / "config" / "config.yaml",
            Path.cwd() / "xiaotie" / "config" / "config.yaml",
            Path.home() / ".xiaotie" / "config" / "config.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Config":
        """从 YAML 文件加载配置"""
        config_path = Path(config_path)

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("配置文件为空")

        # 获取 API key（支持环境变量）
        api_key = data.get("api_key", "")
        provider = data.get("provider", "anthropic")

        # 如果 api_key 为空或是占位符，尝试从环境变量读取
        if not api_key or api_key in ("YOUR_API_KEY_HERE", "YOUR_API_KEY"):
            env_key = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            api_key = os.environ.get(env_key, "")
            if not api_key:
                raise ValueError(
                    f"请设置 API key：在配置文件中设置 api_key，或设置环境变量 {env_key}"
                )

        # 解析重试配置
        retry_data = data.get("retry", {})
        retry_config = RetryConfig(
            enabled=retry_data.get("enabled", True),
            max_retries=retry_data.get("max_retries", 3),
            initial_delay=retry_data.get("initial_delay", 1.0),
            max_delay=retry_data.get("max_delay", 60.0),
            exponential_base=retry_data.get("exponential_base", 2.0),
        )

        # LLM 配置
        llm_config = LLMConfig(
            api_key=api_key,
            api_base=data.get("api_base", "https://api.anthropic.com"),
            model=data.get("model", "claude-sonnet-4-20250514"),
            provider=provider,
            retry=retry_config,
        )

        # Agent 配置
        agent_config = AgentConfig(
            max_steps=data.get("max_steps", 50),
            workspace_dir=data.get("workspace_dir", "./workspace"),
            system_prompt_path=data.get("system_prompt_path", "system_prompt.md"),
        )

        # 工具配置
        tools_data = data.get("tools", {})
        tools_config = ToolsConfig(
            enable_file_tools=tools_data.get("enable_file_tools", True),
            enable_bash=tools_data.get("enable_bash", True),
        )

        # MCP 配置
        mcp_data = data.get("mcp", {})
        mcp_servers: Dict[str, MCPServerConfig] = {}
        for server_name, server_data in mcp_data.get("servers", {}).items():
            mcp_servers[server_name] = MCPServerConfig(
                command=server_data.get("command", ""),
                args=server_data.get("args", []),
                env=server_data.get("env", {}),
                cwd=server_data.get("cwd"),
                enabled=server_data.get("enabled", True),
            )
        mcp_config = MCPConfig(
            enabled=mcp_data.get("enabled", False),
            servers=mcp_servers,
        )

        return cls(
            llm=llm_config,
            agent=agent_config,
            tools=tools_config,
            mcp=mcp_config,
        )

    @staticmethod
    def find_config_file(filename: str) -> Path | None:
        """查找配置文件"""
        search_paths = [
            Path.cwd() / "config" / filename,
            Path.cwd() / "xiaotie" / "config" / filename,
            Path.home() / ".xiaotie" / "config" / filename,
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None
