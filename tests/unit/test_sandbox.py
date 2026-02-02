"""
代码执行沙箱测试
"""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from xiaotie.sandbox import (
    Sandbox,
    SandboxConfig,
    SandboxRuntime,
    ExecutionStatus,
    ExecutionResult,
    ImportChecker,
    SubprocessExecutor,
    SandboxPool,
    SandboxError,
)


class TestSandboxConfig:
    """测试沙箱配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = SandboxConfig()
        assert config.runtime == "subprocess"
        assert config.timeout == 30.0
        assert config.memory_limit_mb == 256
        assert config.network_enabled is False
        assert config.blocked_imports is not None

    def test_custom_config(self):
        """测试自定义配置"""
        config = SandboxConfig(
            runtime="docker",
            timeout=60.0,
            memory_limit_mb=512,
            network_enabled=True,
        )
        assert config.runtime == "docker"
        assert config.timeout == 60.0
        assert config.memory_limit_mb == 512
        assert config.network_enabled is True

    def test_default_blocked_imports(self):
        """测试默认阻止的导入"""
        config = SandboxConfig()
        assert "subprocess" in config.blocked_imports
        assert "os.system" in config.blocked_imports


class TestExecutionResult:
    """测试执行结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="Hello",
            execution_time=0.5,
        )
        assert result.success is True
        assert result.stdout == "Hello"

    def test_error_result(self):
        """测试错误结果"""
        result = ExecutionResult(
            status=ExecutionStatus.ERROR,
            error_message="Something went wrong",
        )
        assert result.success is False
        assert result.error_message == "Something went wrong"

    def test_to_dict(self):
        """测试转换为字典"""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            stdout="output",
            execution_time=1.0,
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["stdout"] == "output"
        assert d["execution_time"] == 1.0


class TestImportChecker:
    """测试导入检查器"""

    def test_no_restrictions(self):
        """测试无限制"""
        checker = ImportChecker()
        code = "import json\nimport os"
        violations = checker.check_code(code)
        assert len(violations) == 0

    def test_blocked_import(self):
        """测试阻止的导入"""
        checker = ImportChecker(blocked=["subprocess"])
        code = "import subprocess"
        violations = checker.check_code(code)
        assert len(violations) == 1
        assert "subprocess" in violations[0]

    def test_allowed_import(self):
        """测试允许的导入"""
        checker = ImportChecker(allowed=["json", "math"])
        code = "import json\nimport math"
        violations = checker.check_code(code)
        assert len(violations) == 0

    def test_not_allowed_import(self):
        """测试不在白名单的导入"""
        checker = ImportChecker(allowed=["json"])
        code = "import os"
        violations = checker.check_code(code)
        assert len(violations) == 1

    def test_from_import(self):
        """测试 from import"""
        checker = ImportChecker(blocked=["os.path"])
        code = "from os import path"
        violations = checker.check_code(code)
        assert len(violations) == 1

    def test_syntax_error_code(self):
        """测试语法错误的代码"""
        checker = ImportChecker()
        code = "import json\nthis is not valid python"
        violations = checker.check_code(code)
        # 语法错误时返回空列表
        assert len(violations) == 0


class TestSubprocessExecutor:
    """测试子进程执行器"""

    def test_simple_execution(self):
        """测试简单执行"""
        config = SandboxConfig(timeout=10.0)
        executor = SubprocessExecutor(config)
        result = executor.execute("print('Hello, World!')")
        assert result.status == ExecutionStatus.SUCCESS
        assert "Hello, World!" in result.stdout

    def test_execution_with_error(self):
        """测试执行错误"""
        config = SandboxConfig(timeout=10.0)
        executor = SubprocessExecutor(config)
        result = executor.execute("raise ValueError('test error')")
        assert result.status == ExecutionStatus.ERROR
        assert "ValueError" in result.stderr

    def test_execution_timeout(self):
        """测试执行超时"""
        config = SandboxConfig(timeout=1.0)
        executor = SubprocessExecutor(config)
        result = executor.execute("import time; time.sleep(10)")
        assert result.status == ExecutionStatus.TIMEOUT

    def test_multiline_code(self):
        """测试多行代码"""
        config = SandboxConfig(timeout=10.0)
        executor = SubprocessExecutor(config)
        code = """
x = 1
y = 2
print(x + y)
"""
        result = executor.execute(code)
        assert result.status == ExecutionStatus.SUCCESS
        assert "3" in result.stdout

    def test_execution_with_env_vars(self):
        """测试环境变量"""
        config = SandboxConfig(
            timeout=10.0,
            env_vars={"TEST_VAR": "test_value"},
        )
        executor = SubprocessExecutor(config)
        code = "import os; print(os.environ.get('TEST_VAR', ''))"
        result = executor.execute(code)
        assert result.status == ExecutionStatus.SUCCESS
        assert "test_value" in result.stdout


