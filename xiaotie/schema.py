"""数据模型定义"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class FunctionCall(BaseModel):
    """函数调用"""
    name: str
    arguments: Dict[str, Any]


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    type: str = "function"
    function: FunctionCall


class Message(BaseModel):
    """消息"""
    role: str  # system, user, assistant, tool
    content: Union[str, List[Dict[str, Any]]] = ""
    thinking: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class TokenUsage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = "stop"
    usage: Optional[TokenUsage] = None


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    content: str = ""
    error: Optional[str] = None
