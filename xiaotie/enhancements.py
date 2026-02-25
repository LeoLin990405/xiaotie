"""
功能增强模块

包含小铁框架的各种功能增强
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional

from .cache import get_global_cache, cache_result
from .logging import get_logger


async def get_system_info(detail_level: str = "basic") -> Dict[str, Any]:
    """
    获取系统信息
    """
    logger = get_logger()
    logger.info(f"获取系统信息，详细程度: {detail_level}")
    
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
            "python_version": platform.python_version(),
        }
        
        if detail_level == "detailed":
            disk_usage = {}
            for part in psutil.disk_partitions():
                if os.path.exists(part.mountpoint):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disk_usage[part.mountpoint] = {
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": (usage.used / usage.total) * 100 if usage.total > 0 else 0
                        }
                    except (OSError, PermissionError):
                        # 忽略无法访问的分区
                        continue
            
            info.update({
                "cpu_count": psutil.cpu_count(logical=True),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": disk_usage,
                "boot_time": psutil.boot_time(),
            })
        
        logger.debug("系统信息获取成功")
        return info
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        raise


async def manage_process(action: str, process_name: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
    """
    管理进程
    """
    logger = get_logger()
    logger.info(f"执行进程管理操作: {action}")
    
    try:
        import psutil
        import subprocess
        
        if action == "list":
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'status']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return {"success": True, "processes": processes[:100]}  # 只返回前100个进程
            
        elif action == "status" and process_name:
            for proc in psutil.process_iter(['pid', 'name', 'status']):
                if proc.info['name'] == process_name:
                    return {
                        "success": True, 
                        "process": proc.info
                    }
            return {"success": False, "error": f"未找到进程 {process_name}"}
            
        elif action == "start" and command:
            # 启动新进程
            process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return {
                "success": True,
                "message": f"已启动进程",
                "pid": process.pid
            }
            
        elif action == "stop" and process_name:
            # 停止进程
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == process_name:
                    proc.kill()
                    return {
                        "success": True,
                        "message": f"已停止进程 {process_name}",
                        "pid": proc.info['pid']
                    }
            return {"success": False, "error": f"未找到进程 {process_name}"}
            
        else:
            return {"success": False, "error": "参数不完整或操作不支持"}
                
    except Exception as e:
        logger.error(f"进程管理操作失败: {str(e)}")
        return {"success": False, "error": f"进程管理操作失败: {str(e)}"}


async def network_operation(action: str, host: Optional[str] = None, ports: Optional[list] = None) -> Dict[str, Any]:
    """
    执行网络操作
    """
    logger = get_logger()
    logger.info(f"执行网络操作: {action}")
    
    try:
        if action == "ping" and host:
            import subprocess
            # 使用subprocess执行ping命令
            result = subprocess.run(["ping", "-c", "4", host], capture_output=True, text=True, timeout=10)
            return {
                "success": True,
                "output": result.stdout,
                "error_output": result.stderr,
                "return_code": result.returncode
            }
        
        elif action == "netstat":
            import psutil
            connections = psutil.net_connections(kind='inet')
            conn_list = []
            for conn in connections:
                conn_list.append({
                    "fd": conn.fd,
                    "family": str(conn.family),
                    "type": str(conn.type),
                    "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr and hasattr(conn.laddr, 'port') else "",
                    "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr and conn.raddr.ip else "",
                    "status": conn.status,
                    "pid": conn.pid
                })
            return {"success": True, "connections": conn_list}
        
        elif action == "port_scan" and host and ports:
            # 简单的端口扫描
            import socket
            open_ports = []
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1秒超时
                result = sock.connect_ex((host, port))
                if result == 0:
                    open_ports.append(port)
                sock.close()
            
            return {
                "success": True,
                "host": host,
                "ports_scanned": len(ports),
                "open_ports": open_ports
            }
        
        else:
            return {"success": False, "error": "参数不完整或操作不支持"}
                
    except Exception as e:
        logger.error(f"网络操作失败: {str(e)}")
        return {"success": False, "error": f"网络操作失败: {str(e)}"}


async def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息
    """
    logger = get_logger()
    logger.info("获取缓存统计信息")
    
    try:
        cache = get_global_cache()
        size = await cache.size()
        keys = await cache.keys()
        
        stats = {
            "size": size,
            "max_size": cache.max_size,
            "keys": keys,
            "default_ttl": cache.default_ttl
        }
        
        logger.debug("缓存统计信息获取成功")
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"获取缓存统计信息失败: {str(e)}")
        return {"success": False, "error": f"获取缓存统计信息失败: {str(e)}"}


async def clear_cache() -> Dict[str, Any]:
    """
    清空缓存
    """
    logger = get_logger()
    logger.info("清空缓存")
    
    try:
        cache = get_global_cache()
        await cache.clear()
        
        logger.info("缓存清空成功")
        return {"success": True, "message": "缓存已清空"}
    except Exception as e:
        logger.error(f"清空缓存失败: {str(e)}")
        return {"success": False, "error": f"清空缓存失败: {str(e)}"}


# 为常用函数添加缓存装饰器
async def get_cached_system_info(detail_level: str = "basic") -> Dict[str, Any]:
    """
    获取系统信息（带缓存）
    """
    # 生成缓存键
    cache_key = f"system_info:{detail_level}"
    cache = get_global_cache()
    
    # 尝试从缓存获取
    cached_result = await cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # 获取实际结果并缓存
    result = await get_system_info(detail_level)
    await cache.set(cache_key, result, ttl=300)  # 5分钟TTL
    return result