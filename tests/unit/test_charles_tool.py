"""Charles 代理抓包工具 - 单元测试与集成测试

测试覆盖：
- 工具初始化与属性
- 启动/停止 Charles 代理
- 状态查询
- 会话导出
- 无效操作处理
- 工具注册与 Agent 集成
- 参数传递
- Mock 模拟 Charles 进程与系统代理
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xiaotie.tools.charles_tool import CharlesProxyTool
from xiaotie.schema import ToolResult


# ============================================================
# 单元测试
# ============================================================


class TestCharlesToolInit:
    """测试 CharlesProxyTool 初始化"""

    def test_charles_tool_init(self):
        """测试工具初始化默认值"""
        tool = CharlesProxyTool()

        assert tool.charles_process is None
        assert tool.proxy_port == 8888
        assert tool.session_file is None
        # 继承自 Tool 基类的 execution_stats
        assert tool.execution_stats["call_count"] == 0

    def test_charles_tool_init_custom_path(self):
        """测试自定义 Charles 路径"""
        tool = CharlesProxyTool(charles_path="/custom/charles")
        assert tool.charles_app == "/custom/charles"

    def test_charles_tool_init_custom_port(self):
        """测试自定义端口"""
        tool = CharlesProxyTool(proxy_port=9999)
        assert tool.proxy_port == 9999

    def test_tool_properties(self):
        """测试工具名称、描述、参数 schema"""
        tool = CharlesProxyTool()

        assert tool.name == "charles_proxy"
        assert "Charles" in tool.description
        params = tool.parameters
        assert params["type"] == "object"
        assert "action" in params["properties"]
        # 新版本包含 analyze 和 filter_miniapp
        enum_vals = params["properties"]["action"]["enum"]
        assert "start" in enum_vals
        assert "stop" in enum_vals
        assert "export" in enum_vals
        assert "status" in enum_vals
        assert "action" in params["required"]

    def test_to_schema(self):
        """测试 Anthropic schema 转换"""
        tool = CharlesProxyTool()
        schema = tool.to_schema()
        assert schema["name"] == "charles_proxy"
        assert "input_schema" in schema

    def test_to_openai_schema(self):
        """测试 OpenAI schema 转换"""
        tool = CharlesProxyTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "charles_proxy"

    def test_detect_charles_path(self):
        """测试自动检测 Charles 路径"""
        # _detect_charles_path 是静态方法，应返回字符串
        path = CharlesProxyTool._detect_charles_path()
        assert isinstance(path, str)
        assert len(path) > 0


class TestStartCharles:
    """测试启动 Charles 代理"""

    @pytest.mark.asyncio
    async def test_start_charles_success(self):
        """测试成功启动 Charles"""
        tool = CharlesProxyTool(charles_path="/fake/charles")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 进程运行中
        mock_proc.pid = 12345

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            return_value=mock_proc,
        ), patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch.object(
            CharlesProxyTool,
            "_configure_system_proxy",
            new_callable=AsyncMock,
        ):
            result = await tool.execute(action="start", port=9999)

        assert result.success is True
        assert "9999" in result.content
        assert "12345" in result.content
        assert tool.proxy_port == 9999

    @pytest.mark.asyncio
    async def test_start_charles_already_running(self):
        """测试 Charles 已在运行时再次启动"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 进程运行中
        tool.charles_process = mock_proc
        tool.proxy_port = 8888

        result = await tool.execute(action="start")

        assert result.success is True
        assert "已在运行" in result.content

    @pytest.mark.asyncio
    async def test_start_charles_default_port(self):
        """测试使用默认端口启动"""
        tool = CharlesProxyTool(charles_path="/fake/charles")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 99999

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            return_value=mock_proc,
        ), patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch.object(
            CharlesProxyTool,
            "_configure_system_proxy",
            new_callable=AsyncMock,
        ):
            result = await tool.execute(action="start")

        assert result.success is True
        assert tool.proxy_port == 8888

    @pytest.mark.asyncio
    async def test_start_charles_file_not_found(self):
        """测试 Charles 应用未找到"""
        tool = CharlesProxyTool(charles_path="/nonexistent/charles")

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            side_effect=FileNotFoundError("not found"),
        ):
            result = await tool.execute(action="start")

        assert result.success is False
        assert "未找到" in result.error or "失败" in result.error

    @pytest.mark.asyncio
    async def test_start_charles_generic_failure(self):
        """测试启动时的通用异常"""
        tool = CharlesProxyTool(charles_path="/fake/charles")

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            side_effect=OSError("permission denied"),
        ):
            result = await tool.execute(action="start")

        assert result.success is False


