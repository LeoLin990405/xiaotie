"""
小铁 (XiaoTie) - 轻量级 AI Agent 框架

基于 Mini-Agent 架构复现，支持多 LLM Provider 和工具调用。
"""

__version__ = "0.1.0"
__author__ = "Leo"

from .agent import Agent
from .schema import Message, ToolCall, LLMResponse, ToolResult

__all__ = ["Agent", "Message", "ToolCall", "LLMResponse", "ToolResult"]
