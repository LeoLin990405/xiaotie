"""工作流模块

提供端到端的自动化工作流，编排多个工具协同完成复杂任务。
"""

from .miniapp_capture import MiniAppCaptureWorkflow, CaptureConfig

__all__ = [
    "MiniAppCaptureWorkflow",
    "CaptureConfig",
]
