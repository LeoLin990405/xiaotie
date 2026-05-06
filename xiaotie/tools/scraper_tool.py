"""爬虫工具

将爬虫模块集成到 xiaotie Agent 框架，提供 AI 可调用的爬虫能力。
支持运行爬虫、稳定性验证、数据导出、爬虫管理等操作。

Actions:
    - scrape: 运行爬虫抓取数据
    - verify: 多次运行验证数据稳定性
    - export: 导出抓取结果
    - list_scrapers: 列出可用爬虫
    - create_scraper: 从模板创建新爬虫
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..schema import ToolResult
from .base import Tool

logger = logging.getLogger(__name__)

# 爬虫模板代码
_SCRAPER_TEMPLATE = '''\
"""
{name} - 自定义爬虫

由 xiaotie ScraperTool 自动生成。
"""

from xiaotie.scraper import BaseScraper, ScraperConfig, ScrapeResult


class {class_name}(BaseScraper):
    """抓取 {target_url} 的数据"""

    def __init__(self):
        config = ScraperConfig(
            name="{name}",
            target_url="{target_url}",
            max_workers=2,
            request_delay=1.0,
        )
        super().__init__(config)

    async def parse(self, html: str, url: str) -> dict:
        """解析页面内容，返回提取的数据"""
        # TODO: 实现解析逻辑
        return {{"url": url, "content_length": len(html)}}
'''


class ScraperTool(Tool):
    """爬虫工具

    集成 xiaotie 爬虫模块，通过 Agent 调用实现网页数据抓取。

    Actions:
        - scrape: 运行爬虫抓取数据
        - verify: 多次运行验证数据稳定性
        - export: 导出抓取结果（json/csv）
        - list_scrapers: 列出可用爬虫脚本
        - create_scraper: 从模板创建新爬虫
    """

    def __init__(
        self,
        scraper_dir: Optional[str] = None,
        max_workers: int = 4,
        request_delay: float = 1.0,
        num_runs: int = 3,
        stability_threshold: float = 0.9,
    ):
        super().__init__()
        self._scraper_dir = Path(scraper_dir) if scraper_dir else None
        self._max_workers = max_workers
        self._request_delay = request_delay
        self._num_runs = num_runs
        self._stability_threshold = stability_threshold
        self._last_results: List[Dict] = []

    @property
    def name(self) -> str:
        return "scraper"

    @property
    def description(self) -> str:
        return (
            "网页爬虫工具，用于抓取网页数据、验证数据稳定性、导出结果。"
            "支持运行自定义爬虫脚本、多次验证、JSON/CSV 导出。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "scrape",
                        "verify",
                        "export",
                        "list_scrapers",
                        "create_scraper",
                    ],
                    "description": (
                        "操作类型：scrape-运行爬虫，verify-验证稳定性，"
                        "export-导出结果，list_scrapers-列出爬虫，"
                        "create_scraper-创建新爬虫"
                    ),
                },
                "url": {
                    "type": "string",
                    "description": "目标 URL（scrape/verify 操作）",
                },
                "scraper_name": {
                    "type": "string",
                    "description": "爬虫脚本名称（可选，使用已有爬虫）",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv"],
                    "description": "导出格式（默认 json）",
                    "default": "json",
                },
                "output_file": {
                    "type": "string",
                    "description": "导出文件路径",
                },
                "num_runs": {
                    "type": "integer",
                    "description": "验证运行次数（默认 3）",
                    "default": 3,
                },
                "name": {
                    "type": "string",
                    "description": "新爬虫名称（create_scraper 操作）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """执行爬虫操作"""
        action = kwargs.get("action")
        dispatch = {
            "scrape": self._action_scrape,
            "verify": self._action_verify,
            "export": self._action_export,
            "list_scrapers": self._action_list_scrapers,
            "create_scraper": self._action_create_scraper,
        }
        handler = dispatch.get(action)
        if handler is None:
            return ToolResult(success=False, error=f"未知操作: {action}")
        try:
            return await handler(kwargs)
        except ImportError as e:
            return ToolResult(
                success=False,
                error=f"爬虫模块未完整安装: {e}。请确保 xiaotie/scraper/ 模块已就绪。",
            )
        except Exception as e:
            logger.exception("爬虫操作 '%s' 异常", action)
            return ToolResult(success=False, error=f"操作 {action} 异常: {e}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _action_scrape(self, kwargs: dict) -> ToolResult:
        """运行爬虫抓取数据"""
        url = kwargs.get("url")
        scraper_name = kwargs.get("scraper_name")

        if not url and not scraper_name:
            return ToolResult(
                success=False,
                error="请提供 url 或 scraper_name 参数",
            )

        # 如果指定了爬虫名称，加载并运行
        if scraper_name:
            return await self._run_named_scraper(scraper_name, url)

        # 直接抓取 URL
        from ..scraper import BaseScraper, ScraperConfig

        config = ScraperConfig(
            name="adhoc",
            target_url=url,
            max_workers=self._max_workers,
            request_delay=self._request_delay,
        )
        scraper = BaseScraper(config)

        start = time.perf_counter()
        result = await scraper.scrape(url)
        elapsed = time.perf_counter() - start

        if result.success:
            self._last_results = [result.data] if result.data else []
            lines = [
                f"抓取完成 ({elapsed:.1f}s)",
                f"- URL: {url}",
                "- 状态: 成功",
                f"- 数据字段: {len(result.data) if result.data else 0}",
            ]
            if result.data:
                preview = json.dumps(result.data, ensure_ascii=False, indent=2)
                if len(preview) > 2000:
                    preview = preview[:2000] + "\n... (已截断)"
                lines.append(f"\n数据预览:\n{preview}")
            return ToolResult(success=True, content="\n".join(lines))
        else:
            return ToolResult(
                success=False,
                error=f"抓取失败: {result.error}",
            )

    async def _action_verify(self, kwargs: dict) -> ToolResult:
        """多次运行验证数据稳定性"""
        url = kwargs.get("url")
        scraper_name = kwargs.get("scraper_name")
        num_runs = kwargs.get("num_runs", self._num_runs)

        if not url and not scraper_name:
            return ToolResult(
                success=False,
                error="请提供 url 或 scraper_name 参数",
            )

        from ..scraper import (
            BaseScraper,
            ScraperConfig,
            StabilityAnalyzer,
        )

        # 创建或加载爬虫
        if scraper_name:
            scraper = self._load_scraper(scraper_name)
            if scraper is None:
                return ToolResult(
                    success=False,
                    error=f"未找到爬虫: {scraper_name}",
                )
        else:
            config = ScraperConfig(
                name="verify",
                target_url=url,
                max_workers=self._max_workers,
                request_delay=self._request_delay,
            )
            scraper = BaseScraper(config)

        target = url or scraper.config.target_url
        analyzer = StabilityAnalyzer(threshold=self._stability_threshold)

        lines = [f"开始稳定性验证 ({num_runs} 次运行)"]
        lines.append(f"- URL: {target}")
        lines.append(f"- 稳定性阈值: {self._stability_threshold}")
        lines.append("")

        results = []
        for i in range(num_runs):
            result = await scraper.scrape(target)
            results.append(result)
            status = "成功" if result.success else f"失败: {result.error}"
            lines.append(f"  第 {i + 1} 次: {status}")
            if i < num_runs - 1:
                await asyncio.sleep(self._request_delay)

        # 分析稳定性
        report = analyzer.analyze(results)
        lines.append("")
        lines.append("稳定性报告:")
        lines.append(f"- 成功率: {report.success_rate:.0%}")
        lines.append(f"- 数据一致性: {report.consistency_score:.0%}")
        lines.append(f"- 稳定: {'是' if report.is_stable else '否'}")

        if report.changes:
            lines.append(f"- 变化字段: {', '.join(report.changes)}")

        self._last_results = [r.data for r in results if r.success and r.data]

        return ToolResult(success=True, content="\n".join(lines))

    async def _action_export(self, kwargs: dict) -> ToolResult:
        """导出抓取结果"""
        fmt = kwargs.get("format", "json")
        output_file = kwargs.get("output_file")

        if not self._last_results:
            return ToolResult(
                success=True,
                content="没有可导出的数据，请先运行 scrape 或 verify 操作",
            )

        if not output_file:
            output_file = f"scraper_export_{int(time.time())}.{fmt}"
        output_path = Path(output_file).resolve()

        try:
            from ..scraper import OutputFormat, OutputManager

            fmt_enum = OutputFormat.CSV if fmt == "csv" else OutputFormat.JSON
            manager = OutputManager()
            manager.export(self._last_results, output_path, fmt_enum)

            return ToolResult(
                success=True,
                content=(
                    f"已导出 {len(self._last_results)} 条记录\n"
                    f"- 格式: {fmt.upper()}\n"
                    f"- 文件: {output_path}"
                ),
            )
        except ImportError:
            # Fallback: 直接写 JSON
            output_path = output_path.with_suffix(".json")
            output_path.write_text(
                json.dumps(self._last_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return ToolResult(
                success=True,
                content=(
                    f"已导出 {len(self._last_results)} 条记录 (JSON fallback)\n"
                    f"- 文件: {output_path}"
                ),
            )

    async def _action_list_scrapers(self, _kwargs: dict) -> ToolResult:
        """列出可用爬虫脚本"""
        dirs = self._get_scraper_dirs()

        scrapers: List[Dict[str, str]] = []
        for d in dirs:
            if not d.exists():
                continue
            for py_file in sorted(d.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                scrapers.append(
                    {
                        "name": py_file.stem,
                        "path": str(py_file),
                        "dir": str(d),
                    }
                )

        if not scrapers:
            return ToolResult(
                success=True,
                content=(
                    "未找到爬虫脚本\n"
                    "搜索目录:\n"
                    + "\n".join(f"  - {d}" for d in dirs)
                    + "\n\n使用 create_scraper 操作创建新爬虫"
                ),
            )

        lines = [f"可用爬虫 ({len(scrapers)} 个):"]
        for s in scrapers:
            lines.append(f"  - {s['name']}  ({s['path']})")

        return ToolResult(success=True, content="\n".join(lines))

    async def _action_create_scraper(self, kwargs: dict) -> ToolResult:
        """从模板创建新爬虫"""
        name = kwargs.get("name")
        url = kwargs.get("url", "https://example.com")

        if not name:
            return ToolResult(
                success=False,
                error="请提供 name 参数（爬虫名称）",
            )

        # 生成类名
        class_name = (
            "".join(word.capitalize() for word in name.replace("-", "_").split("_")) + "Scraper"
        )

        # 确定输出目录
        dirs = self._get_scraper_dirs()
        output_dir = dirs[0]  # 优先使用 examples 目录
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{name}.py"
        if output_file.exists():
            return ToolResult(
                success=False,
                error=f"爬虫已存在: {output_file}",
            )

        content = _SCRAPER_TEMPLATE.format(
            name=name,
            class_name=class_name,
            target_url=url,
        )
        output_file.write_text(content, encoding="utf-8")

        return ToolResult(
            success=True,
            content=(
                f"爬虫已创建: {output_file}\n"
                f"- 类名: {class_name}\n"
                f"- 目标: {url}\n\n"
                f"请编辑 parse() 方法实现数据提取逻辑"
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_scraper_dirs(self) -> List[Path]:
        """获取爬虫脚本搜索目录"""
        dirs = []
        if self._scraper_dir:
            dirs.append(self._scraper_dir)
        # 默认搜索 xiaotie/scraper/examples/
        pkg_dir = Path(__file__).parent.parent / "scraper" / "examples"
        dirs.append(pkg_dir)
        return dirs

    def _load_scraper(self, name: str):
        """按名称加载爬虫实例"""
        for d in self._get_scraper_dirs():
            py_file = d / f"{name}.py"
            if py_file.exists():
                return self._import_scraper(py_file)
        return None

    def _import_scraper(self, py_file: Path):
        """从文件导入爬虫类并实例化"""
        spec = importlib.util.spec_from_file_location(py_file.stem, str(py_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 查找 BaseScraper 子类
        from ..scraper import BaseScraper

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseScraper) and attr is not BaseScraper:
                return attr()
        return None

    async def _run_named_scraper(self, scraper_name: str, url: Optional[str]) -> ToolResult:
        """运行指定名称的爬虫"""
        scraper = self._load_scraper(scraper_name)
        if scraper is None:
            return ToolResult(
                success=False,
                error=f"未找到爬虫: {scraper_name}",
            )

        target = url or scraper.config.target_url
        start = time.perf_counter()
        result = await scraper.scrape(target)
        elapsed = time.perf_counter() - start

        if result.success:
            self._last_results = [result.data] if result.data else []
            lines = [
                f"爬虫 '{scraper_name}' 完成 ({elapsed:.1f}s)",
                f"- URL: {target}",
                "- 状态: 成功",
            ]
            if result.data:
                preview = json.dumps(result.data, ensure_ascii=False, indent=2)
                if len(preview) > 2000:
                    preview = preview[:2000] + "\n... (已截断)"
                lines.append(f"\n数据预览:\n{preview}")
            return ToolResult(success=True, content="\n".join(lines))
        else:
            return ToolResult(
                success=False,
                error=f"爬虫 '{scraper_name}' 失败: {result.error}",
            )
