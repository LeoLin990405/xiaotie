"""配置模块测试"""

import os
from pathlib import Path

import pytest
import yaml

from xiaotie.config import (
    AgentConfig,
    CacheConfig,
    Config,
    LLMConfig,
    LoggingConfig,
    MCPConfig,
    ToolsConfig,
)


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

class TestConfigLoad:
    def test_from_yaml_basic(self, tmp_path):
        """基本 YAML 配置加载"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "api_key": "test-key-123",
            "model": "gpt-4",
            "provider": "openai",
        }))
        config = Config.from_yaml(cfg_file)
        assert config.llm.api_key == "test-key-123"
        assert config.llm.model == "gpt-4"
        assert config.llm.provider == "openai"

    def test_from_yaml_with_all_sections(self, tmp_path):
        """完整配置加载（含所有 section）"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "api_key": "key-abc",
            "provider": "anthropic",
            "max_steps": 100,
            "temperature": 0.5,
            "tools": {"enable_bash": False},
            "cache": {"enabled": False, "max_size": 500},
            "logging": {"level": "DEBUG"},
        }))
        config = Config.from_yaml(cfg_file)
        assert config.agent.max_steps == 100
        assert config.llm.temperature == 0.5
        assert config.tools.enable_bash is False
        assert config.agent.cache_config.enabled is False
        assert config.agent.cache_config.max_size == 500
        assert config.logging.level == "DEBUG"

    def test_empty_yaml_raises(self, tmp_path):
        """空配置文件应抛出 ValueError"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")
        with pytest.raises(ValueError, match="配置文件为空"):
            Config.from_yaml(cfg_file)

    def test_missing_file_raises(self):
        """不存在的配置文件应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            Config.load("/nonexistent/path/config.yaml")


# ---------------------------------------------------------------------------
# 配置验证
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_api_key_from_env(self, tmp_path, monkeypatch):
        """api_key 为占位符时应从环境变量读取"""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-456")
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "api_key": "YOUR_API_KEY_HERE",
            "provider": "openai",
        }))
        config = Config.from_yaml(cfg_file)
        assert config.llm.api_key == "env-key-456"

    def test_missing_api_key_raises(self, tmp_path, monkeypatch):
        """api_key 为空且环境变量也没有时应抛出 ValueError"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "api_key": "",
            "provider": "anthropic",
        }))
        with pytest.raises(ValueError, match="API key"):
            Config.from_yaml(cfg_file)

    def test_retry_config_defaults(self, tmp_path):
        """未指定 retry 时应使用默认值"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({"api_key": "k"}))
        config = Config.from_yaml(cfg_file)
        assert config.llm.retry.max_retries == 3
        assert config.llm.retry.enabled is True

    def test_mcp_config(self, tmp_path):
        """MCP 配置解析"""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "api_key": "k",
            "mcp": {
                "enabled": True,
                "servers": {
                    "test-server": {
                        "command": "node",
                        "args": ["server.js"],
                    }
                },
            },
        }))
        config = Config.from_yaml(cfg_file)
        assert config.mcp.enabled is True
        assert "test-server" in config.mcp.servers
        assert config.mcp.servers["test-server"].command == "node"


# ---------------------------------------------------------------------------
# Dataclass 默认值
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    def test_agent_config_defaults(self):
        cfg = AgentConfig()
        assert cfg.max_steps == 50
        assert cfg.thinking_enabled is True

    def test_tools_config_defaults(self):
        cfg = ToolsConfig()
        assert cfg.enable_bash is True
        assert cfg.enable_git is True

    def test_cache_config_defaults(self):
        cfg = CacheConfig()
        assert cfg.enabled is True
        assert cfg.ttl_seconds == 3600
