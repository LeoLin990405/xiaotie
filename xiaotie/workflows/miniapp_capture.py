"""小程序自动化抓取工作流

编排 ProxyServer + MiniAppAutomation/WeChatController 实现端到端的
微信小程序网络请求自动抓取。

工作流步骤:
    1. 启动代理服务器（mitmproxy）
    2. 启动自动化引擎（macOS AppleScript 或 Appium）
    3. 打开微信 -> 搜索并进入小程序
    4. 执行页面操作（滚动、点击等）触发网络请求
    5. 等待抓取完成
    6. 过滤小程序请求 + 导出数据
    7. 清理：停止代理和自动化会话

支持:
    - 单个或批量小程序抓取
    - macOS 原生自动化（AppleScript）和 Appium 两种引擎
    - JSON / HAR 导出格式
    - 自定义页面操作序列
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class AutomationEngine(Enum):
    """自动化引擎类型"""
    MACOS = "macos"       # macOS AppleScript (仅 macOS)
    APPIUM = "appium"     # Appium (Android/iOS 模拟器)
    NONE = "none"         # 不使用自动化（手动操作小程序）


class ExportFormat(Enum):
    JSON = "json"
    HAR = "har"


@dataclass
class PageAction:
    """页面操作指令"""
    action: str           # scroll_down, click, wait, screenshot
    params: Dict[str, Any] = field(default_factory=dict)
    delay: float = 1.0    # 操作后等待秒数


@dataclass
class MiniAppTarget:
    """单个小程序抓取目标"""
    name: str                                    # 小程序名称
    app_id: Optional[str] = None                 # 小程序 AppID
    deeplink: Optional[str] = None               # 深链接
    actions: List[PageAction] = field(default_factory=list)
    capture_duration: float = 30.0               # 抓取持续时间（秒）
    export_format: ExportFormat = ExportFormat.JSON


@dataclass
class CaptureConfig:
    """抓取工作流配置"""
    # 代理
    proxy_port: int = 8080
    enable_https: bool = True
    auto_system_proxy: bool = False
    miniapp_only: bool = True

    # 自动化
    engine: AutomationEngine = AutomationEngine.NONE
    appium_server: str = "http://localhost:4723"
    appium_platform: str = "Android"
    device_name: str = "emulator-5554"

    # 输出
    output_dir: str = "./capture_output"
    export_format: ExportFormat = ExportFormat.JSON

    # 行为
    scroll_count: int = 5
    default_capture_duration: float = 30.0
    action_delay: float = 1.5


@dataclass
class CaptureResult:
    """单个小程序的抓取结果"""
    miniapp_name: str
    success: bool
    total_requests: int = 0
    miniapp_requests: int = 0
    export_path: Optional[str] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)


class MiniAppCaptureWorkflow:
    """小程序自动化抓取工作流

    编排代理服务器和自动化引擎，实现端到端的小程序网络请求抓取。

    Example::

        config = CaptureConfig(proxy_port=8080, engine=AutomationEngine.NONE)
        workflow = MiniAppCaptureWorkflow(config)

        target = MiniAppTarget(name="美团", capture_duration=30)
        result = await workflow.capture_one(target)

        # 批量抓取
        targets = [MiniAppTarget(name="美团"), MiniAppTarget(name="饿了么")]
        results = await workflow.capture_batch(targets)
    """

    def __init__(
        self,
        config: Optional[CaptureConfig] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or CaptureConfig()
        self.on_progress = on_progress or (lambda msg: None)
        self._proxy = None
        self._automation = None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def capture_one(self, target: MiniAppTarget) -> CaptureResult:
        """抓取单个小程序的网络请求"""
        start = time.time()
        try:
            self._log(f"开始抓取小程序: {target.name}")

            # 1. 启动代理
            await self._start_proxy()

            # 2. 启动自动化（如果配置了引擎）
            if self.config.engine != AutomationEngine.NONE:
                await self._start_automation()
                await self._open_miniapp(target)
                await self._execute_actions(target)
            else:
                self._log(
                    f"手动模式: 请在 {target.capture_duration}s 内"
                    f"手动打开小程序「{target.name}」并操作"
                )

            # 3. 等待抓取
            await self._wait_capture(target.capture_duration)

            # 4. 过滤 + 导出
            result = await self._collect_and_export(target)
            result.duration_seconds = time.time() - start

            # 5. 清理本次抓取数据（为下一个小程序准备）
            self._proxy.clear_captured_flows()

            self._log(
                f"抓取完成: {target.name} "
                f"({result.miniapp_requests} 条小程序请求, "
                f"{result.duration_seconds:.1f}s)"
            )
            return result

        except Exception as e:
            logger.exception("抓取 %s 失败", target.name)
            return CaptureResult(
                miniapp_name=target.name,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start,
            )

    async def capture_batch(
        self, targets: Sequence[MiniAppTarget]
    ) -> List[CaptureResult]:
        """批量抓取多个小程序"""
        results = []
        self._log(f"批量抓取: {len(targets)} 个小程序")

        try:
            for i, target in enumerate(targets, 1):
                self._log(f"[{i}/{len(targets)}] {target.name}")
                result = await self.capture_one(target)
                results.append(result)

                # 小程序之间间隔
                if i < len(targets):
                    await asyncio.sleep(self.config.action_delay)
        finally:
            await self.cleanup()

        self._log_summary(results)
        return results

    async def cleanup(self) -> None:
        """清理所有资源"""
        if self._automation:
            try:
                await self._stop_automation()
            except Exception as e:
                logger.warning("停止自动化失败: %s", e)

        if self._proxy:
            try:
                await self._proxy.stop()
                self._log("代理服务器已停止")
            except Exception as e:
                logger.warning("停止代理失败: %s", e)

        self._proxy = None
        self._automation = None

    async def __aenter__(self) -> "MiniAppCaptureWorkflow":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.cleanup()

    # ------------------------------------------------------------------
    # 内部方法: 代理
    # ------------------------------------------------------------------

    async def _start_proxy(self) -> None:
        """启动代理服务器（如果尚未运行）"""
        if self._proxy and self._proxy.is_running:
            return

        from ..proxy import ProxyServer

        self._proxy = ProxyServer(
            port=self.config.proxy_port,
            enable_ssl=self.config.enable_https,
            miniapp_only=self.config.miniapp_only,
            auto_system_proxy=self.config.auto_system_proxy,
        )
        await self._proxy.start()
        self._log(
            f"代理服务器已启动 (端口 {self.config.proxy_port}, "
            f"HTTPS={'启用' if self.config.enable_https else '禁用'})"
        )

    # ------------------------------------------------------------------
    # 内部方法: 自动化
    # ------------------------------------------------------------------

    async def _start_automation(self) -> None:
        """启动自动化引擎"""
        if self._automation:
            return

        if self.config.engine == AutomationEngine.MACOS:
            from ..automation.macos import WeChatController
            self._automation = WeChatController()
            self._log("macOS 自动化引擎已启动")

        elif self.config.engine == AutomationEngine.APPIUM:
            from ..automation import MiniAppAutomation
            from ..automation.appium_driver import AppiumConfig
            from ..automation.miniapp_automation import MiniAppConfig

            appium_cfg = AppiumConfig(
                platform=self.config.appium_platform,
                device_name=self.config.device_name,
                appium_server=self.config.appium_server,
            )
            miniapp_cfg = MiniAppConfig(
                miniapp_name="",
                proxy_host="127.0.0.1",
                proxy_port=self.config.proxy_port,
            )
            self._automation = MiniAppAutomation(appium_cfg, miniapp_cfg)
            await self._automation.start()
            self._log("Appium 自动化引擎已启动")

    async def _stop_automation(self) -> None:
        """停止自动化引擎"""
        if not self._automation:
            return
        if self.config.engine == AutomationEngine.APPIUM:
            await self._automation.stop()
        self._automation = None
        self._log("自动化引擎已停止")

    async def _open_miniapp(self, target: MiniAppTarget) -> None:
        """通过自动化打开小程序"""
        if self.config.engine == AutomationEngine.MACOS:
            if hasattr(self._automation, "launch"):
                await self._automation.launch()
            if hasattr(self._automation, "activate"):
                await self._automation.activate()
            if hasattr(self._automation, "search"):
                await self._automation.search(target.name)
            self._log(f"已通过 macOS 自动化打开: {target.name}")

        elif self.config.engine == AutomationEngine.APPIUM:
            if target.deeplink:
                await self._automation.open_miniapp_by_deeplink(target.deeplink)
            else:
                await self._automation.open_miniapp_by_name(target.name)
            self._log(f"已通过 Appium 打开: {target.name}")

    async def _execute_actions(self, target: MiniAppTarget) -> None:
        """执行页面操作序列"""
        actions = target.actions
        if not actions:
            # 默认操作: 等待加载 + 滚动页面
            actions = [
                PageAction(action="wait", delay=2.0),
            ] + [
                PageAction(
                    action="scroll_down",
                    delay=self.config.action_delay,
                )
                for _ in range(self.config.scroll_count)
            ]

        for act in actions:
            try:
                await self._do_action(act)
            except Exception as e:
                logger.warning("操作 %s 失败: %s", act.action, e)

    async def _do_action(self, act: PageAction) -> None:
        """执行单个页面操作"""
        if act.action == "wait":
            await asyncio.sleep(act.delay)
        elif act.action == "scroll_down":
            if hasattr(self._automation, "scroll_down"):
                distance = act.params.get("distance", 500)
                await self._automation.scroll_down(distance)
            await asyncio.sleep(act.delay)
        elif act.action == "screenshot":
            if hasattr(self._automation, "screenshot"):
                filename = act.params.get(
                    "filename", f"screenshot_{int(time.time())}.png"
                )
                await self._automation.screenshot(filename)
        elif act.action == "click":
            if (
                hasattr(self._automation, "driver")
                and self._automation.driver
            ):
                x = act.params.get("x", 0)
                y = act.params.get("y", 0)
                await self._automation.driver.tap(x, y)
            await asyncio.sleep(act.delay)

    # ------------------------------------------------------------------
    # 内部方法: 抓取与导出
    # ------------------------------------------------------------------

    async def _wait_capture(self, duration: float) -> None:
        """等待抓取指定时长"""
        self._log(f"等待抓取中... ({duration:.0f}s)")
        interval = min(5.0, duration / 4)
        elapsed = 0.0
        while elapsed < duration:
            wait = min(interval, duration - elapsed)
            await asyncio.sleep(wait)
            elapsed += wait
            count = self._proxy.storage.count if self._proxy else 0
            self._log(f"  已捕获 {count} 条请求 ({elapsed:.0f}/{duration:.0f}s)")

    async def _collect_and_export(self, target: MiniAppTarget) -> CaptureResult:
        """收集过滤结果并导出"""
        storage = self._proxy.storage
        total = storage.count
        miniapp_entries = storage.filter_miniapp()

        fmt = target.export_format or self.config.export_format
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = target.name.replace("/", "_").replace(" ", "_")
        ts = int(time.time())
        filename = f"{safe_name}_{ts}.{fmt.value}"
        export_path = output_dir / filename

        if miniapp_entries:
            data = [e.to_dict() for e in miniapp_entries]
            if fmt == ExportFormat.HAR:
                storage.export_har(export_path)
            else:
                export_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        stats = storage.get_stats()

        return CaptureResult(
            miniapp_name=target.name,
            success=True,
            total_requests=total,
            miniapp_requests=len(miniapp_entries),
            export_path=str(export_path) if miniapp_entries else None,
            stats=stats,
        )

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        logger.info(msg)
        self.on_progress(msg)

    def _log_summary(self, results: List[CaptureResult]) -> None:
        success = sum(1 for r in results if r.success)
        total_reqs = sum(r.miniapp_requests for r in results)
        lines = [
            "=== 批量抓取完成 ===",
            f"成功: {success}/{len(results)}",
            f"小程序请求总数: {total_reqs}",
        ]
        for r in results:
            status = "OK" if r.success else f"FAIL: {r.error}"
            lines.append(
                f"  - {r.miniapp_name}: {r.miniapp_requests} 请求, "
                f"{r.duration_seconds:.1f}s [{status}]"
            )
            if r.export_path:
                lines.append(f"    导出: {r.export_path}")
        self._log("\n".join(lines))
