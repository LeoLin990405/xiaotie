import asyncio
from typing import Dict

class SessionState:
    """会话状态管理 - 防止并发冲突"""

    def __init__(self):
        self._busy_sessions: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, session_id: str) -> bool:
        """获取会话锁"""
        async with self._lock:
            if session_id in self._busy_sessions:
                return False
            self._busy_sessions[session_id] = asyncio.Event()
            return True

    async def release(self, session_id: str):
        """释放会话锁"""
        async with self._lock:
            if session_id in self._busy_sessions:
                self._busy_sessions[session_id].set()
                del self._busy_sessions[session_id]

    def is_busy(self, session_id: str) -> bool:
        """检查会话是否忙碌"""
        return session_id in self._busy_sessions

    async def wait_for_release(self, session_id: str, timeout: float = 30.0) -> bool:
        """等待会话释放"""
        if session_id not in self._busy_sessions:
            return True
        try:
            await asyncio.wait_for(self._busy_sessions[session_id].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

# 全局会话状态
_session_state = SessionState()
