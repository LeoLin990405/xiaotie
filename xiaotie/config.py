"""配置管理"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator


class RetryConfig(BaseModel):
    """重试配置"""
    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


class CacheConfig(BaseModel):
    """缓存配置"""
    
    enabled: bool = True
    max_size: int = 1000
    ttl_seconds: int = 3600  # 1 hour


class LLMConfig(BaseModel):
    """LLM 配置"""

    api_key: str = ""
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 4096
    retry: RetryConfig = Field(default_factory=RetryConfig)


class AgentConfig(BaseModel):
    """Agent 配置"""

    max_steps: int = 50
    workspace_dir: str = "./workspace"
    system_prompt_path: str = "system_prompt.md"
    thinking_enabled: bool = True
    streaming_enabled: bool = True
    verbose: bool = False
    cache_config: CacheConfig = Field(default_factory=CacheConfig, alias="cache")


class ProxyConfig(BaseModel):
    """内置代理服务器配置"""

    enabled: bool = False
    port: int = 8080
    enable_https: bool = True
    cert_path: Optional[str] = None
    storage_path: Optional[str] = None


class ScraperConfig(BaseModel):
    """爬虫工具配置"""

    enabled: bool = False
    scraper_dir: Optional[str] = None
    max_workers: int = 4
    request_delay: float = 1.0
    num_runs: int = 3
    stability_threshold: float = 0.9


class AutomationConfig(BaseModel):
    """macOS 自动化工具配置"""

    enabled: bool = False
    wechat_bundle_id: str = "com.tencent.xinWeChat"
    screenshot_dir: Optional[str] = None
    applescript_timeout: int = 30


class TelegramConfig(BaseModel):
    """Telegram 工具配置"""

    enabled: bool = False
    bot_token: Optional[str] = None
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 9000
    webhook_path: str = "/telegram/webhook"
    webhook_secret_token: Optional[str] = None
    allowed_chat_ids: List[int] = Field(default_factory=list)
    allowed_cidrs: List[str] = Field(default_factory=list)


class ToolsConfig(BaseModel):
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
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    enable_scraper: bool = False
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    enable_automation: bool = False
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    enable_telegram: bool = False
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)

    @model_validator(mode="before")
    @classmethod
    def sync_tool_enables(cls, values):
        if not isinstance(values, dict):
            return values
        # 如果启用了具体的模块，也设置顶级标志
        proxy_data = values.get("proxy", {})
        if "enabled" in proxy_data:
            values["enable_proxy"] = values.get("enable_proxy", proxy_data["enabled"])
            
        scraper_data = values.get("scraper", {})
        if "enabled" in scraper_data:
            values["enable_scraper"] = values.get("enable_scraper", scraper_data["enabled"])
            
        automation_data = values.get("automation", {})
        if "enabled" in automation_data:
            values["enable_automation"] = values.get("enable_automation", automation_data["enabled"])
            
        telegram_data = values.get("telegram", {})
        if "enabled" in telegram_data:
            values["enable_telegram"] = values.get("enable_telegram", telegram_data["enabled"])
            
        return values


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    command: str = ""
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    enabled: bool = True


class MCPConfig(BaseModel):
    """MCP 配置"""

    enabled: bool = False
    servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)


class LoggingConfig(BaseModel):
    """日志配置"""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


class Config(BaseModel):
    """主配置"""

    llm: LLMConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

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
        # 兼容老版本配置（llm_data打平在最外层）
        llm_data = data.get("llm", {})
        if not llm_data:
            api_key = data.get("api_key", "")
            provider = data.get("provider", "anthropic")
            llm_data = {
                "api_key": api_key,
                "provider": provider,
                "api_base": data.get("api_base", "https://api.anthropic.com"),
                "model": data.get("model", "claude-sonnet-4-20250514"),
                "temperature": data.get("temperature", 0.7),
                "max_tokens": data.get("max_tokens", 4096),
                "retry": data.get("retry", {})
            }
            data["llm"] = llm_data

        # 兼容老版本 Agent 配置
        agent_data = data.get("agent", {})
        if not agent_data:
            agent_data = {
                "max_steps": data.get("max_steps", 50),
                "workspace_dir": data.get("workspace_dir", "./workspace"),
                "system_prompt_path": data.get("system_prompt_path", "system_prompt.md"),
                "thinking_enabled": data.get("thinking_enabled", True),
                "streaming_enabled": data.get("streaming_enabled", True),
                "verbose": data.get("verbose", False),
                "cache": data.get("cache", {})
            }
            data["agent"] = agent_data

        api_key = llm_data.get("api_key", "")
        provider = llm_data.get("provider", "anthropic")

        # 如果 api_key 为空或是占位符，尝试从环境变量读取
        if not api_key or api_key in ("YOUR_API_KEY_HERE", "YOUR_API_KEY"):
            env_key = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            api_key = os.environ.get(env_key, "")
            if not api_key:
                raise ValueError(
                    f"请设置 API key：在配置文件中设置 api_key，或设置环境变量 {env_key}"
                )
            llm_data["api_key"] = api_key

        return cls.model_validate(data)

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
