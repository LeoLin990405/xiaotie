"""pytest 配置"""

import asyncio
import sys
from pathlib import Path

import pytest

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def workspace_dir(tmp_path):
    """创建临时工作目录"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return str(workspace)


@pytest.fixture
def sample_python_file(workspace_dir):
    """创建示例 Python 文件"""
    file_path = Path(workspace_dir) / "sample.py"
    file_path.write_text('''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator."""

    def __init__(self):
        self.result = 0

    def add(self, x: int) -> "Calculator":
        self.result += x
        return self

    def subtract(self, x: int) -> "Calculator":
        self.result -= x
        return self
''')
    return str(file_path)


@pytest.fixture
def sample_config(workspace_dir):
    """创建示例配置文件"""
    config_dir = Path(workspace_dir) / "config"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text('''
api_key: test-api-key
api_base: https://api.example.com
model: test-model
provider: openai
''')
    return str(config_file)


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应"""
    from xiaotie.schema import LLMResponse, Message

    return LLMResponse(
        message=Message(role="assistant", content="Hello! How can I help you?"),
        tool_calls=[],
        thinking=None,
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    )


@pytest.fixture
def mock_tool_result():
    """模拟工具结果"""
    from xiaotie.schema import ToolResult

    return ToolResult(
        success=True,
        content="Tool executed successfully",
    )
