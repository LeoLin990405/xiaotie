#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xiaotie 爬虫模块示例脚本

演示内容:
1. 基础爬虫 - 最简单的 BaseScraper 用法
2. 多线程爬虫 - 并发抓取多个城市
3. 带认证的爬虫 - Bearer Token / Cookie 认证
4. Agent 集成 - 通过 ScraperTool 在 Agent 中使用
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

# ============================================================
# 示例 1: 基础爬虫
# ============================================================

from xiaotie.scraper import BaseScraper


class BasicScraper(BaseScraper):
    """最简单的爬虫示例 - 只需实现 2 个方法"""

    def get_brand_name(self) -> str:
        return "示例品牌"

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        """单次抓取逻辑"""
        session = self.create_session()
        resp = session.get(
            "https://jsonplaceholder.typicode.com/posts",
            params={"_limit": 10},
        )
        resp.raise_for_status()
        return pd.DataFrame(resp.json())


def demo_basic():
    """运行基础爬虫"""
    print("=" * 60)
    print("示例 1: 基础爬虫")
    print("=" * 60)

    scraper = BasicScraper(test_mode=True)
    result = scraper.run()
    print(f"\n抓取完成: {len(result)} 条数据")
    print(result.head())


# ============================================================
# 示例 2: 多线程爬虫
# ============================================================


class MultiThreadScraper(BaseScraper):
    """多线程并发抓取示例"""

    ENDPOINTS = [
        "/posts",
        "/comments",
        "/albums",
        "/photos",
        "/todos",
    ]

    def get_brand_name(self) -> str:
        return "多线程示例"

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        all_data = []
        endpoints = self.ENDPOINTS[:2] if self.test_mode else self.ENDPOINTS

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_endpoint, ep): ep
                for ep in endpoints
            }
            for future in as_completed(futures):
                endpoint = futures[future]
                try:
                    data = future.result()
                    all_data.extend(data)
                    print(f"  {endpoint}: {len(data)} 条")
                except Exception as e:
                    print(f"  {endpoint} 失败: {e}")

        return pd.DataFrame(all_data)

    def _fetch_endpoint(self, endpoint: str) -> list:
        session = self.create_session()
        resp = session.get(
            f"https://jsonplaceholder.typicode.com{endpoint}",
            params={"_limit": 5},
        )
        resp.raise_for_status()
        return resp.json()


def demo_multithread():
    """运行多线程爬虫"""
    print("\n" + "=" * 60)
    print("示例 2: 多线程爬虫")
    print("=" * 60)

    scraper = MultiThreadScraper(test_mode=True, max_workers=3)
    result = scraper.run()
    print(f"\n抓取完成: {len(result)} 条数据")


# ============================================================
# 示例 3: 带认证的爬虫
# ============================================================

from xiaotie.scraper import AuthType


class AuthenticatedScraper(BaseScraper):
    """带认证的爬虫示例"""

    def get_brand_name(self) -> str:
        return "认证示例"

    def setup(self):
        """初始化认证配置"""
        # Bearer Token 认证
        self.set_auth(AuthType.BEARER, token="demo-token-12345")

    def fetch_data_single_run(self, run_number: int) -> pd.DataFrame:
        session = self.create_session()
        # 认证头会自动添加到 session 中
        resp = session.get(
            "https://jsonplaceholder.typicode.com/posts",
            params={"_limit": 5},
        )
        resp.raise_for_status()
        return pd.DataFrame(resp.json())

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据后处理：只保留需要的列"""
        if "userId" in df.columns:
            df = df[["id", "userId", "title"]]
        return df.drop_duplicates(subset=["id"])


def demo_auth():
    """运行带认证的爬虫"""
    print("\n" + "=" * 60)
    print("示例 3: 带认证的爬虫")
    print("=" * 60)

    scraper = AuthenticatedScraper(test_mode=True)
    result = scraper.run()
    print(f"\n抓取完成: {len(result)} 条数据")
    print(result.head())


# ============================================================
# 示例 4: Agent 集成
# ============================================================


async def demo_agent_integration():
    """通过 ScraperTool 在 Agent 中使用爬虫"""
    print("\n" + "=" * 60)
    print("示例 4: Agent 集成 (ScraperTool)")
    print("=" * 60)

    from xiaotie.tools import ScraperTool

    tool = ScraperTool()

    # 列出可用品牌
    result = await tool.execute(action="list_brands")
    print(f"\n可用品牌:\n{result.content}")

    # 运行爬虫
    result = await tool.execute(
        action="run",
        brand="示例品牌",
        mode="test",
    )
    print(f"\n运行结果:\n{result.content}")

    # 查看状态
    result = await tool.execute(action="status")
    print(f"\n状态:\n{result.content}")


# ============================================================
# 主入口
# ============================================================


def main():
    """运行所有示例"""
    print("xiaotie 爬虫模块示例")
    print("=" * 60)

    # 基础示例
    demo_basic()

    # 多线程示例
    demo_multithread()

    # 认证示例
    demo_auth()

    # Agent 集成示例（异步）
    print("\n[Agent 集成示例需要完整的 xiaotie 环境]")
    print("运行方式: asyncio.run(demo_agent_integration())")


if __name__ == "__main__":
    main()