class TestStopCharles:
    """测试停止 Charles 代理"""

    @pytest.mark.asyncio
    async def test_stop_charles_success(self):
        """测试成功停止 Charles"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 进程运行中
        mock_proc.terminate.return_value = None
        mock_proc.wait.return_value = 0
        tool.charles_process = mock_proc

        with patch.object(
            CharlesProxyTool,
            "_restore_system_proxy",
            new_callable=AsyncMock,
        ):
            result = await tool.execute(action="stop")

        assert result.success is True
        assert "已停止" in result.content
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_charles_not_running(self):
        """测试 Charles 未运行时停止"""
        tool = CharlesProxyTool()
        # charles_process is None
        result = await tool.execute(action="stop")

        assert result.success is True
        assert "未运行" in result.content

    @pytest.mark.asyncio
    async def test_stop_charles_already_exited(self):
        """测试 Charles 进程已退出时停止"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 进程已退出
        tool.charles_process = mock_proc

        result = await tool.execute(action="stop")

        assert result.success is True
        assert "未运行" in result.content

    @pytest.mark.asyncio
    async def test_stop_charles_terminate_failure(self):
        """测试终止进程失败"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.terminate.side_effect = OSError("Permission denied")
        tool.charles_process = mock_proc

        result = await tool.execute(action="stop")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_stop_charles_timeout_then_kill(self):
        """测试 terminate 超时后 kill"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.terminate.return_value = None
        # wait 第一次超时，第二次成功
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="charles", timeout=5),
            0,
        ]
        mock_proc.kill.return_value = None
        tool.charles_process = mock_proc

        with patch.object(
            CharlesProxyTool,
            "_restore_system_proxy",
            new_callable=AsyncMock,
        ):
            result = await tool.execute(action="stop")

        assert result.success is True
        mock_proc.kill.assert_called_once()


class TestGetStatus:
    """测试状态查询"""

    @pytest.mark.asyncio
    async def test_get_status_running(self):
        """测试运行中的状态"""
        tool = CharlesProxyTool()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 54321
        tool.charles_process = mock_proc
        tool.proxy_port = 9090

        result = await tool.execute(action="status")

        assert result.success is True
        assert "运行中" in result.content
        assert "9090" in result.content
        assert "54321" in result.content

    @pytest.mark.asyncio
    async def test_get_status_not_running(self):
        """测试未运行的状态"""
        tool = CharlesProxyTool()

        result = await tool.execute(action="status")

        assert result.success is True
        assert "未运行" in result.content

    @pytest.mark.asyncio
    async def test_get_status_with_session_file(self):
        """测试有最近导出文件时的状态"""
        tool = CharlesProxyTool()
        tool.session_file = Path("/tmp/test_session.json")

        result = await tool.execute(action="status")

        assert result.success is True
        assert "test_session.json" in result.content


class TestExportSession:
    """测试会话导出"""

    @pytest.mark.asyncio
    async def test_export_session_with_output_file(self):
        """测试指定输出文件导出（AppleScript 失败回退到手动说明）"""
        tool = CharlesProxyTool()

        # AppleScript 导出会失败（没有 Charles 运行），回退到手动说明
        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no Charles"),
        ):
            result = await tool.execute(
                action="export",
                output_file="my_capture.json",
            )

        assert result.success is True
        assert "my_capture.json" in result.content

    @pytest.mark.asyncio
    async def test_export_session_default_filename(self):
        """测试默认文件名导出"""
        tool = CharlesProxyTool()

        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no Charles"),
        ):
            result = await tool.execute(action="export")

        assert result.success is True
        assert "charles_session_" in result.content

    @pytest.mark.asyncio
    async def test_export_session_auto_success(self):
        """测试 AppleScript 自动导出成功"""
        tool = CharlesProxyTool()

        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            return_value=True,
        ), patch.object(
            CharlesProxyTool,
            "_load_session_file",
            return_value=None,
        ):
            result = await tool.execute(
                action="export",
                output_file="/tmp/auto_export.json",
            )

        assert result.success is True
        assert "auto_export.json" in result.content
        assert tool.session_file is not None


