"""
AgentBuilder 单元测试
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xiaotie.builder import AgentBuilder, AgentHooks, AgentSpec, create_agent


class TestAgentSpec:
    """AgentSpec 测试"""

    def test_default_values(self):
        """测试默认值"""
        spec = AgentSpec(name="test-agent")
        assert spec.name == "test-agent"
        assert spec.provider == "anthropic"
        assert spec.model == "claude-sonnet-4-20250514"
        assert spec.max_steps == 50
        assert spec.stream is True

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "name": "custom-agent",
            "provider": "openai",
            "model": "gpt-4o",
            "max_steps": 100,
        }
        spec = AgentSpec.from_dict(data)
        assert spec.name == "custom-agent"
        assert spec.provider == "openai"
        assert spec.model == "gpt-4o"
        assert spec.max_steps == 100

    def test_to_dict(self):
        """测试转换为字典"""
        spec = AgentSpec(name="test", provider="openai")
        data = spec.to_dict()
        assert data["name"] == "test"
        assert data["provider"] == "openai"

    def test_yaml_roundtrip(self):
        """测试 YAML 读写"""
        spec = AgentSpec(
            name="yaml-test",
            description="Test agent",
            provider="anthropic",
            model="claude-sonnet-4",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            spec.to_yaml(f.name)
            loaded = AgentSpec.from_yaml(f.name)

        assert loaded.name == spec.name
        assert loaded.description == spec.description
        assert loaded.provider == spec.provider
        os.unlink(f.name)


class TestAgentHooks:
    """AgentHooks 测试"""

    def test_default_hooks(self):
        """测试默认钩子为 None"""
        hooks = AgentHooks()
        assert hooks.on_start is None
        assert hooks.on_step is None
        assert hooks.on_tool_call is None

    def test_custom_hooks(self):
        """测试自定义钩子"""
        on_start = lambda: print("started")
        hooks = AgentHooks(on_start=on_start)
        assert hooks.on_start is on_start


class TestAgentBuilder:
    """AgentBuilder 测试"""

    def test_basic_builder(self):
        """测试基本构建器"""
        builder = AgentBuilder("test-agent")
        assert builder._name == "test-agent"

    def test_fluent_api(self):
        """测试流畅 API"""
        builder = (
            AgentBuilder("fluent-test")
            .with_description("A test agent")
            .with_llm(provider="openai", model="gpt-4o")
            .with_system_prompt("You are helpful.")
            .with_config(max_steps=100, stream=False)
        )

        assert builder._name == "fluent-test"
        assert builder._description == "A test agent"
        assert builder._provider == "openai"
        assert builder._model == "gpt-4o"
        assert builder._system_prompt == "You are helpful."
        assert builder._max_steps == 100
        assert builder._stream is False

    def test_with_tools(self):
        """测试添加工具"""
        mock_tool = MagicMock()
        mock_tool.name = "mock_tool"

        builder = AgentBuilder("tool-test").with_tool(mock_tool).with_tools([mock_tool])

        assert len(builder._tools) == 2

    def test_with_hooks(self):
        """测试添加钩子"""
        on_start = lambda: None
        on_complete = lambda x: None

        builder = AgentBuilder("hook-test").with_hooks(on_start=on_start, on_complete=on_complete)

        assert builder._hooks.on_start is on_start
        assert builder._hooks.on_complete is on_complete

    def test_from_spec(self):
        """测试从 Spec 加载"""
        spec = AgentSpec(
            name="spec-agent",
            provider="openai",
            model="gpt-4",
            max_steps=200,
        )

        builder = AgentBuilder().from_spec(spec)

        assert builder._name == "spec-agent"
        assert builder._provider == "openai"
        assert builder._model == "gpt-4"
        assert builder._max_steps == 200

    def test_to_spec(self):
        """测试导出为 Spec"""
        builder = (
            AgentBuilder("export-test")
            .with_description("Export test")
            .with_llm(provider="anthropic", model="claude-3")
            .with_config(max_steps=75)
        )

        spec = builder.to_spec()

        assert spec.name == "export-test"
        assert spec.description == "Export test"
        assert spec.provider == "anthropic"
        assert spec.model == "claude-3"
        assert spec.max_steps == 75

    def test_with_system_prompt_file(self):
        """测试从文件加载系统提示词"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("You are a test assistant.")
            f.flush()

            builder = AgentBuilder("prompt-test").with_system_prompt_file(f.name)

        assert builder._system_prompt == "You are a test assistant."
        os.unlink(f.name)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_with_env_key(self):
        """测试使用环境变量 API Key 构建"""
        builder = AgentBuilder("env-test").with_llm(provider="anthropic", model="claude-3")

        # 不应该抛出异常
        llm_client = builder._create_llm_client()
        assert llm_client is not None

    def test_build_without_key_raises(self):
        """测试没有 API Key 时抛出异常"""
        # 清除可能存在的环境变量
        with patch.dict(os.environ, {}, clear=True):
            builder = AgentBuilder("no-key-test").with_llm(provider="anthropic")

            with pytest.raises(ValueError, match="API key not provided"):
                builder._create_llm_client()

    def test_with_llm_client(self):
        """测试直接传入 LLM 客户端"""
        mock_client = MagicMock()

        builder = AgentBuilder("client-test").with_llm(client=mock_client)

        assert builder._llm_client is mock_client


class TestCreateAgent:
    """create_agent 便捷函数测试"""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_create_agent_basic(self):
        """测试基本创建"""
        agent = create_agent(
            name="quick-agent",
            provider="anthropic",
            model="claude-3",
            system_prompt="Hello",
        )

        assert agent is not None
        assert agent.config.stream is True

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_create_agent_with_config(self):
        """测试带配置创建"""
        agent = create_agent(
            name="config-agent",
            max_steps=100,
            stream=False,
            parallel_tools=False,
        )

        assert agent.config.max_steps == 100
        assert agent.config.stream is False
        assert agent.config.parallel_tools is False
