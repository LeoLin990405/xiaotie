"""
代码执行沙箱模块

提供安全的代码执行环境，支持多种运行时：
- subprocess: 本地进程隔离（默认）
- docker: Docker 容器隔离
- 未来: firecracker, wasm

使用示例:
    from xiaotie.sandbox import Sandbox, SandboxConfig

    # 基础用法
    sandbox = Sandbox()
    result = sandbox.execute("print('Hello, World!')")
    print(result.stdout)  # Hello, World!

    # 配置选项
    config = SandboxConfig(
        timeout=30,
        memory_limit_mb=256,
        runtime="subprocess",
    )
    sandbox = Sandbox(config)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
import subprocess
import tempfile
import os
import sys
import signal
import resource
import threading
import time
from pathlib import Path


class SandboxRuntime(Enum):
    """沙箱运行时类型"""
    SUBPROCESS = "subprocess"
    DOCKER = "docker"


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    KILLED = "killed"


@dataclass
class SandboxConfig:
    """沙箱配置"""
    runtime: str = "subprocess"
    timeout: float = 30.0  # 秒
    memory_limit_mb: int = 256  # MB
    cpu_limit: float = 1.0  # CPU 核心数
    network_enabled: bool = False
    allowed_imports: Optional[List[str]] = None  # None = 允许所有
    blocked_imports: Optional[List[str]] = None  # 阻止的模块
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Docker 特定配置
    docker_image: str = "python:3.9-slim"
    docker_volumes: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.blocked_imports is None:
            # 默认阻止危险模块
            self.blocked_imports = [
                "os.system",
                "subprocess",
                "shutil.rmtree",
                "ctypes",
                "__builtins__.__import__",
            ]


@dataclass
class ExecutionResult:
    """执行结果"""
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time: float = 0.0
    memory_used_mb: float = 0.0
    exit_code: int = 0
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_value": self.return_value,
            "execution_time": self.execution_time,
            "memory_used_mb": self.memory_used_mb,
            "exit_code": self.exit_code,
            "error_message": self.error_message,
        }


class SandboxError(Exception):
    """沙箱错误基类"""
    pass


class TimeoutError(SandboxError):
    """执行超时"""
    pass


class MemoryExceededError(SandboxError):
    """内存超限"""
    pass


class SecurityError(SandboxError):
    """安全违规"""
    pass


class ImportChecker:
    """导入检查器"""

    def __init__(self, allowed: Optional[List[str]] = None,
                 blocked: Optional[List[str]] = None):
        self.allowed = set(allowed) if allowed else None
        self.blocked = set(blocked) if blocked else set()

    def check_code(self, code: str) -> List[str]:
        """检查代码中的导入，返回违规列表"""
        violations = []

        # 简单的导入检测
        import ast
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_allowed(alias.name):
                        violations.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    if not self._is_allowed(full_name):
                        violations.append(f"from {module} import {alias.name}")

        return violations

    def _is_allowed(self, module: str) -> bool:
        """检查模块是否允许"""
        # 检查是否在阻止列表
        for blocked in self.blocked:
            if module.startswith(blocked) or blocked.startswith(module):
                return False

        # 如果有白名单，检查是否在白名单
        if self.allowed is not None:
            for allowed in self.allowed:
                if module.startswith(allowed) or allowed.startswith(module):
                    return True
            return False

        return True


class SubprocessExecutor:
    """子进程执行器"""

    def __init__(self, config: SandboxConfig):
        self.config = config

    def execute(self, code: str) -> ExecutionResult:
        """在子进程中执行代码"""
        start_time = time.time()

        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False
        ) as f:
            # 包装代码以捕获输出
            wrapped_code = self._wrap_code(code)
            f.write(wrapped_code)
            temp_file = f.name

        try:
            # 准备环境变量
            env = os.environ.copy()
            env.update(self.config.env_vars)

            # 执行
            process = subprocess.Popen(
                [sys.executable, temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=self.config.working_dir,
                preexec_fn=self._set_limits if sys.platform != 'win32' else None,
            )

            try:
                stdout, stderr = process.communicate(
                    timeout=self.config.timeout
                )
                execution_time = time.time() - start_time

                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')

                if process.returncode == 0:
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        stdout=stdout_str,
                        stderr=stderr_str,
                        execution_time=execution_time,
                        exit_code=0,
                    )
                else:
                    return ExecutionResult(
                        status=ExecutionStatus.ERROR,
                        stdout=stdout_str,
                        stderr=stderr_str,
                        execution_time=execution_time,
                        exit_code=process.returncode,
                        error_message=stderr_str or f"Exit code: {process.returncode}",
                    )

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    execution_time=self.config.timeout,
                    error_message=f"Execution timed out after {self.config.timeout}s",
                )

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except OSError:
                pass

    def _wrap_code(self, code: str) -> str:
        """包装代码"""
        return f'''
import sys
import traceback

try:
{self._indent_code(code)}
except Exception as e:
    print(traceback.format_exc(), file=sys.stderr)
    sys.exit(1)
'''

    def _indent_code(self, code: str) -> str:
        """缩进代码"""
        lines = code.split('\n')
        return '\n'.join('    ' + line for line in lines)

    def _set_limits(self):
        """设置资源限制 (Unix only)"""
        # 内存限制
        memory_bytes = self.config.memory_limit_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, resource.error):
            pass

        # CPU 时间限制
        cpu_seconds = int(self.config.timeout) + 5
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        except (ValueError, resource.error):
            pass


class DockerExecutor:
    """Docker 执行器"""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._check_docker()

    def _check_docker(self):
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise SandboxError("Docker is not available")
        except FileNotFoundError:
            raise SandboxError("Docker is not installed")
        except subprocess.TimeoutExpired:
            raise SandboxError("Docker check timed out")

    def execute(self, code: str) -> ExecutionResult:
        """在 Docker 容器中执行代码"""
        start_time = time.time()

        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 写入代码文件
            code_file = Path(temp_dir) / "code.py"
            code_file.write_text(code)

            # 构建 Docker 命令
            cmd = self._build_docker_command(temp_dir)

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                try:
                    stdout, stderr = process.communicate(
                        timeout=self.config.timeout + 10  # 额外时间用于容器启动
                    )
                    execution_time = time.time() - start_time

                    stdout_str = stdout.decode('utf-8', errors='replace')
                    stderr_str = stderr.decode('utf-8', errors='replace')

                    if process.returncode == 0:
                        return ExecutionResult(
                            status=ExecutionStatus.SUCCESS,
                            stdout=stdout_str,
                            stderr=stderr_str,
                            execution_time=execution_time,
                            exit_code=0,
                        )
                    elif process.returncode == 137:  # OOM killed
                        return ExecutionResult(
                            status=ExecutionStatus.MEMORY_EXCEEDED,
                            stdout=stdout_str,
                            stderr=stderr_str,
                            execution_time=execution_time,
                            exit_code=137,
                            error_message="Container killed due to memory limit",
                        )
                    else:
                        return ExecutionResult(
                            status=ExecutionStatus.ERROR,
                            stdout=stdout_str,
                            stderr=stderr_str,
                            execution_time=execution_time,
                            exit_code=process.returncode,
                            error_message=stderr_str or f"Exit code: {process.returncode}",
                        )

                except subprocess.TimeoutExpired:
                    # 强制停止容器
                    subprocess.run(
                        ["docker", "kill", f"sandbox_{os.getpid()}"],
                        capture_output=True,
                    )
                    process.kill()
                    process.wait()
                    return ExecutionResult(
                        status=ExecutionStatus.TIMEOUT,
                        execution_time=self.config.timeout,
                        error_message=f"Execution timed out after {self.config.timeout}s",
                    )

            except Exception as e:
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    execution_time=time.time() - start_time,
                    error_message=str(e),
                )

    def _build_docker_command(self, temp_dir: str) -> List[str]:
        """构建 Docker 命令"""
        cmd = [
            "docker", "run",
            "--rm",
            f"--name=sandbox_{os.getpid()}",
            f"--memory={self.config.memory_limit_mb}m",
            f"--cpus={self.config.cpu_limit}",
            "--pids-limit=100",
            "--read-only",
            "--tmpfs=/tmp:size=64m",
            "-v", f"{temp_dir}:/code:ro",
            "-w", "/code",
        ]

        # 网络设置
        if not self.config.network_enabled:
            cmd.append("--network=none")

        # 环境变量
        for key, value in self.config.env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

        # 额外卷
        for host_path, container_path in self.config.docker_volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}:ro"])

        # 镜像和命令
        cmd.extend([
            self.config.docker_image,
            "python", "/code/code.py",
        ])

        return cmd


class Sandbox:
    """代码执行沙箱"""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._import_checker = ImportChecker(
            allowed=self.config.allowed_imports,
            blocked=self.config.blocked_imports,
        )
        self._executor = self._create_executor()
        self._callbacks: List[Callable[[ExecutionResult], None]] = []

    def _create_executor(self):
        """创建执行器"""
        runtime = SandboxRuntime(self.config.runtime)
        if runtime == SandboxRuntime.SUBPROCESS:
            return SubprocessExecutor(self.config)
        elif runtime == SandboxRuntime.DOCKER:
            return DockerExecutor(self.config)
        else:
            raise ValueError(f"Unknown runtime: {self.config.runtime}")

    def on_complete(self, callback: Callable[[ExecutionResult], None]) -> "Sandbox":
        """注册执行完成回调"""
        self._callbacks.append(callback)
        return self

    def execute(self, code: str, check_imports: bool = True) -> ExecutionResult:
        """执行代码"""
        # 检查导入
        if check_imports:
            violations = self._import_checker.check_code(code)
            if violations:
                result = ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"Blocked imports: {', '.join(violations)}",
                )
                self._notify_callbacks(result)
                return result

        # 执行代码
        result = self._executor.execute(code)

        # 通知回调
        self._notify_callbacks(result)

        return result

    def execute_file(self, file_path: str, check_imports: bool = True) -> ExecutionResult:
        """执行文件"""
        path = Path(file_path)
        if not path.exists():
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=f"File not found: {file_path}",
            )

        code = path.read_text()
        return self.execute(code, check_imports=check_imports)

    def _notify_callbacks(self, result: ExecutionResult):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass


class SandboxPool:
    """沙箱池，用于并发执行"""

    def __init__(self, config: Optional[SandboxConfig] = None,
                 pool_size: int = 4):
        self.config = config or SandboxConfig()
        self.pool_size = pool_size
        self._sandboxes: List[Sandbox] = []
        self._lock = threading.Lock()
        self._available: List[Sandbox] = []

        # 初始化沙箱池
        for _ in range(pool_size):
            sandbox = Sandbox(self.config)
            self._sandboxes.append(sandbox)
            self._available.append(sandbox)

    def acquire(self) -> Optional[Sandbox]:
        """获取一个可用的沙箱"""
        with self._lock:
            if self._available:
                return self._available.pop()
            return None

    def release(self, sandbox: Sandbox):
        """释放沙箱"""
        with self._lock:
            if sandbox in self._sandboxes and sandbox not in self._available:
                self._available.append(sandbox)

    def execute(self, code: str, timeout: float = 30.0) -> ExecutionResult:
        """执行代码，自动管理沙箱"""
        sandbox = self.acquire()
        if sandbox is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message="No available sandbox in pool",
            )

        try:
            return sandbox.execute(code)
        finally:
            self.release(sandbox)

    @property
    def available_count(self) -> int:
        """可用沙箱数量"""
        with self._lock:
            return len(self._available)

    @property
    def total_count(self) -> int:
        """总沙箱数量"""
        return len(self._sandboxes)
