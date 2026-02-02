"""LLM 响应录制和回放模块

用于测试时录制和回放 LLM API 响应，避免真实 API 调用。

使用方式:
```python
from xiaotie.testing import LLMCassette, mock_llm_response

# 方式 1: 使用装饰器
@mock_llm_response("fixtures/hello.yaml")
async def test_hello():
    client = LLMClient(provider="anthropic")
    response = await client.generate([Message(role="user", content="Hello")])
    assert "Hello" in response.content

# 方式 2: 使用上下文管理器
async def test_with_cassette():
    async with LLMCassette("fixtures/chat.yaml") as cassette:
        client = LLMClient(provider="anthropic")
        response = await client.generate([Message(role="user", content="Hi")])
        # 响应会被录制或回放
```
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml


@dataclass
class RecordedRequest:
    """录制的请求"""

    provider: str
    model: str
    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def fingerprint(self) -> str:
        """生成请求指纹用于匹配"""
        data = {
            "provider": self.provider,
            "model": self.model,
            "messages": self.messages,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:16]


@dataclass
class RecordedResponse:
    """录制的响应"""

    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None
    model: str = ""
    stop_reason: str = "end_turn"


@dataclass
class CassetteRecord:
    """单条录制记录"""

    request: RecordedRequest
    response: RecordedResponse


@dataclass
class Cassette:
    """录制带 (cassette)"""

    name: str
    records: List[CassetteRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.metadata:
            self.metadata = {
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
            }

    def find_response(self, request: RecordedRequest) -> Optional[RecordedResponse]:
        """根据请求查找响应"""
        fingerprint = request.fingerprint
        for record in self.records:
            if record.request.fingerprint == fingerprint:
                return record.response
        return None

    def add_record(self, request: RecordedRequest, response: RecordedResponse) -> None:
        """添加录制记录"""
        self.records.append(CassetteRecord(request=request, response=response))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "metadata": self.metadata,
            "records": [
                {
                    "request": asdict(r.request),
                    "response": asdict(r.response),
                }
                for r in self.records
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cassette":
        """从字典创建"""
        records = []
        for r in data.get("records", []):
            request = RecordedRequest(**r["request"])
            response = RecordedResponse(**r["response"])
            records.append(CassetteRecord(request=request, response=response))

        return cls(
            name=data.get("name", "unnamed"),
            records=records,
            metadata=data.get("metadata", {}),
        )

    def save(self, path: Union[str, Path]) -> None:
        """保存到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Cassette":
        """从文件加载"""
        path = Path(path)
        if not path.exists():
            return cls(name=path.stem)

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data or {})


class LLMCassette:
    """LLM 响应录制/回放上下文管理器"""

    def __init__(
        self,
        cassette_path: Union[str, Path],
        record_mode: str = "once",  # "once", "new_episodes", "none", "all"
    ):
        self.cassette_path = Path(cassette_path)
        self.record_mode = record_mode
        self.cassette: Optional[Cassette] = None
        self._original_generate: Optional[Callable] = None

    async def __aenter__(self) -> "LLMCassette":
        """进入上下文"""
        self.cassette = Cassette.load(self.cassette_path)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文"""
        if self.cassette and self.record_mode != "none":
            self.cassette.save(self.cassette_path)

    def get_response(self, request: RecordedRequest) -> Optional[RecordedResponse]:
        """获取录制的响应"""
        if self.cassette:
            return self.cassette.find_response(request)
        return None

    def record(self, request: RecordedRequest, response: RecordedResponse) -> None:
        """录制响应"""
        if self.cassette and self.record_mode in ("once", "new_episodes", "all"):
            # "once" 模式下只录制新请求
            if self.record_mode == "once":
                existing = self.cassette.find_response(request)
                if existing:
                    return

            self.cassette.add_record(request, response)


def mock_llm_response(cassette_path: Union[str, Path], record_mode: str = "once"):
    """装饰器：使用录制的响应"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with LLMCassette(cassette_path, record_mode):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# 预定义的测试响应
MOCK_RESPONSES: Dict[str, RecordedResponse] = {
    "hello": RecordedResponse(
        content="Hello! How can I help you today?",
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 10, "output_tokens": 15},
    ),
    "code": RecordedResponse(
        content='```python\ndef hello():\n    print("Hello, World!")\n```',
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 20, "output_tokens": 30},
    ),
    "tool_call": RecordedResponse(
        content="",
        tool_calls=[
            {
                "id": "call_123",
                "name": "read_file",
                "arguments": {"path": "/tmp/test.txt"},
            }
        ],
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 25, "output_tokens": 20},
    ),
    "thinking": RecordedResponse(
        content="The answer is 42.",
        thinking="Let me think about this step by step...",
        model="claude-sonnet-4-20250514",
        usage={"input_tokens": 30, "output_tokens": 50},
    ),
}


def get_mock_response(key: str) -> RecordedResponse:
    """获取预定义的模拟响应"""
    return MOCK_RESPONSES.get(key, MOCK_RESPONSES["hello"])


class MockLLMClient:
    """模拟 LLM 客户端用于测试"""

    def __init__(
        self,
        responses: Optional[List[RecordedResponse]] = None,
        default_response: Optional[RecordedResponse] = None,
    ):
        self.responses = responses or []
        self.default_response = default_response or MOCK_RESPONSES["hello"]
        self.call_count = 0
        self.call_history: List[Dict[str, Any]] = []

    async def generate(
        self,
        messages: List[Any],
        tools: Optional[List[Any]] = None,
    ) -> "MockLLMResponse":
        """模拟生成响应"""
        self.call_history.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            response = self.default_response

        self.call_count += 1

        return MockLLMResponse(
            content=response.content,
            thinking=response.thinking,
            tool_calls=response.tool_calls,
            usage=response.usage or {},
            model=response.model,
            stop_reason=response.stop_reason,
        )


@dataclass
class MockLLMResponse:
    """模拟 LLM 响应"""

    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = "mock-model"
    stop_reason: str = "end_turn"

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
