"""
demo_scraper - 示例爬虫

演示如何使用 xiaotie 爬虫框架抓取网页数据。
可通过 ScraperTool 的 scrape 操作调用：
    action: scrape, scraper_name: demo_scraper
"""

from xiaotie.scraper import BaseScraper, ScraperConfig


class DemoScraper(BaseScraper):
    """抓取 Hacker News 首页标题"""

    def __init__(self):
        config = ScraperConfig(
            name="demo_scraper",
            target_url="https://news.ycombinator.com",
            max_workers=1,
            request_delay=2.0,
        )
        super().__init__(config)

    async def parse(self, html: str, url: str) -> dict:
        """解析 HN 首页，提取标题列表"""
        import re

        titles = re.findall(
            r'class="titleline"[^>]*><a[^>]*>([^<]+)</a>', html
        )
        return {
            "url": url,
            "title_count": len(titles),
            "titles": titles[:10],
        }