class TestSandbox:
    """测试沙箱"""

    def test_create_sandbox(self):
        """测试创建沙箱"""
        sandbox = Sandbox()
        assert sandbox.config is not None
        assert sandbox.config.runtime == "subprocess"

    def test_create_sandbox_with_config(self):
        """测试使用配置创建沙箱"""
        config = SandboxConfig(timeout=60.0)
        sandbox = Sandbox(config)
        assert sandbox.config.timeout == 60.0

    def test_execute_simple_code(self):
        """测试执行简单代码"""
        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        result = sandbox.execute("print('test')")
        assert result.success is True
        assert "test" in result.stdout

    def test_execute_blocked_import(self):
        """测试执行阻止的导入"""
        config = SandboxConfig(
            timeout=10.0,
            blocked_imports=["subprocess"],
        )
        sandbox = Sandbox(config)
        result = sandbox.execute("import subprocess")
        assert result.success is False
        assert "Blocked imports" in result.error_message

    def test_execute_skip_import_check(self):
        """测试跳过导入检查"""
        config = SandboxConfig(
            timeout=10.0,
            blocked_imports=["json"],
        )
        sandbox = Sandbox(config)
        # 跳过检查时应该能执行
        result = sandbox.execute("import json; print('ok')", check_imports=False)
        assert result.success is True

    def test_on_complete_callback(self):
        """测试完成回调"""
        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        callback_results = []

        def callback(result):
            callback_results.append(result)

        sandbox.on_complete(callback)
        sandbox.execute("print('test')")

        assert len(callback_results) == 1
        assert callback_results[0].success is True

    def test_execute_file(self, tmp_path):
        """测试执行文件"""
        # 创建临时文件
        code_file = tmp_path / "test.py"
        code_file.write_text("print('from file')")

        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        result = sandbox.execute_file(str(code_file))
        assert result.success is True
        assert "from file" in result.stdout

    def test_execute_file_not_found(self):
        """测试执行不存在的文件"""
        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        result = sandbox.execute_file("/nonexistent/file.py")
        assert result.success is False
        assert "File not found" in result.error_message


class TestSandboxPool:
    """测试沙箱池"""

    def test_create_pool(self):
        """测试创建沙箱池"""
        pool = SandboxPool(pool_size=2)
        assert pool.total_count == 2
        assert pool.available_count == 2

    def test_acquire_release(self):
        """测试获取和释放"""
        pool = SandboxPool(pool_size=2)

        sandbox1 = pool.acquire()
        assert sandbox1 is not None
        assert pool.available_count == 1

        sandbox2 = pool.acquire()
        assert sandbox2 is not None
        assert pool.available_count == 0

        # 没有可用的了
        sandbox3 = pool.acquire()
        assert sandbox3 is None

        # 释放一个
        pool.release(sandbox1)
        assert pool.available_count == 1

    def test_execute_with_pool(self):
        """测试使用池执行"""
        config = SandboxConfig(timeout=10.0)
        pool = SandboxPool(config, pool_size=2)

        result = pool.execute("print('pool test')")
        assert result.success is True
        assert "pool test" in result.stdout

        # 执行后沙箱应该被释放
        assert pool.available_count == 2

    def test_execute_no_available(self):
        """测试无可用沙箱"""
        pool = SandboxPool(pool_size=1)

        # 获取唯一的沙箱
        sandbox = pool.acquire()
        assert sandbox is not None

        # 尝试执行，应该失败
        result = pool.execute("print('test')")
        assert result.success is False
        assert "No available sandbox" in result.error_message

        # 释放后可以执行
        pool.release(sandbox)
        result = pool.execute("print('test')")
        assert result.success is True


class TestDockerExecutor:
    """测试 Docker 执行器"""

    @pytest.fixture
    def mock_docker(self):
        """模拟 Docker"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            yield mock_run

    def test_docker_not_available(self):
        """测试 Docker 不可用"""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            config = SandboxConfig(runtime="docker")
            with pytest.raises(SandboxError, match="not installed"):
                Sandbox(config)

    def test_docker_check_timeout(self):
        """测试 Docker 检查超时"""
        import subprocess as sp
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = sp.TimeoutExpired("docker", 5)
            config = SandboxConfig(runtime="docker")
            with pytest.raises(SandboxError, match="timed out"):
                Sandbox(config)


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        config = SandboxConfig(
            timeout=10.0,
            memory_limit_mb=128,
            blocked_imports=["subprocess", "os.system"],
        )
        sandbox = Sandbox(config)

        # 执行安全代码
        result = sandbox.execute("""
import json
data = {"key": "value"}
print(json.dumps(data))
""")
        assert result.success is True
        assert '"key"' in result.stdout

    def test_computation(self):
        """测试计算"""
        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        result = sandbox.execute("""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))
""")
        assert result.success is True
        assert "55" in result.stdout

    def test_error_handling(self):
        """测试错误处理"""
        sandbox = Sandbox(SandboxConfig(timeout=10.0))
        result = sandbox.execute("""
x = 1 / 0
""")
        assert result.success is False
        assert "ZeroDivisionError" in result.stderr
