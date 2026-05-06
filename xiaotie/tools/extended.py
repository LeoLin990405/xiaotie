"""
扩展工具模块

包含各种实用工具，扩展了基本工具集
"""

import json
import subprocess
from typing import List, Optional

from ..permissions import PermissionManager
from ..schema import ToolResult
from .base import Tool


class SystemInfoTool(Tool):
    """系统信息工具"""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return "获取系统信息，包括操作系统、CPU、内存等"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "detail_level": {
                    "type": "string",
                    "enum": ["basic", "detailed"],
                    "description": "信息详细程度，默认为 basic",
                    "default": "basic",
                }
            },
            "required": [],
        }

    async def execute(self, detail_level: str = "basic") -> ToolResult:
        try:
            import platform

            import psutil

            info = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "node": platform.node(),
            }

            if detail_level == "detailed":
                info.update(
                    {
                        "cpu_count": psutil.cpu_count(logical=True),
                        "cpu_percent": psutil.cpu_percent(interval=1),
                        "memory_total": psutil.virtual_memory().total,
                        "memory_available": psutil.virtual_memory().available,
                        "disk_usage": {
                            part.mountpoint: {
                                "total": part.total,
                                "used": part.used,
                                "free": part.free,
                            }
                            for part in psutil.disk_partitions()
                        },
                    }
                )

            return ToolResult(success=True, content=json.dumps(info, indent=2, ensure_ascii=False))
        except Exception as e:
            return ToolResult(success=False, error=f"获取系统信息失败: {str(e)}")


class ProcessManagerTool(Tool):
    """进程管理工具（带权限检查）"""

    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        super().__init__()
        self._permission_manager = permission_manager or PermissionManager(
            auto_approve_low_risk=True,
            interactive=False,
        )

    @property
    def name(self) -> str:
        return "process_manager"

    @property
    def description(self) -> str:
        return "管理进程，可以列出、启动、停止进程"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "start", "stop", "status"],
                    "description": "操作类型",
                },
                "process_name": {
                    "type": "string",
                    "description": "进程名称（用于start/stop/status操作）",
                },
                "command": {"type": "string", "description": "启动命令（用于start操作）"},
            },
            "required": ["action"],
        }

    async def execute(
        self, action: str, process_name: Optional[str] = None, command: Optional[str] = None
    ) -> ToolResult:
        try:
            import psutil

            # 对 start/stop 操作进行权限检查
            if action in ("start", "stop"):
                args = {"action": action}
                if command:
                    args["command"] = command
                if process_name:
                    args["process_name"] = process_name

                allowed, reason = await self._permission_manager.check_permission(
                    "process_manager", args
                )
                if not allowed:
                    return ToolResult(success=False, error=f"权限被拒绝: {reason}")

            if action == "list":
                processes = []
                for proc in psutil.process_iter(["pid", "name", "username"]):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                return ToolResult(
                    success=True,
                    content=json.dumps(processes[:50], indent=2),  # 只返回前50个进程
                )

            elif action == "status" and process_name:
                for proc in psutil.process_iter(["pid", "name", "status"]):
                    if proc.info["name"] == process_name:
                        return ToolResult(
                            success=True,
                            content=f"进程 {process_name} 状态: {proc.info['status']}, PID: {proc.info['pid']}",
                        )
                return ToolResult(success=False, error=f"未找到进程 {process_name}")

            elif action == "start" and command:
                # 启动新进程 - 使用列表形式避免 shell 注入
                import shlex

                process = subprocess.Popen(
                    shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                return ToolResult(success=True, content=f"已启动进程，PID: {process.pid}")

            elif action == "stop" and process_name:
                # 停止进程
                for proc in psutil.process_iter(["pid", "name"]):
                    if proc.info["name"] == process_name:
                        proc.kill()
                        return ToolResult(
                            success=True,
                            content=f"已停止进程 {process_name}，PID: {proc.info['pid']}",
                        )
                return ToolResult(success=False, error=f"未找到进程 {process_name}")

            else:
                return ToolResult(success=False, error="参数不完整或操作不支持")

        except Exception as e:
            return ToolResult(success=False, error=f"进程管理操作失败: {str(e)}")


class NetworkTool(Tool):
    """网络工具"""

    @property
    def name(self) -> str:
        return "network_tool"

    @property
    def description(self) -> str:
        return "执行网络相关的操作，如ping、端口扫描等"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["ping", "port_scan", "netstat"],
                    "description": "网络操作类型",
                },
                "host": {"type": "string", "description": "目标主机（用于ping和port_scan）"},
                "ports": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要扫描的端口列表（用于port_scan）",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self, action: str, host: Optional[str] = None, ports: Optional[List[int]] = None
    ) -> ToolResult:
        try:
            if action == "ping" and host:
                # 使用subprocess执行ping命令
                result = subprocess.run(["ping", "-c", "4", host], capture_output=True, text=True)
                return ToolResult(success=True, content=result.stdout)

            elif action == "netstat":
                # 获取网络连接状态
                import psutil

                connections = psutil.net_connections(kind="inet")
                conn_list = []
                for conn in connections:
                    conn_list.append(
                        {
                            "fd": conn.fd,
                            "family": str(conn.family),
                            "type": str(conn.type),
                            "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                            "raddr": f"{conn.raddr.ip}:{conn.raddr.port}"
                            if conn.raddr and conn.raddr.ip
                            else "",
                            "status": conn.status,
                            "pid": conn.pid,
                        }
                    )
                return ToolResult(success=True, content=json.dumps(conn_list, indent=2))

            elif action == "port_scan" and host and ports:
                # 简单的端口扫描
                open_ports = []
                for port in ports:
                    import socket

                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)  # 1秒超时
                    result = sock.connect_ex((host, port))
                    if result == 0:
                        open_ports.append(port)
                    sock.close()

                return ToolResult(success=True, content=f"主机 {host} 上开放的端口: {open_ports}")

            else:
                return ToolResult(success=False, error="参数不完整或操作不支持")

        except Exception as e:
            return ToolResult(success=False, error=f"网络操作失败: {str(e)}")


# 收集所有扩展工具
EXTENDED_TOOLS = [SystemInfoTool(), ProcessManagerTool(), NetworkTool()]
