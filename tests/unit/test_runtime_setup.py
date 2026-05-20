"""共享运行时装配测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from xiaotie.config import Config
from xiaotie.runtime_setup import create_tools, setup_runtime


def _make_config(**overrides) -> Config:
    data = {
        "llm": {
            "api_key": "test-key",
            "provider": "mimo",
            "model": "mimo-v2-pro",
        },
        "agent": {
            "workspace_dir": "./workspace",
            "max_steps": 10,
        },
        "tools": {},
    }
    for key, value in overrides.items():
        data[key] = value
    return Config.model_validate(data)


def test_create_tools_respects_flags(tmp_path, monkeypatch):
    monkeypatch.setattr("xiaotie.runtime_setup.EXTENDED_TOOLS", [])
    config = _make_config(
        tools={
            "enable_file_tools": True,
            "enable_bash": True,
            "enable_python": False,
            "enable_calculator": False,
            "enable_git": False,
            "enable_web_tools": False,
            "enable_code_analysis": False,
        }
    )

    tools = create_tools(config, tmp_path)
    names = [tool.name for tool in tools]

    assert names == ["read_file", "write_file", "edit_file", "bash"]


@pytest.mark.asyncio
async def test_setup_runtime_collects_plugin_and_mcp_tools(monkeypatch, tmp_path):
    monkeypatch.setattr("xiaotie.runtime_setup.EXTENDED_TOOLS", [])

    class DummyPluginManager:
        def load_all_plugins(self):
            return [SimpleNamespace(name="plugin_tool")]

    async def fake_load_mcp_tools(config, status_reporter=None):
        return [SimpleNamespace(name="mcp_tool")]

    monkeypatch.setattr("xiaotie.runtime_setup.PluginManager", DummyPluginManager)
    monkeypatch.setattr("xiaotie.runtime_setup.load_mcp_tools", fake_load_mcp_tools)

    config = _make_config(agent={"workspace_dir": str(tmp_path), "max_steps": 10})
    setup = await setup_runtime(config, stream=False, thinking=False, quiet=True)

    names = [tool.name for tool in setup.runtime.tools]
    assert "plugin_tool" in names
    assert "mcp_tool" in names
    assert setup.workspace == tmp_path