class TestInvalidAction:
    """测试无效操作"""

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """测试未知的操作类型"""
        tool = CharlesProxyTool()

        result = await tool.execute(action="restart")

        assert result.success is False
        assert "未知的操作类型" in result.error
        assert "restart" in result.error

    @pytest.mark.asyncio
    async def test_none_action(self):
        """测试 action 为 None"""
        tool = CharlesProxyTool()

        result = await tool.execute(action=None)

        assert result.success is False


# ============================================================
# 集成测试
# ============================================================


class TestToolRegistration:
    """测试工具注册"""

    def test_charles_tool_in_module_exports(self):
        """测试 CharlesProxyTool 在 __init__.py 中导出"""
        from xiaotie.tools import CharlesProxyTool as Imported
        assert Imported is CharlesProxyTool

    def test_charles_tool_in_all(self):
        """测试 CharlesProxyTool 在 __all__ 中"""
        import xiaotie.tools as tools_module
        assert "CharlesProxyTool" in tools_module.__all__

    def test_tool_is_subclass_of_base(self):
        """测试 CharlesProxyTool 是 Tool 的子类"""
        from xiaotie.tools.base import Tool
        assert issubclass(CharlesProxyTool, Tool)


class TestAgentIntegration:
    """测试与 Agent 的集成"""

    def test_tool_schema_for_anthropic(self):
        """测试 Anthropic 格式 schema 可用于 Agent"""
        tool = CharlesProxyTool()
        schema = tool.to_schema()

        assert schema["name"] == "charles_proxy"
        assert isinstance(schema["description"], str)
        assert isinstance(schema["input_schema"], dict)
        assert schema["input_schema"]["type"] == "object"

    def test_tool_schema_for_openai(self):
        """测试 OpenAI 格式 schema 可用于 Agent"""
        tool = CharlesProxyTool()
        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        func = schema["function"]
        assert func["name"] == "charles_proxy"
        assert "parameters" in func

    def test_execution_stats_tracking(self):
        """测试执行统计跟踪"""
        tool = CharlesProxyTool()
        stats = tool.get_execution_stats()

        assert stats["call_count"] == 0
        assert stats["total_time"] == 0.0
        assert stats["success_count"] == 0
        assert stats["error_count"] == 0

    @pytest.mark.asyncio
    async def test_execute_with_monitoring(self):
        """测试带监控的执行"""
        tool = CharlesProxyTool()

        result = await tool.execute_with_monitoring(action="status")

        assert result.success is True
        stats = tool.get_execution_stats()
        assert stats["call_count"] == 1
        assert stats["success_count"] == 1
        assert stats["avg_time"] > 0


class TestParameterPassing:
    """测试参数传递"""

    @pytest.mark.asyncio
    async def test_start_with_port_kwarg(self):
        """测试通过 kwargs 传递 port 参数"""
        tool = CharlesProxyTool(charles_path="/fake/charles")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 11111

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            return_value=mock_proc,
        ), patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch.object(
            CharlesProxyTool,
            "_configure_system_proxy",
            new_callable=AsyncMock,
        ):
            result = await tool.execute(action="start", port=7777)

        assert tool.proxy_port == 7777
        assert "7777" in result.content

    @pytest.mark.asyncio
    async def test_export_with_output_file_kwarg(self):
        """测试通过 kwargs 传递 output_file 参数"""
        tool = CharlesProxyTool()

        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no Charles"),
        ):
            result = await tool.execute(
                action="export",
                output_file="/tmp/test_export.json",
            )

        assert result.success is True
        assert "/tmp/test_export.json" in result.content

    @pytest.mark.asyncio
    async def test_extra_kwargs_ignored(self):
        """测试多余参数不影响执行"""
        tool = CharlesProxyTool()

        result = await tool.execute(
            action="status",
            filter_domain="example.com",
            unknown_param="ignored",
        )

        assert result.success is True


# ============================================================
# Mock 测试
# ============================================================


