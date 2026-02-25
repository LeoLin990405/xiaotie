"""配置管理"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml

from .retry import RetryConfig


@dataclass
class CacheConfig:
    """缓存配置"""
    
    enabled: bool = True
    max_size: int = 1000
    ttl_seconds: int = 3600  # 1 hour


@dataclass
class LLMConfig:
    """LLM 配置"""

    api_key: str
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 4096
    retry: RetryConfig = field(default_factory=RetryConfig)


@dataclass
class AgentConfig:
    """Agent 配置"""

    max_steps: int = 50
    workspace_dir: str = "./workspace"
    system_prompt_path: str = "system_prompt.md"
    thinking_enabled: bool = True
    streaming_enabled: bool = True
    verbose: bool = False
    cache_config: CacheConfig = field(default_factory=CacheConfig)


@dataclass
class ProxyConfig:
    """内置代理服务器配置"""

    enabled: bool = False
    port: int = 8080
    enable_https: bool = True
    cert_path: Optional[str] = None
    storage_path: Optional[str] = None


@dataclass
class ToolsConfig:
    """工具配置"""

    enable_file_tools: bool = True
    enable_bash: bool = True
    enable_web_tools: bool = True
    enable_code_analysis: bool = True
    enable_python: bool = True
    enable_calculator: bool = True
    enable_git: bool = True
    enable_charles: bool = False
    charles_path: Optional[str] = None
    charles_proxy_port: int = 8888
    enable_proxy: bool = False
    proxy: ProxyConfig = field(default_factory=ProxyConfig)


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
class LoggingConfig:
    """日志配置"""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


@dataclass
class Config:
    """主配置"""

    llm: LLMConfig
    agent: AgentConfig = field(default_factory=AgentConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

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
        """从 YAML 文件加载配置。

        解析 YAML 配置文件并构建完整的 Config 对象。支持从环境变量
        读取 API Key，支持嵌套的重试、缓存、工具、MCP 等配置。

        Args:
            config_path: YAML 配置文件路径。

        Returns:
            Config: 解析后的配置对象。

        Raises:
            FileNotFoundError: 配置文件不存在。
            ValueError: 配置文件为空，或 API Key 未设置。
            yaml.YAMLError: YAML 格式解析错误。
        """
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

        # 解析缓存配置
        cache_data = data.get("cache", {})
        cache_config = CacheConfig(
            enabled=cache_data.get("enabled", True),
            max_size=cache_data.get("max_size", 1000),
            ttl_seconds=cache_data.get("ttl_seconds", 3600),
        )

        # LLM 配置
        llm_config = LLMConfig(
            api_key=api_key,
            api_base=data.get("api_base", "https://api.anthropic.com"),
            model=data.get("model", "claude-sonnet-4-20250514"),
            provider=provider,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
            retry=retry_config,
        )

        # Agent 配置
        agent_config = AgentConfig(
            max_steps=data.get("max_steps", 50),
            workspace_dir=data.get("workspace_dir", "./workspace"),
            system_prompt_path=data.get("system_prompt_path", "system_prompt.md"),
            thinking_enabled=data.get("thinking_enabled", True),
            streaming_enabled=data.get("streaming_enabled", True),
            verbose=data.get("verbose", False),
            cache_config=cache_config,
        )

        # 工具配置
        tools_data = data.get("tools", {})

        # 代理配置
        proxy_data = tools_data.get("proxy", {})
        proxy_config = ProxyConfig(
            enabled=proxy_data.get("enabled", False),
            port=proxy_data.get("port", 8080),
            enable_https=proxy_data.get("enable_https", True),
            cert_path=proxy_data.get("cert_path"),
            storage_path=proxy_data.get("storage_path"),
        )

        tools_config = ToolsConfig(
            enable_file_tools=tools_data.get("enable_file_tools", True),
            enable_bash=tools_data.get("enable_bash", True),
            enable_web_tools=tools_data.get("enable_web_tools", True),
            enable_code_analysis=tools_data.get("enable_code_analysis", True),
            enable_python=tools_data.get("enable_python", True),
            enable_calculator=tools_data.get("enable_calculator", True),
            enable_git=tools_data.get("enable_git", True),
            enable_charles=tools_data.get("enable_charles", False),
            charles_path=tools_data.get("charles_path"),
            charles_proxy_port=tools_data.get("charles_proxy_port", 8888),
            enable_proxy=tools_data.get("enable_proxy", proxy_data.get("enabled", False)),
            proxy=proxy_config,
        )

        # MCP 配置
        mcp_data = data.get("mcp", {}) or {}
        mcp_servers: Dict[str, MCPServerConfig] = {}
        servers_data = mcp_data.get("servers", {}) or {}
        for server_name, server_data in servers_data.items():
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

        # 日志配置
        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            format=logging_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=logging_data.get("file_path"),
            max_bytes=logging_data.get("max_bytes", 10485760),
            backup_count=logging_data.get("backup_count", 5),
        )

        return cls(
            llm=llm_config,
            agent=agent_config,
            tools=tools_config,
            mcp=mcp_config,
            logging=logging_config,
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