class TestMockCharlesProcess:
    """使用 Mock 模拟 Charles 进程"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """测试完整生命周期：启动 -> 状态 -> 导出 -> 停止"""
        tool = CharlesProxyTool(charles_path="/fake/charles")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 42
        mock_proc.terminate.return_value = None
        mock_proc.wait.return_value = 0

        # 1. 启动
        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            return_value=mock_proc,
        ), patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch.object(
            CharlesProxyTool,
            "_configure_system_proxy",
            new_callable=AsyncMock,
        ):
            start_result = await tool.execute(action="start", port=8888)
        assert start_result.success is True

        # 2. 状态
        status_result = await tool.execute(action="status")
        assert status_result.success is True
        assert "运行中" in status_result.content

        # 3. 导出
        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no gui"),
        ):
            export_result = await tool.execute(
                action="export", output_file="lifecycle_test.json",
            )
        assert export_result.success is True

        # 4. 停止
        with patch.object(
            CharlesProxyTool,
            "_restore_system_proxy",
            new_callable=AsyncMock,
        ):
            stop_result = await tool.execute(action="stop")
        assert stop_result.success is True
        assert "已停止" in stop_result.content

    @pytest.mark.asyncio
    async def test_popen_called_with_correct_args(self):
        """测试 Popen 使用正确的参数调用"""
        tool = CharlesProxyTool(charles_path="/custom/charles")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 1

        with patch(
            "xiaotie.tools.charles_tool.subprocess.Popen",
            return_value=mock_proc,
        ) as mock_popen, patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch.object(
            CharlesProxyTool,
            "_configure_system_proxy",
            new_callable=AsyncMock,
        ):
            await tool.execute(action="start")

        mock_popen.assert_called_once_with(
            ["/custom/charles"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class TestMockSystemProxy:
    """模拟系统代理配置"""

    @pytest.mark.asyncio
    async def test_configure_system_proxy_macos(self):
        """测试 macOS 上配置系统代理"""
        tool = CharlesProxyTool()

        with patch(
            "xiaotie.tools.charles_tool.platform.system",
            return_value="Darwin",
        ), patch.object(
            CharlesProxyTool,
            "_get_network_services",
            new_callable=AsyncMock,
            return_value=["Wi-Fi", "Ethernet"],
        ), patch(
            "xiaotie.tools.charles_tool.subprocess.run",
        ) as mock_run:
            await tool._configure_system_proxy(8888)

        # 每个服务应调用 setwebproxy + setsecurewebproxy
        assert mock_run.call_count == 4

    @pytest.mark.asyncio
    async def test_restore_system_proxy_macos(self):
        """测试 macOS 上恢复系统代理"""
        tool = CharlesProxyTool()

        with patch(
            "xiaotie.tools.charles_tool.platform.system",
            return_value="Darwin",
        ), patch.object(
            CharlesProxyTool,
            "_get_network_services",
            new_callable=AsyncMock,
            return_value=["Wi-Fi"],
        ), patch(
            "xiaotie.tools.charles_tool.subprocess.run",
        ) as mock_run:
            await tool._restore_system_proxy()

        # Wi-Fi: setwebproxystate off + setsecurewebproxystate off
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_configure_proxy_ignores_errors(self):
        """测试配置代理时忽略错误"""
        tool = CharlesProxyTool()

        with patch(
            "xiaotie.tools.charles_tool.platform.system",
            return_value="Darwin",
        ), patch.object(
            CharlesProxyTool,
            "_get_network_services",
            new_callable=AsyncMock,
            side_effect=Exception("networksetup failed"),
        ):
            # 不应抛出异常
            await tool._configure_system_proxy(8888)

    @pytest.mark.asyncio
    async def test_restore_proxy_ignores_errors(self):
        """测试恢复代理时忽略错误"""
        tool = CharlesProxyTool()

        with patch(
            "xiaotie.tools.charles_tool.platform.system",
            return_value="Darwin",
        ), patch.object(
            CharlesProxyTool,
            "_get_network_services",
            new_callable=AsyncMock,
            side_effect=Exception("networksetup failed"),
        ):
            # 不应抛出异常
            await tool._restore_system_proxy()

    @pytest.mark.asyncio
    async def test_get_network_services(self):
        """测试获取 macOS 网络服务列表"""
        mock_result = MagicMock()
        mock_result.stdout = "An asterisk (*) denotes...\nWi-Fi\n*Bluetooth\nEthernet\n"

        with patch(
            "xiaotie.tools.charles_tool.subprocess.run",
            return_value=mock_result,
        ):
            services = await CharlesProxyTool._get_network_services()

        assert "Wi-Fi" in services
        assert "Ethernet" in services
        # *Bluetooth should be filtered out
        assert "*Bluetooth" not in services

    @pytest.mark.asyncio
    async def test_configure_proxy_linux(self):
        """测试 Linux 上配置环境变量代理"""
        tool = CharlesProxyTool()
        import os

        old_http = os.environ.get("http_proxy")
        old_https = os.environ.get("https_proxy")

        try:
            with patch(
                "xiaotie.tools.charles_tool.platform.system",
                return_value="Linux",
            ):
                await tool._configure_system_proxy(9090)

            assert os.environ.get("http_proxy") == "http://127.0.0.1:9090"
            assert os.environ.get("https_proxy") == "http://127.0.0.1:9090"
        finally:
            # Restore original values
            if old_http is not None:
                os.environ["http_proxy"] = old_http
            else:
                os.environ.pop("http_proxy", None)
            if old_https is not None:
                os.environ["https_proxy"] = old_https
            else:
                os.environ.pop("https_proxy", None)


class TestMockSessionExport:
    """模拟会话导出"""

    @pytest.mark.asyncio
    async def test_export_fallback_instructions(self):
        """测试导出回退到手动说明"""
        tool = CharlesProxyTool()

        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no gui"),
        ):
            result = await tool.execute(
                action="export",
                output_file="test_output.json",
            )

        assert result.success is True
        assert "Export Session" in result.content
        assert "test_output.json" in result.content

    @pytest.mark.asyncio
    async def test_export_default_filename_contains_timestamp(self):
        """测试默认文件名包含时间戳"""
        tool = CharlesProxyTool()

        with patch(
            "xiaotie.tools.charles_tool.time.time",
            return_value=1700000000,
        ), patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no gui"),
        ):
            result = await tool.execute(action="export")

        assert result.success is True
        assert "charles_session_1700000000" in result.content

    @pytest.mark.asyncio
    async def test_export_har_format(self):
        """测试 HAR 格式导出"""
        tool = CharlesProxyTool()

        with patch.object(
            CharlesProxyTool,
            "_applescript_export",
            new_callable=AsyncMock,
            side_effect=RuntimeError("no gui"),
        ):
            result = await tool.execute(
                action="export",
                format="har",
                output_file="test.har",
            )

        assert result.success is True
        assert "HAR" in result.content or "har" in result.content


class TestAnalyzeSession:
    """测试会话分析功能"""

    @pytest.mark.asyncio
    async def test_analyze_no_session_file(self):
        """测试没有会话文件时分析"""
        tool = CharlesProxyTool()

        result = await tool.execute(action="analyze")

        assert result.success is False
        assert "session_file" in result.error or "会话文件" in result.error

    @pytest.mark.asyncio
    async def test_analyze_with_session_data(self, tmp_path):
        """测试分析会话数据"""
        tool = CharlesProxyTool()

        # 创建模拟会话文件
        session_data = [
            {
                "url": "https://api.example.com/v1/users",
                "method": "GET",
                "status": 200,
                "sizes": {"response": 1024},
            },
            {
                "url": "https://api.example.com/v1/posts",
                "method": "POST",
                "status": 201,
                "sizes": {"response": 512},
            },
        ]
        session_file = tmp_path / "test_session.json"
        session_file.write_text(json.dumps(session_data))

        result = await tool.execute(
            action="analyze",
            session_file=str(session_file),
        )

        assert result.success is True
        assert "分析报告" in result.content or "会话中没有" in result.content


class TestFilterMiniapp:
    """测试小程序请求过滤"""

    @pytest.mark.asyncio
    async def test_filter_miniapp_no_session(self):
        """测试没有会话文件时过滤"""
        tool = CharlesProxyTool()

        result = await tool.execute(action="filter_miniapp")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_filter_miniapp_no_matches(self, tmp_path):
        """测试没有小程序请求时"""
        tool = CharlesProxyTool()

        session_data = [
            {"url": "https://google.com/search", "method": "GET", "status": 200},
        ]
        session_file = tmp_path / "no_miniapp.json"
        session_file.write_text(json.dumps(session_data))

        result = await tool.execute(
            action="filter_miniapp",
            session_file=str(session_file),
        )

        assert result.success is True
        assert "未找到" in result.content or "没有" in result.content

    @pytest.mark.asyncio
    async def test_filter_miniapp_with_matches(self, tmp_path):
        """测试有小程序请求时"""
        tool = CharlesProxyTool()

        session_data = [
            {
                "url": "https://servicewechat.com/wx123/api/data",
                "method": "POST",
                "status": 200,
            },
            {
                "url": "https://google.com/search",
                "method": "GET",
                "status": 200,
            },
        ]
        session_file = tmp_path / "with_miniapp.json"
        session_file.write_text(json.dumps(session_data))

        result = await tool.execute(
            action="filter_miniapp",
            session_file=str(session_file),
        )

        assert result.success is True
        assert "servicewechat" in result.content or "小程序" in result.content


class TestRetryHelper:
    """测试重试包装器"""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """测试第一次就成功"""
        tool = CharlesProxyTool()

        async def success_fn():
            return "ok"

        result = await tool._retry(success_fn, retries=3)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """测试失败后重试成功"""
        tool = CharlesProxyTool()
        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "ok"

        with patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await tool._retry(flaky_fn, retries=3)

        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        """测试所有重试都失败"""
        tool = CharlesProxyTool()

        async def always_fail():
            raise RuntimeError("permanent error")

        with patch(
            "xiaotie.tools.charles_tool.asyncio.sleep",
            new_callable=AsyncMock,
        ), pytest.raises(RuntimeError, match="permanent error"):
            await tool._retry(always_fail, retries=2)


class TestInternalHelpers:
    """测试内部辅助方法"""

    def test_resolve_session_path_from_kwargs(self):
        """测试从 kwargs 解析会话路径"""
        tool = CharlesProxyTool()
        path = tool._resolve_session_path({"session_file": "/tmp/test.json"})
        assert path is not None
        assert path.name == "test.json"

    def test_resolve_session_path_from_instance(self, tmp_path):
        """测试从实例属性解析会话路径"""
        tool = CharlesProxyTool()
        sf = tmp_path / "session.json"
        sf.write_text("[]")
        tool.session_file = sf
        path = tool._resolve_session_path({})
        assert path == sf

    def test_resolve_session_path_none(self):
        """测试无可用会话路径"""
        tool = CharlesProxyTool()
        path = tool._resolve_session_path({})
        assert path is None

    def test_load_session_file_valid(self, tmp_path):
        """测试加载有效 JSON 文件"""
        f = tmp_path / "valid.json"
        f.write_text('[{"url": "https://example.com"}]')
        data = CharlesProxyTool._load_session_file(f)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_load_session_file_invalid_json(self, tmp_path):
        """测试加载无效 JSON 文件"""
        f = tmp_path / "invalid.json"
        f.write_text("not json")
        data = CharlesProxyTool._load_session_file(f)
        assert data is None

    def test_load_session_file_missing(self, tmp_path):
        """测试加载不存在的文件"""
        f = tmp_path / "missing.json"
        data = CharlesProxyTool._load_session_file(f)
        assert data is None

    def test_extract_entries_list(self):
        """测试从列表提取条目"""
        data = [{"url": "a"}, {"url": "b"}]
        entries = CharlesProxyTool._extract_entries(data)
        assert len(entries) == 2

    def test_extract_entries_har(self):
        """测试从 HAR 格式提取条目"""
        data = {"log": {"entries": [{"url": "a"}]}}
        entries = CharlesProxyTool._extract_entries(data)
        assert len(entries) == 1

    def test_extract_entries_dict_with_entries(self):
        """测试从 dict.entries 提取条目"""
        data = {"entries": [{"url": "a"}, {"url": "b"}]}
        entries = CharlesProxyTool._extract_entries(data)
        assert len(entries) == 2

    def test_extract_entries_single_dict(self):
        """测试从单个 dict 提取条目"""
        data = {"url": "a", "method": "GET"}
        entries = CharlesProxyTool._extract_entries(data)
        assert len(entries) == 1

    def test_extract_entries_empty(self):
        """测试空数据"""
        assert CharlesProxyTool._extract_entries("not a dict or list") == []

    def test_filter_by_domain(self):
        """测试按域名过滤"""
        data = [
            {"url": "https://api.example.com/v1"},
            {"url": "https://other.com/v1"},
            {"url": "https://api.example.com/v2"},
        ]
        filtered = CharlesProxyTool._filter_by_domain(data, "example.com")
        assert len(filtered) == 2
